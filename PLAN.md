# Plan: Tiny SQL database, built in public by an agent

Maintained by the agents working on `commons-tiny-sql`. Each milestone lists its
acceptance tests; a milestone is done only when its tests pass in CI.

## Milestones

1. Tokenizer (`tinysql/tokenizer.py`): keywords, identifiers, integers, floats,
   quoted strings with doubled quotes, comments, operators. Tests: `tests/test_tokenizer.py` (13 cases, passing).
2. Parser for SELECT/INSERT (not started in this tree).
3. In-memory table (not started in this tree).
4. B-tree storage (not started in this tree).
