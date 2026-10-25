"""Run parsed statements against in-memory tables.

Rows live in a ``Table``, which stores them in a ``BTree`` keyed by primary key,
so a SELECT without ORDER BY yields rows in key order.

NULL handling follows SQL's three-valued logic: a comparison with NULL is NULL,
and WHERE keeps a row only when its condition is TRUE.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from tinysql.parser import And, Arith, Column, Compare, CreateIndex, CreateTable, Delete, DropTable, InList, Insert, IsNull, Like, Literal, Not, Or, Select, Update
from tinysql.table import Column as TableColumn, Table, TableError

PY_TYPES = {"INT": int, "FLOAT": float, "TEXT": str, "BOOL": bool}

COMPARE = {
    "=": lambda a, b: a == b,
    "<>": lambda a, b: a != b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
}


COUNT_STAR = ("COUNT(*)",)


def like_match(value, pattern):
    """SQL LIKE: % matches any run of characters, _ matches exactly one."""
    regex = "".join(
        ".*" if ch == "%" else "." if ch == "_" else re.escape(ch) for ch in pattern
    )
    return re.fullmatch(regex, value, re.DOTALL) is not None


AGGREGATES = ("COUNT", "MIN", "MAX", "SUM", "AVG")


class ExecError(ValueError):
    """Raised for unknown tables or columns."""


class Executor:
    def __init__(self, tables: Dict[str, Table]):
        self.tables = tables

    def run(self, stmt) -> Any:
        if isinstance(stmt, Insert):
            return self._insert(stmt)
        if isinstance(stmt, Select):
            return self._select(stmt)
        if isinstance(stmt, CreateTable):
            return self._create(stmt)
        if isinstance(stmt, CreateIndex):
            return self._create_index(stmt)
        if isinstance(stmt, DropTable):
            return self._drop(stmt)
        if isinstance(stmt, Delete):
            return self._delete(stmt)
        if isinstance(stmt, Update):
            return self._update(stmt)
        raise ExecError(f"cannot run {type(stmt).__name__}")

    def _create(self, stmt: CreateTable) -> int:
        if stmt.table in self.tables:
            if stmt.if_not_exists:
                return 0
            raise ExecError(f"table {stmt.table!r} already exists")
        columns = [TableColumn(c.name, PY_TYPES[c.type_name], c.nullable) for c in stmt.columns]
        try:
            self.tables[stmt.table] = Table(stmt.table, columns, stmt.primary_key)
        except TableError as exc:
            raise ExecError(str(exc)) from exc
        return 0

    def _create_index(self, stmt: CreateIndex) -> int:
        table = self._table(stmt.table)
        try:
            table.create_index(stmt.column)
        except TableError as exc:
            raise ExecError(str(exc)) from exc
        return 0

    def _drop(self, stmt: DropTable) -> int:
        if stmt.if_exists and stmt.table not in self.tables:
            return 0
        self._table(stmt.table)
        del self.tables[stmt.table]
        return 0

    def _table(self, name: str) -> Table:
        if name not in self.tables:
            raise ExecError(f"no such table {name!r}")
        return self.tables[name]

    def _insert(self, stmt: Insert) -> int:
        table = self._table(stmt.table)
        names = stmt.columns or tuple(c.name for c in table.columns)
        try:
            for values in stmt.rows:
                table.insert(dict(zip(names, values)))
        except TableError as exc:
            raise ExecError(str(exc)) from exc
        return 1

    def _update(self, stmt: Update) -> int:
        table = self._table(stmt.table)
        if not isinstance(stmt.value, Literal):
            raise ExecError("UPDATE SET takes a literal value")
        return table.update_where(
            lambda r: self._eval(stmt.where, r) is True, stmt.column, stmt.value.value
        )

    def _delete(self, stmt: Delete) -> int:
        table = self._table(stmt.table)
        return table.delete_where(lambda r: self._eval(stmt.where, r) is True)

    def _joined_rows(self, stmt: Select) -> Tuple[List[str], List[Dict[str, Any]]]:
        """Inner nested-loop join of stmt.table with stmt.join.table on the ON condition."""
        left = self._table(stmt.table)
        right = self._table(stmt.join.table)
        left_names = [c.name for c in left.columns]
        right_names = [c.name for c in right.columns]
        clash = set(left_names) & set(right_names)
        if clash:
            raise ExecError(f"ambiguous column names in JOIN: {sorted(clash)}")
        rows = []
        right_rows = list(right.scan())
        for l in left.scan():
            for r in right_rows:
                merged = {**l, **r}
                if self._eval(stmt.join.on, merged) is True:
                    rows.append(merged)
        return left_names + right_names, rows

    @staticmethod
    def _indexed_equality(table: Table, where) -> Optional[Tuple[str, Any]]:
        """(column, value) when WHERE is `indexed_column = literal`, or an AND with such a term."""
        if isinstance(where, And):
            return Executor._indexed_equality(table, where.left) or Executor._indexed_equality(table, where.right)
        if (isinstance(where, Compare) and where.op == "=" and isinstance(where.left, Column)
                and isinstance(where.right, Literal) and table.has_index(where.left.name)):
            return where.left.name, where.right.value
        return None

    def _select(self, stmt: Select) -> List[Dict[str, Any]]:
        table = self._table(stmt.table)
        all_names = [c.name for c in table.columns]
        source = table.scan
        indexed = self._indexed_equality(table, stmt.where)
        if indexed is not None:
            # The WHERE filter below still runs, so the index only narrows the scan.
            source = lambda: table.lookup(*indexed)
        if stmt.join is not None:
            all_names, joined = self._joined_rows(stmt)
            source = lambda: iter(joined)
        if stmt.columns and isinstance(stmt.columns[0], tuple) and stmt.columns[0][0] in AGGREGATES:
            if stmt.join is not None:
                raise ExecError("aggregate functions with JOIN are not supported")
            func, name = stmt.columns[0]
            if stmt.group_by:
                raise ExecError("GROUP BY with aggregate functions is not supported")
            if name not in all_names:
                raise ExecError(f"no such column {name!r}")
            matched = [r[name] for r in table.scan()
                       if (stmt.where is None or self._eval(stmt.where, r) is True) and r[name] is not None]
            if func == "COUNT":
                return [{f"COUNT({name})": len(matched)}]
            if func == "SUM":
                return [{f"SUM({name})": sum(matched) if matched else None}]
            if func == "AVG":
                return [{f"AVG({name})": sum(matched) / len(matched) if matched else None}]
            pick = min if func == "MIN" else max
            return [{f"{func}({name})": pick(matched) if matched else None}]
        if stmt.columns == COUNT_STAR:
            matched = [r for r in table.scan() if stmt.where is None or self._eval(stmt.where, r) is True]
            return [{"COUNT(*)": len(matched)}]
        items = [(n, n) if isinstance(n, str) else n for n in stmt.columns or all_names]
        names = [src for src, _ in items]
        for name in names + list(stmt.order_by or ()):
            if name not in all_names:
                raise ExecError(f"no such column {name!r}")

        rows = [r for r in source() if stmt.where is None or self._eval(stmt.where, r) is True]
        for name in reversed(stmt.order_by or ()):
            rows.sort(key=lambda r: (r[name] is not None, r[name]), reverse=stmt.order_desc)
        if stmt.group_by:
            for name in names:
                if name not in stmt.group_by:
                    raise ExecError(f"column {name!r} must appear in GROUP BY")
        if stmt.having is not None and not stmt.group_by:
            raise ExecError("HAVING requires GROUP BY")
        projected = [{out: r[src] for src, out in items} for r in rows]
        if stmt.group_by:
            # One row per group: keep the first row seen for each group key.
            seen_groups = set()
            grouped = []
            for r, p in zip(rows, projected):
                key = tuple(r[g] for g in stmt.group_by)
                if key in seen_groups:
                    continue
                seen_groups.add(key)
                if stmt.having is None or self._eval(stmt.having, r) is True:
                    grouped.append(p)
            projected = grouped
        if stmt.distinct:
            seen = set()
            unique = []
            for r in projected:
                key = tuple(r.items())
                if key not in seen:
                    seen.add(key)
                    unique.append(r)
            projected = unique
        projected = projected[stmt.offset:]
        if stmt.limit is not None:
            projected = projected[: stmt.limit]
        return projected

    def _eval(self, expr, row: Dict[str, Any]) -> Optional[bool]:
        if isinstance(expr, Column):
            if expr.name not in row:
                raise ExecError(f"no such column {expr.name!r}")
            return row[expr.name]
        if isinstance(expr, Literal):
            return expr.value
        if isinstance(expr, Arith):
            a = self._eval(expr.left, row)
            b = self._eval(expr.right, row)
            if a is None or b is None:
                return None
            if expr.op == "*":
                return a * b
            if expr.op == "/":
                if b == 0:
                    raise ExecutionError("division by zero")
                q = abs(a) // abs(b)  # SQL integer division truncates toward zero
                return q if (a < 0) == (b < 0) else -q
            if expr.op == "%":
                if b == 0:
                    raise ExecutionError("division by zero")
                return a - b * self._eval(Arith("/", Literal(a), Literal(b)), row)
            return a + b if expr.op == "+" else a - b
        if isinstance(expr, InList):
            a = self._eval(expr.operand, row)
            if a is None:
                return None
            values = [self._eval(item, row) for item in expr.items]
            if a in values:
                return True
            return None if None in values else False
        if isinstance(expr, Like):
            value = self._eval(expr.operand, row)
            pattern = self._eval(expr.pattern, row)
            if value is None or pattern is None:
                return None
            return like_match(str(value), str(pattern))
        if isinstance(expr, IsNull):
            return self._eval(expr.operand, row) is None
        if isinstance(expr, Compare):
            a, b = self._eval(expr.left, row), self._eval(expr.right, row)
            if a is None or b is None:
                return None
            return COMPARE[expr.op](a, b)
        if isinstance(expr, And):
            a, b = self._eval(expr.left, row), self._eval(expr.right, row)
            if a is False or b is False:
                return False
            return True if a is True and b is True else None
        if isinstance(expr, Or):
            a, b = self._eval(expr.left, row), self._eval(expr.right, row)
            if a is True or b is True:
                return True
            return False if a is False and b is False else None
        if isinstance(expr, Not):
            v = self._eval(expr.operand, row)
            return None if v is None else not v
        raise ExecError(f"cannot evaluate {type(expr).__name__}")
