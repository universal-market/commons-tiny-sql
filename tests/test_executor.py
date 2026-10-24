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

    def test_order_by_two_columns(self):
        db = make_db()
        self.run_sql(db, "INSERT INTO users VALUES (1, 'b', 2.0)")
        self.run_sql(db, "INSERT INTO users VALUES (2, 'a', 2.0)")
        self.run_sql(db, "INSERT INTO users VALUES (3, 'a', 1.0)")
        rows = self.run_sql(db, "SELECT id FROM users ORDER BY score, name")
        self.assertEqual(rows, [{"id": 3}, {"id": 2}, {"id": 1}])

    def test_order_by_explicit_asc(self):
        db = make_db()
        self.run_sql(db, "INSERT INTO users VALUES (1, 'b', 2.0)")
        self.run_sql(db, "INSERT INTO users VALUES (2, 'a', 1.0)")
        rows = self.run_sql(db, "SELECT id FROM users ORDER BY score ASC")
        self.assertEqual(rows, [{"id": 2}, {"id": 1}])

    def test_order_by_desc_puts_nulls_last(self):
        db = make_db()
        self.run_sql(db, "INSERT INTO users VALUES (1, 'a', 2.0)")
        self.run_sql(db, "INSERT INTO users VALUES (3, 'c', 5.0)")
        self.run_sql(db, "INSERT INTO users (id) VALUES (2)")
        rows = self.run_sql(db, "SELECT id FROM users ORDER BY score DESC")
        self.assertEqual(rows, [{"id": 3}, {"id": 1}, {"id": 2}])

    def test_limit_with_offset(self):
        db = make_db()
        for i in range(1, 5):
            self.run_sql(db, f"INSERT INTO users VALUES ({i}, 'u{i}', 1.0)")
        rows = self.run_sql(db, "SELECT id FROM users ORDER BY id LIMIT 2 OFFSET 1")
        self.assertEqual(rows, [{"id": 2}, {"id": 3}])

    def test_insert_multiple_rows(self):
        db = make_db()
        self.run_sql(db, "INSERT INTO users (id, name) VALUES (1, 'a'), (2, 'b')")
        self.assertEqual(self.run_sql(db, "SELECT COUNT(*) FROM users"), [{"COUNT(*)": 2}])

    def test_delete_and_update_missing_table_raise(self):
        from tinysql.parser import parse

        db = make_db()
        for sql in ("DELETE FROM nope WHERE id = 1", "UPDATE nope SET name = 'x' WHERE id = 1"):
            with self.assertRaises(ExecError):
                self.run_sql(db, sql)

    def test_where_is_null(self):
        db = make_db()
        self.run_sql(db, "INSERT INTO users (id, name) VALUES (1, 'a')")
        self.run_sql(db, "INSERT INTO users (id, name) VALUES (2, 'b')")
        self.run_sql(db, "UPDATE users SET score = 1.5 WHERE id = 2")
        rows = self.run_sql(db, "SELECT id FROM users WHERE score IS NULL")
        self.assertEqual(rows, [{"id": 1}])

    def test_where_is_not_null(self):
        db = make_db()
        self.run_sql(db, "INSERT INTO users (id, name) VALUES (1, 'a')")
        self.run_sql(db, "INSERT INTO users (id, name) VALUES (2, 'b')")
        self.run_sql(db, "UPDATE users SET score = 1.5 WHERE id = 2")
        rows = self.run_sql(db, "SELECT id FROM users WHERE score IS NOT NULL")
        self.assertEqual(rows, [{"id": 2}])

    def test_where_in_list(self):
        db = make_db()
        for i in (1, 2, 3):
            self.run_sql(db, f"INSERT INTO users (id, name) VALUES ({i}, 'u{i}')")
        rows = self.run_sql(db, "SELECT id FROM users WHERE id IN (1, 3)")
        self.assertEqual(rows, [{"id": 1}, {"id": 3}])

    def test_select_distinct(self):
        db = make_db()
        for i, name in ((1, "a"), (2, "a"), (3, "b")):
            self.run_sql(db, f"INSERT INTO users (id, name) VALUES ({i}, '{name}')")
        rows = self.run_sql(db, "SELECT DISTINCT name FROM users")
        self.assertEqual(rows, [{"name": "a"}, {"name": "b"}])

    def test_where_between(self):
        db = make_db()
        for i in (1, 2, 3, 4):
            self.run_sql(db, f"INSERT INTO users (id, name) VALUES ({i}, 'u{i}')")
        rows = self.run_sql(db, "SELECT id FROM users WHERE id BETWEEN 2 AND 3")
        self.assertEqual(rows, [{"id": 2}, {"id": 3}])

    def test_where_not_in_list(self):
        db = make_db()
        for i in (1, 2, 3):
            self.run_sql(db, f"INSERT INTO users (id, name) VALUES ({i}, 'u{i}')")
        rows = self.run_sql(db, "SELECT id FROM users WHERE id NOT IN (1, 3)")
        self.assertEqual(rows, [{"id": 2}])

    def test_where_not_between(self):
        db = make_db()
        for i in (1, 2, 3, 4):
            self.run_sql(db, f"INSERT INTO users (id, name) VALUES ({i}, 'u{i}')")
        rows = self.run_sql(db, "SELECT id FROM users WHERE id NOT BETWEEN 2 AND 3")
        self.assertEqual(rows, [{"id": 1}, {"id": 4}])

    def test_where_like(self):
        db = make_db()
        for i, name in ((1, "alpha"), (2, "beta"), (3, "alps")):
            self.run_sql(db, f"INSERT INTO users (id, name) VALUES ({i}, '{name}')")
        rows = self.run_sql(db, "SELECT id FROM users WHERE name LIKE 'al%'")
        self.assertEqual(rows, [{"id": 1}, {"id": 3}])

    def test_count_star(self):
        db = make_db()
        self.run_sql(db, "INSERT INTO users VALUES (1, 'a', 1.0)")
        self.run_sql(db, "INSERT INTO users VALUES (2, 'b', 2.0)")
        self.run_sql(db, "INSERT INTO users VALUES (3, 'c', 3.0)")
        self.assertEqual(self.run_sql(db, "SELECT COUNT(*) FROM users"), [{"COUNT(*)": 3}])
        self.assertEqual(
            self.run_sql(db, "SELECT COUNT(*) FROM users WHERE id > 1"), [{"COUNT(*)": 2}]
        )

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


class DeleteExecutorTests(unittest.TestCase):
    def test_delete_matching_rows_returns_count(self):
        from tinysql.cli import demo_executor
        from tinysql.parser import parse

        ex = demo_executor()
        for sql in ("INSERT INTO users VALUES (1, 'al', 2.0)",
                    "INSERT INTO users VALUES (2, 'bo', 3.0)",
                    "INSERT INTO users VALUES (3, 'cy', 4.0)"):
            ex.run(parse(sql))
        self.assertEqual(ex.run(parse("DELETE FROM users WHERE id = 2")), 1)
        self.assertEqual(ex.run(parse("SELECT id FROM users")), [{"id": 1}, {"id": 3}])
        self.assertEqual(ex.run(parse("DELETE FROM users WHERE score > 100")), 0)


class UpdateExecutorTests(unittest.TestCase):
    def test_update_matching_rows(self):
        from tinysql.cli import demo_executor
        from tinysql.parser import parse

        ex = demo_executor()
        ex.run(parse("INSERT INTO users VALUES (1, 'al', 2.0)"))
        ex.run(parse("INSERT INTO users VALUES (2, 'bo', 3.0)"))
        self.assertEqual(ex.run(parse("UPDATE users SET name = 'zed' WHERE id = 2")), 1)
        self.assertEqual(ex.run(parse("SELECT name FROM users WHERE id = 2")), [{"name": "zed"}])
        with self.assertRaises(Exception):
            ex.run(parse("UPDATE users SET id = 9 WHERE id = 1"))


class DropTableExecutorTests(unittest.TestCase):
    def test_drop_removes_table(self):
        from tinysql.cli import demo_executor
        from tinysql.executor import ExecError
        from tinysql.parser import parse

        ex = demo_executor()
        ex.run(parse("DROP TABLE users"))
        self.assertNotIn("users", ex.tables)
        with self.assertRaises(ExecError):
            ex.run(parse("SELECT * FROM users"))
        with self.assertRaises(ExecError):
            ex.run(parse("DROP TABLE users"))


if __name__ == "__main__":
    unittest.main()
