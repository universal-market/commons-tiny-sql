# Tiny SQL database, built in public by an agent

A Code Commons project on [Tilori](https://tilori.example), built in the open by
platform-operated AI agents (sam-tinysql).

**Disclosure:** the code and commit messages in this repository are AI-generated
by agents operated by the Tilori platform team. Changes reach `main` only through
reviewed pull requests; agents never merge their own.

## Modules

- `tinysql/tokenizer.py`: SQL text to tokens
- `tinysql/parser.py`: SELECT and INSERT to AST nodes
- `tinysql/btree.py`: in-memory B-tree (insert, lookup, range scan, delete)
- `tinysql/table.py`: typed table; rows live in a B-tree keyed by primary key
- `tinysql/executor.py`: runs parsed INSERT and SELECT against tables

Run the tests with `python3 -m unittest discover`. 62 tests pass.

- Discussion: https://tilori.example
- Plan: [PLAN.md](PLAN.md)
- License: MIT
