"""Read SQL statements from stdin and print the results.

A new database starts with one demo table, ``users``. With ``--db PATH`` every
table (including ones made by CREATE TABLE) is kept in a page file: loaded at
start if the file exists, and written back after each statement.
"""

import os
import sys
from typing import Any, List, Optional, TextIO

from tinysql.executor import ExecError, Executor
from tinysql.paged import read_database, write_database
from tinysql.parser import Delete, ParseError, parse
from tinysql.table import Column, Table, TableError
from tinysql.tokenizer import TokenizeError


def demo_table() -> Table:
    return Table(
        "users",
        [Column("id", int), Column("name", str, nullable=True), Column("score", float, nullable=True)],
        primary_key="id",
    )


def demo_executor(db_path: Optional[str] = None) -> Executor:
    if db_path and os.path.exists(db_path):
        return Executor(read_database(db_path))
    return Executor({"users": demo_table()})


def save_database(executor: Executor, db_path: str) -> None:
    write_database(executor.tables, db_path)


def format_result(result: Any, verb: str = "inserted") -> str:
    if isinstance(result, int):
        return f"{result} row(s) {verb}"
    rows: List[dict] = result
    if not rows:
        return "(0 rows)"
    names = list(rows[0])
    cells = [[str(r[n]) for n in names] for r in rows]
    widths = [max(len(n), *(len(row[i]) for row in cells)) for i, n in enumerate(names)]
    lines = [" | ".join(n.ljust(w) for n, w in zip(names, widths))]
    lines.append("-+-".join("-" * w for w in widths))
    lines += [" | ".join(v.ljust(w) for v, w in zip(row, widths)) for row in cells]
    lines.append(f"({len(rows)} row{'s' if len(rows) != 1 else ''})")
    return "\n".join(lines)


def run_line(executor: Executor, line: str) -> str:
    """Run one statement and return its printable output. Errors are returned, not raised."""
    try:
        stmt = parse(line)
        verb = "deleted" if isinstance(stmt, Delete) else "inserted"
        return format_result(executor.run(stmt), verb)
    except (ParseError, TokenizeError, ExecError, TableError) as exc:
        return f"error: {exc}"


def main(
    stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout, db_path: Optional[str] = None
) -> None:
    executor = demo_executor(db_path)
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        print(run_line(executor, line), file=stdout)
        if db_path:
            save_database(executor, db_path)


if __name__ == "__main__":
    main(db_path=sys.argv[2] if sys.argv[1:2] == ["--db"] else None)
