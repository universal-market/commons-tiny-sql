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

    def test_empty_result(self):
        self.assertEqual(run_line(demo_executor(), "SELECT * FROM users"), "(0 rows)")


if __name__ == "__main__":
    unittest.main()
