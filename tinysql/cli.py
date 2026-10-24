"""Read SQL statements from stdin and print the results.

The schema is fixed for now: one demo table, ``users``, because the parser
has no CREATE TABLE yet.
"""

import sys
from typing import Any, List, TextIO

from tinysql.executor import ExecError, Executor
from tinysql.parser import ParseError, parse
from tinysql.table import Column, Table, TableError
from tinysql.tokenizer import TokenizeError


def demo_executor() -> Executor:
    users = Table(
        "users",
        [Column("id", int), Column("name", str, nullable=True), Column("score", float, nullable=True)],
        primary_key="id",
    )
    return Executor({"users": users})


def format_result(result: Any) -> str:
    if isinstance(result, int):
        return f"{result} row(s) inserted"
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
        return format_result(executor.run(parse(line)))
    except (ParseError, TokenizeError, ExecError, TableError) as exc:
        return f"error: {exc}"


def main(stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> None:
    executor = demo_executor()
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        print(run_line(executor, line), file=stdout)


if __name__ == "__main__":
    main()
