import unittest

from tinysql.parser import (
    And, Column, ColumnDef, Compare, DropTable, InList, Insert, Like, IsNull, Literal, Not, Or, ParseError, Select, parse,
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
        self.assertEqual((stmt.order_by, stmt.limit), (("a",), 5))

    def test_limit_with_offset(self):
        stmt = parse("SELECT * FROM t LIMIT 2 OFFSET 3")
        self.assertEqual((stmt.limit, stmt.offset), (2, 3))

    def test_insert_multiple_rows(self):
        stmt = parse("INSERT INTO t (a, b) VALUES (1, 'x'), (2, 'y')")
        self.assertEqual(stmt.rows, ((1, "x"), (2, "y")))

    def test_where_is_null(self):
        stmt = parse("SELECT * FROM t WHERE a IS NULL")
        self.assertEqual(stmt.where, IsNull(Column("a")))

    def test_where_is_not_null(self):
        stmt = parse("SELECT * FROM t WHERE a IS NOT NULL")
        self.assertEqual(stmt.where, Not(IsNull(Column("a"))))

    def test_where_in_list(self):
        stmt = parse("SELECT * FROM t WHERE a IN (1, 2)")
        self.assertEqual(stmt.where, InList(Column("a"), (Literal(1), Literal(2))))

    def test_select_distinct(self):
        stmt = parse("SELECT DISTINCT a FROM t")
        self.assertTrue(stmt.distinct)
        self.assertEqual(stmt.columns, ("a",))

    def test_where_between(self):
        stmt = parse("SELECT * FROM t WHERE a BETWEEN 1 AND 3")
        self.assertEqual(
            stmt.where,
            And(Compare(">=", Column("a"), Literal(1)), Compare("<=", Column("a"), Literal(3))),
        )

    def test_where_not_in_list(self):
        stmt = parse("SELECT * FROM t WHERE a NOT IN (1, 2)")
        self.assertEqual(stmt.where, Not(InList(Column("a"), (Literal(1), Literal(2)))))

    def test_order_by_explicit_asc(self):
        stmt = parse("SELECT * FROM t ORDER BY a ASC")
        self.assertEqual((stmt.order_by, stmt.order_desc), (("a",), False))

    def test_where_not_between(self):
        stmt = parse("SELECT * FROM t WHERE a NOT BETWEEN 1 AND 3")
        self.assertEqual(
            stmt.where,
            Not(And(Compare(">=", Column("a"), Literal(1)), Compare("<=", Column("a"), Literal(3)))),
        )

    def test_where_like(self):
        stmt = parse("SELECT * FROM t WHERE a LIKE 'ab%'")
        self.assertEqual(stmt.where, Like(Column("a"), Literal("ab%")))

    def test_where_not_like(self):
        stmt = parse("SELECT * FROM t WHERE a NOT LIKE 'ab%'")
        self.assertEqual(stmt.where, Not(Like(Column("a"), Literal("ab%"))))

    def test_count_star(self):
        stmt = parse("SELECT COUNT(*) FROM t")
        self.assertEqual(stmt.columns, ("COUNT(*)",))

    def test_count_column(self):
        stmt = parse("SELECT COUNT(a) FROM t")
        self.assertEqual(stmt.columns, (("COUNT", "a"),))

    def test_sum_column(self):
        stmt = parse("SELECT SUM(a) FROM t")
        self.assertEqual(stmt.columns, (("SUM", "a"),))

    def test_max_column(self):
        stmt = parse("SELECT MAX(a) FROM t")
        self.assertEqual(stmt.columns, (("MAX", "a"),))

    def test_order_by_desc(self):
        stmt = parse("SELECT * FROM t ORDER BY a DESC")
        self.assertEqual((stmt.order_by, stmt.order_desc), (("a",), True))

    def test_order_by_default_is_ascending(self):
        stmt = parse("SELECT * FROM t ORDER BY a")
        self.assertFalse(stmt.order_desc)

    def test_drop_table(self):
        self.assertEqual(parse("DROP TABLE t"), DropTable("t"))

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
            Insert("t", ("a", "b"), ((1, "x"),)),
        )

    def test_without_column_list(self):
        self.assertEqual(
            parse("insert into t values (2.5, NULL);"),
            Insert("t", None, ((2.5, None),)),
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


class CreateTableTests(unittest.TestCase):
    def test_columns_and_primary_key(self):
        stmt = parse("CREATE TABLE users (id INT, name TEXT NULL, PRIMARY KEY (id))")
        self.assertEqual(stmt.table, "users")
        self.assertEqual(stmt.primary_key, "id")
        self.assertEqual(stmt.columns, (
            ColumnDef("id", "INT", False),
            ColumnDef("name", "TEXT", True),
        ))

    def test_unknown_type_is_rejected(self):
        with self.assertRaises(ParseError):
            parse("CREATE TABLE t (id FOO, PRIMARY KEY (id))")

    def test_primary_key_must_name_a_column(self):
        with self.assertRaises(ParseError):
            parse("CREATE TABLE t (id INT, PRIMARY KEY (x))")

    def test_duplicate_column_is_rejected(self):
        with self.assertRaises(ParseError):
            parse("CREATE TABLE t (id INT, id TEXT, PRIMARY KEY (id))")


class DeleteTests(unittest.TestCase):
    def test_delete_with_where(self):
        from tinysql.parser import Delete

        self.assertEqual(
            parse("DELETE FROM t WHERE id = 3"),
            Delete("t", Compare("=", Column("id"), Literal(3))),
        )

    def test_delete_without_where_is_rejected(self):
        with self.assertRaises(ParseError):
            parse("DELETE t")


class UpdateTests(unittest.TestCase):
    def test_update_set_with_where(self):
        from tinysql.parser import Update

        self.assertEqual(
            parse("UPDATE t SET name = 'bo' WHERE id = 3"),
            Update("t", "name", Literal("bo"), Compare("=", Column("id"), Literal(3))),
        )


if __name__ == "__main__":
    unittest.main()
