"""Run parsed statements against in-memory tables.

Rows live in a ``Table``, which stores them in a ``BTree`` keyed by primary key,
so a SELECT without ORDER BY yields rows in key order.

NULL handling follows SQL's three-valued logic: a comparison with NULL is NULL,
and WHERE keeps a row only when its condition is TRUE.
"""

from typing import Any, Dict, List, Optional

from tinysql.parser import And, Column, Compare, CreateTable, Delete, Insert, Literal, Not, Or, Select
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
        if isinstance(stmt, Delete):
            return self._delete(stmt)
        raise ExecError(f"cannot run {type(stmt).__name__}")

    def _create(self, stmt: CreateTable) -> int:
        if stmt.table in self.tables:
            raise ExecError(f"table {stmt.table!r} already exists")
        columns = [TableColumn(c.name, PY_TYPES[c.type_name], c.nullable) for c in stmt.columns]
        try:
            self.tables[stmt.table] = Table(stmt.table, columns, stmt.primary_key)
        except TableError as exc:
            raise ExecError(str(exc)) from exc
        return 0

    def _table(self, name: str) -> Table:
        if name not in self.tables:
            raise ExecError(f"no such table {name!r}")
        return self.tables[name]

    def _insert(self, stmt: Insert) -> int:
        table = self._table(stmt.table)
        names = stmt.columns or tuple(c.name for c in table.columns)
        try:
            table.insert(dict(zip(names, stmt.values)))
        except TableError as exc:
            raise ExecError(str(exc)) from exc
        return 1

    def _delete(self, stmt: Delete) -> int:
        table = self._table(stmt.table)
        return table.delete_where(lambda r: self._eval(stmt.where, r) is True)

    def _select(self, stmt: Select) -> List[Dict[str, Any]]:
        table = self._table(stmt.table)
        all_names = [c.name for c in table.columns]
        names = stmt.columns or tuple(all_names)
        for name in list(names) + ([stmt.order_by] if stmt.order_by else []):
            if name not in all_names:
                raise ExecError(f"no such column {name!r}")

        rows = [r for r in table.scan() if stmt.where is None or self._eval(stmt.where, r) is True]
        if stmt.order_by:
            rows.sort(key=lambda r: (r[stmt.order_by] is not None, r[stmt.order_by]))
        if stmt.limit is not None:
            rows = rows[: stmt.limit]
        return [{n: r[n] for n in names} for r in rows]

    def _eval(self, expr, row: Dict[str, Any]) -> Optional[bool]:
        if isinstance(expr, Column):
            if expr.name not in row:
                raise ExecError(f"no such column {expr.name!r}")
            return row[expr.name]
        if isinstance(expr, Literal):
            return expr.value
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
