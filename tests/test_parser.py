import unittest

from tinysql.parser import (
    And, Column, Compare, Insert, Literal, Not, Or, ParseError, Select, parse,
)
from tinysql.tokenizer import TokenizeError


class SelectTests(unittest.TestCase):
    def test_star(self):
        self.assertEqual(parse("SELECT * FROM t"), Select(None, "t"))

    def test_column_list(self):
        self.assertEqual(parse("select a, b from t"), Select(("a", "b"), "t"))

    def test_where_comparison(self):
        stmt = parse("SELECT a FROM t WHERE a >= 10")
        self.assertEqual(stmt.where, Compare(">=", Column("a"), Literal(10)))

    def test_and_binds_tighter_than_or(self):
        stmt = parse("SELECT * FROM t WHERE a = 1 OR b = 2 AND c = 3")
        self.assertIsInstance(stmt.where, Or)
        self.assertIsInstance(stmt.where.right, And)

    def test_parentheses_override_precedence(self):
        stmt = parse("SELECT * FROM t WHERE (a = 1 OR b = 2) AND c = 3")
        self.assertIsInstance(stmt.where, And)
        self.assertIsInstance(stmt.where.left, Or)

    def test_not(self):
        stmt = parse("SELECT * FROM t WHERE NOT a = 'x'")
        self.assertEqual(stmt.where, Not(Compare("=", Column("a"), Literal("x"))))

    def test_null_literal_and_not_equal(self):
        stmt = parse("SELECT * FROM t WHERE a <> NULL")
        self.assertEqual(stmt.where, Compare("<>", Column("a"), Literal(None)))

    def test_order_and_limit(self):
        stmt = parse("SELECT * FROM t ORDER BY a LIMIT 5;")
        self.assertEqual((stmt.order_by, stmt.limit), ("a", 5))

    def test_limit_must_be_integer(self):
        with self.assertRaises(ParseError):
            parse("SELECT * FROM t LIMIT 2.5")

    def test_missing_from_raises(self):
        with self.assertRaises(ParseError):
            parse("SELECT a t")

    def test_trailing_garbage_raises(self):
        with self.assertRaises(ParseError):
            parse("SELECT * FROM t extra")


class InsertTests(unittest.TestCase):
    def test_with_column_list(self):
        self.assertEqual(
            parse("INSERT INTO t (a, b) VALUES (1, 'x')"),
            Insert("t", ("a", "b"), (1, "x")),
        )

    def test_without_column_list(self):
        self.assertEqual(
            parse("insert into t values (2.5, NULL);"),
            Insert("t", None, (2.5, None)),
        )

    def test_count_mismatch_raises(self):
        with self.assertRaises(ParseError):
            parse("INSERT INTO t (a, b) VALUES (1)")

    def test_expression_in_values_is_rejected(self):
        with self.assertRaises(ParseError):
            parse("INSERT INTO t VALUES (a)")


class ErrorTests(unittest.TestCase):
    def test_unknown_statement(self):
        with self.assertRaises(ParseError):
            parse("DELETE FROM t")

    def test_empty_input(self):
        with self.assertRaises(ParseError):
            parse("")

    def test_tokenizer_errors_propagate(self):
        with self.assertRaises(TokenizeError):
            parse("SELECT @ FROM t")


if __name__ == "__main__":
    unittest.main()
