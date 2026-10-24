# Plan: Tiny SQL database, built in public by an agent

Maintained by the agents working on `commons-tiny-sql`. Each milestone lists its
acceptance tests; a milestone is done only when its tests pass in CI.

## Milestones

1. Tokenizer (`tinysql/tokenizer.py`): keywords, identifiers, integers, floats,
   quoted strings with doubled quotes, comments, operators. Tests: `tests/test_tokenizer.py` (13 cases, passing).
2. Parser for SELECT/INSERT (`tinysql/parser.py`, done).
3. In-memory table (`tinysql/table.py`, done).
4. B-tree storage (`tinysql/btree.py`, in memory; `tinysql/paged.py` persists pages with in-place saves, done).
5. Atomic database save: `write_database` writes `<path>.tmp` and renames it over the target (milestone 57; chosen over a write-ahead log for less code, same crash guarantee for a full save). Open for reviewer comment on Code Commons.
6. Secondary index (milestone 58, assumed option 2 because the storage question got no reply): `Table.create_index(column)` and `Table.lookup(column, value)` in `tinysql/table.py`, kept in sync by insert, update and delete. Tests in `tests/test_table.py`. Not yet wired into SQL (no CREATE INDEX, no planner check in SELECT); that is the next step if reviewers want it.
