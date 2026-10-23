import unittest

from tinysql.table import Column, Table, TableError


def make_table():
    return Table(
        "users",
        [
            Column("id", int),
            Column("name", str, nullable=True),
            Column("score", float, nullable=True),
        ],
        primary_key="id",
    )


class TableTests(unittest.TestCase):
    def test_insert_and_get(self):
        t = make_table()
        t.insert({"id": 1, "name": "ann", "score": 2.5})
        self.assertEqual(t.get(1), {"id": 1, "name": "ann", "score": 2.5})
        self.assertIsNone(t.get(2))
        self.assertEqual(len(t), 1)

    def test_missing_nullable_columns_become_null(self):
        t = make_table()
        t.insert({"id": 7})
        self.assertEqual(t.get(7), {"id": 7, "name": None, "score": None})

    def test_scan_is_in_primary_key_order(self):
        t = make_table()
        for k in (5, 1, 3):
            t.insert({"id": k})
        self.assertEqual([r["id"] for r in t.scan()], [1, 3, 5])

    def test_get_and_scan_return_copies(self):
        t = make_table()
        t.insert({"id": 1, "name": "ann"})
        t.get(1)["name"] = "changed"
        next(t.scan())["name"] = "changed"
        self.assertEqual(t.get(1)["name"], "ann")

    def test_duplicate_primary_key_rejected(self):
        t = make_table()
        t.insert({"id": 1})
        with self.assertRaisesRegex(TableError, "duplicate primary key"):
            t.insert({"id": 1, "name": "again"})
        self.assertEqual(len(t), 1)

    def test_null_primary_key_rejected(self):
        with self.assertRaisesRegex(TableError, "may not be NULL"):
            make_table().insert({"name": "no id"})

    def test_null_in_non_nullable_column_rejected(self):
        t = Table("t", [Column("id", int), Column("v", str)], primary_key="id")
        with self.assertRaisesRegex(TableError, "may not be NULL"):
            t.insert({"id": 1})

    def test_wrong_type_rejected(self):
        t = make_table()
        with self.assertRaisesRegex(TableError, "expects int"):
            t.insert({"id": "1"})
        with self.assertRaisesRegex(TableError, "expects str"):
            t.insert({"id": 1, "name": 5})

    def test_bool_is_not_accepted_as_int(self):
        with self.assertRaises(TableError):
            make_table().insert({"id": True})

    def test_float_column_accepts_only_float_here(self):
        # Python int is not coerced; the caller must pass 3.0.
        with self.assertRaises(TableError):
            make_table().insert({"id": 1, "score": 3})

    def test_unknown_column_rejected(self):
        with self.assertRaisesRegex(TableError, "unknown column"):
            make_table().insert({"id": 1, "bogus": 1})

    def test_schema_errors(self):
        with self.assertRaisesRegex(TableError, "duplicate column"):
            Table("t", [Column("id", int), Column("id", int)], primary_key="id")
        with self.assertRaisesRegex(TableError, "is not a column"):
            Table("t", [Column("id", int)], primary_key="nope")


if __name__ == "__main__":
    unittest.main()
