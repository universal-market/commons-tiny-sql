"""In-memory table: a schema, a primary key and rows stored in a dict."""

from dataclasses import dataclass
from typing import Any, Dict, Iterator, Optional, Sequence, Tuple

from tinysql.btree import BTree


class TableError(ValueError):
    """Raised for schema, type and key violations."""


@dataclass(frozen=True)
class Column:
    name: str
    type: type  # int, float, str or bool
    nullable: bool = False


class Table:
    def __init__(self, name: str, columns: Sequence[Column], primary_key: str):
        names = [c.name for c in columns]
        if len(set(names)) != len(names):
            raise TableError("duplicate column name")
        if primary_key not in names:
            raise TableError(f"primary key {primary_key!r} is not a column")
        self.name = name
        self.columns: Tuple[Column, ...] = tuple(columns)
        self.primary_key = primary_key
        self._by_name = {c.name: c for c in columns}
        self._rows = BTree(order=8)  # primary key -> row dict

    def insert(self, row: Dict[str, Any]) -> None:
        """Insert one row given as {column: value}. Missing columns become NULL."""
        unknown = set(row) - set(self._by_name)
        if unknown:
            raise TableError(f"unknown column(s): {sorted(unknown)}")
        clean = {}
        for col in self.columns:
            value = row.get(col.name)
            self._check(col, value)
            clean[col.name] = value
        key = clean[self.primary_key]
        if key in self._rows:
            raise TableError(f"duplicate primary key {key!r}")
        self._rows.insert(key, clean)

    def delete_where(self, keep_out) -> int:
        """Delete every row for which ``keep_out(row)`` is true; return how many."""
        doomed = [row[self.primary_key] for row in self.scan() if keep_out(row)]
        for key in doomed:
            self._rows.delete(key)
        return len(doomed)

    def update_where(self, match, column: str, value: Any) -> int:
        """Set ``column`` to ``value`` on every row where ``match(row)`` is true; return how many.

        The primary key cannot be changed. The new value is type-checked.
        """
        if column == self.primary_key:
            raise TableError("cannot update the primary key")
        if column not in self._by_name:
            raise TableError(f"unknown column {column!r}")
        self._check(self._by_name[column], value)
        hits = [row for row in self.scan() if match(row)]
        for row in hits:
            row[column] = value
            self._rows.insert(row[self.primary_key], row)
        return len(hits)

    def get(self, key: Any) -> Optional[Dict[str, Any]]:
        row = self._rows.get(key)
        return dict(row) if row is not None else None

    def scan(self) -> Iterator[Dict[str, Any]]:
        """Yield copies of all rows in primary-key order."""
        for _, row in self._rows.items():
            yield dict(row)

    def __len__(self) -> int:
        return len(self._rows)

    def _check(self, col: Column, value: Any) -> None:
        if value is None:
            if not col.nullable or col.name == self.primary_key:
                raise TableError(f"column {col.name!r} may not be NULL")
            return
        # bool is a subclass of int, so reject it for int columns explicitly.
        if col.type is int and (isinstance(value, bool) or not isinstance(value, int)):
            raise TableError(f"column {col.name!r} expects int, got {value!r}")
        if col.type is not int and not isinstance(value, col.type):
            raise TableError(f"column {col.name!r} expects {col.type.__name__}, got {value!r}")
