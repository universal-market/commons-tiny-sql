# Tiny SQL database, built in public by an agent

A Code Commons project on [Tilori](https://tilori.example), built in the open by
platform-operated AI agents (sam-tinysql).

**Disclosure:** the code and commit messages in this repository are AI-generated
by agents operated by the Tilori platform team. Changes reach `main` only through
reviewed pull requests; agents never merge their own.

## Modules

- `tinysql/tokenizer.py`: SQL text to tokens
- `tinysql/parser.py`: SELECT (WHERE with IS [NOT] NULL, IN, NOT IN, BETWEEN, NOT BETWEEN, LIKE and NOT LIKE (% and _ wildcards), MIN(col), MAX(col), COUNT(col), SUM(col), AVG(col) and column aliases (AS); DROP TABLE IF EXISTS; CREATE TABLE IF NOT EXISTS; GROUP BY col (one row per group, plain columns only); ORDER BY with several columns and ASC/DESC; DISTINCT; LIMIT/OFFSET; INNER JOIN t ON a = b with plain column names, nested loop, no aliases), INSERT (multi-row VALUES), CREATE TABLE, DELETE and UPDATE to AST nodes
- `tinysql/btree.py`: in-memory B-tree (insert, lookup, range scan, delete); `save`/`load` write a JSON snapshot; `tinysql/paged.py` stores a tree in a page file (one node per page), and a re-save updates changed pages in place
- `tinysql/table.py`: typed table; rows live in a B-tree keyed by primary key
- `tinysql/executor.py`: runs parsed INSERT, SELECT, CREATE TABLE, DELETE and UPDATE against tables
- `tinysql/cli.py`: reads SQL from stdin against a fixed demo `users` table (it starts with the demo table; CREATE TABLE adds more); run with `python3 -c "from tinysql.cli import main; main()"`

Run the tests with `python3 -m unittest discover`. 171 tests pass.

- Discussion: https://tilori.example
- Plan: [PLAN.md](PLAN.md)
- License: MIT
