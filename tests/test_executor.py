import unittest

from tinysql.executor import ExecError, Executor
from tinysql.parser import parse
from tinysql.table import Column, Table


def make_db():
    users = Table(
        "users",
        [Column("id", int), Column("name", str, nullable=True), Column("score", float, nullable=True)],
        primary_key="id",
    )
    return Executor({"users": users})


class ExecutorTests(unittest.TestCase):
    def run_sql(self, db, sql):
        return db.run(parse(sql))

    def test_insert_then_select_all(self):
        db = make_db()
        self.assertEqual(self.run_sql(db, "INSERT INTO users VALUES (2, 'bo', 1.5)"), 1)
        self.run_sql(db, "INSERT INTO users (id, name) VALUES (1, 'al')")
        self.assertEqual(
            self.run_sql(db, "SELECT * FROM users"),
            [
                {"id": 1, "name": "al", "score": None},
                {"id": 2, "name": "bo", "score": 1.5},
            ],
        )

    def test_where_order_limit_and_projection(self):
        db = make_db()
        for i in range(10):
            self.run_sql(db, f"INSERT INTO users VALUES ({i}, 'n{i}', {i}.0)")
        rows = self.run_sql(
            db, "SELECT id FROM users WHERE score >= 3.0 AND NOT id = 7 ORDER BY score LIMIT 3"
        )
        self.assertEqual(rows, [{"id": 3}, {"id": 4}, {"id": 5}])

    def test_null_comparison_is_not_true(self):
        db = make_db()
        self.run_sql(db, "INSERT INTO users (id) VALUES (1)")
        self.run_sql(db, "INSERT INTO users VALUES (2, 'x', 2.0)")
        self.assertEqual(self.run_sql(db, "SELECT id FROM users WHERE name = 'x'"), [{"id": 2}])
        self.assertEqual(self.run_sql(db, "SELECT id FROM users WHERE NOT name = 'x'"), [])
        self.assertEqual(
            self.run_sql(db, "SELECT id FROM users WHERE name = 'x' OR id = 1"),
            [{"id": 1}, {"id": 2}],
        )

    def test_order_by_puts_nulls_first(self):
        db = make_db()
        self.run_sql(db, "INSERT INTO users VALUES (1, 'a', 2.0)")
        self.run_sql(db, "INSERT INTO users (id) VALUES (2)")
        rows = self.run_sql(db, "SELECT id FROM users ORDER BY score")
        self.assertEqual(rows, [{"id": 2}, {"id": 1}])

    def test_errors(self):
        db = make_db()
        with self.assertRaisesRegex(ExecError, "no such table"):
            self.run_sql(db, "SELECT * FROM nope")
        with self.assertRaisesRegex(ExecError, "no such column"):
            self.run_sql(db, "SELECT bogus FROM users")
        self.run_sql(db, "INSERT INTO users (id) VALUES (1)")
        with self.assertRaisesRegex(ExecError, "duplicate primary key"):
            self.run_sql(db, "INSERT INTO users (id) VALUES (1)")


class CreateTableExecutorTests(unittest.TestCase):
    def test_create_then_insert_and_select(self):
        db = Executor({})
        db.run(parse("CREATE TABLE t (id INT, name TEXT NULL, PRIMARY KEY (id))"))
        db.run(parse("INSERT INTO t (id) VALUES (1)"))
        self.assertEqual(db.run(parse("SELECT * FROM t")), [{"id": 1, "name": None}])

    def test_existing_table_is_rejected(self):
        db = Executor({})
        db.run(parse("CREATE TABLE t (id INT, PRIMARY KEY (id))"))
        with self.assertRaises(ExecError):
            db.run(parse("CREATE TABLE t (id INT, PRIMARY KEY (id))"))


if __name__ == "__main__":
    unittest.main()
