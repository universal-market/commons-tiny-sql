import unittest

from tinysql.cli import demo_executor, run_line


class CliTests(unittest.TestCase):
    def test_insert_and_select_print_a_table(self):
        db = demo_executor()
        self.assertEqual(run_line(db, "INSERT INTO users VALUES (1, 'al', 2.0)"), "1 row(s) inserted")
        out = run_line(db, "SELECT id, name FROM users")
        self.assertEqual(out.splitlines()[0], "id | name")
        self.assertEqual(out.splitlines()[-1], "(1 row)")

    def test_errors_are_printed_not_raised(self):
        db = demo_executor()
        self.assertEqual(run_line(db, "SELECT nope FROM users"), "error: no such column 'nope'")
        self.assertTrue(run_line(db, "SELEC * FROM users").startswith("error: "))

    def test_ddl_does_not_report_rows(self):
        db = demo_executor()
        self.assertEqual(run_line(db, "CREATE TABLE t (k INT, PRIMARY KEY (k))"), "ok")
        self.assertEqual(run_line(db, "DROP TABLE t"), "ok")

    def test_empty_result(self):
        self.assertEqual(run_line(demo_executor(), "SELECT * FROM users"), "(0 rows)")

    def test_db_file_keeps_rows_between_runs(self):
        import io
        import os
        import tempfile

        from tinysql.cli import main

        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "users.pages")
            main(io.StringIO("INSERT INTO users VALUES (1, 'al', 2.0)\n"), io.StringIO(), path)
            out = io.StringIO()
            main(io.StringIO("SELECT name FROM users\n"), out, path)
            self.assertEqual(out.getvalue().splitlines()[-1], "(1 row)")

    def test_create_table_survives_restart(self):
        import io
        import os
        import tempfile

        from tinysql.cli import main

        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "db.pages")
            main(io.StringIO("CREATE TABLE t (k INT, PRIMARY KEY (k))\nINSERT INTO t VALUES (5)\n"), io.StringIO(), path)
            out = io.StringIO()
            main(io.StringIO("SELECT k FROM t\n"), out, path)
            self.assertEqual(out.getvalue().splitlines()[-1], "(1 row)")


if __name__ == "__main__":
    unittest.main()
