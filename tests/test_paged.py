import os
import random
import tempfile
import unittest

from tinysql.btree import BTree
from tinysql.executor import Executor
from tinysql.parser import parse
from tinysql.table import Column, Table
from tinysql.paged import read_database, read_tree, write_database, write_tree


class PagedTreeTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "tree.pages")

    def tearDown(self):
        self.dir.cleanup()

    def test_empty_tree_round_trip(self):
        write_tree(BTree(order=2), self.path)
        loaded = read_tree(self.path)
        self.assertEqual(len(loaded), 0)
        self.assertEqual(loaded.order, 2)

    def test_many_keys_round_trip(self):
        tree = BTree(order=2)
        keys = list(range(200))
        random.Random(1).shuffle(keys)
        for k in keys:
            tree.insert(k, f"row{k}")
        write_tree(tree, self.path)
        loaded = read_tree(self.path)
        self.assertEqual(len(loaded), 200)
        self.assertEqual(list(loaded.items()), list(tree.items()))
        self.assertEqual(loaded.get(137), "row137")

    def test_loaded_tree_still_accepts_changes(self):
        tree = BTree(order=3)
        for k in range(30):
            tree.insert(k, k)
        write_tree(tree, self.path)
        loaded = read_tree(self.path)
        loaded.delete(10)
        loaded.insert(100, 100)
        self.assertEqual(len(loaded), 30)
        self.assertNotIn(10, loaded)
        self.assertEqual(loaded.get(100), 100)


    def test_split_tree_persisted_after_deletes_reloads(self):
        tree = BTree(order=2)
        for k in range(60):
            tree.insert(k, f"row{k}")
        for k in range(0, 60, 3):
            tree.delete(k)
        write_tree(tree, self.path)
        loaded = read_tree(self.path)
        expected = [(k, f"row{k}") for k in range(60) if k % 3]
        self.assertEqual(list(loaded.items()), expected)
        self.assertEqual(len(loaded), len(expected))

    def test_resave_updates_file_in_place(self):
        tree = BTree(order=2)
        for k in range(120):
            tree.insert(k, k)
        write_tree(tree, self.path)
        before = open(self.path, "rb").read()
        write_tree(tree, self.path)
        self.assertEqual(open(self.path, "rb").read(), before)
        for k in range(0, 120, 2):
            tree.delete(k)
        write_tree(tree, self.path)
        self.assertLess(os.path.getsize(self.path), len(before))
        self.assertEqual(list(read_tree(self.path).items()), list(tree.items()))

    def test_database_survives_delete_and_update(self):
        users = Table("users", [Column("id", int), Column("name", str)], primary_key="id")
        db = Executor({"users": users})
        for i in range(50):
            db.run(parse(f"INSERT INTO users VALUES ({i}, 'n{i}')"))
        db.run(parse("DELETE FROM users WHERE id > 39"))
        db.run(parse("UPDATE users SET name = 'zz' WHERE id = 3"))
        write_database(db.tables, self.path)
        rows = list(read_database(self.path)["users"]._rows.items())
        self.assertEqual(len(rows), 40)
        self.assertEqual(rows[3], (3, {"id": 3, "name": "zz"}))

class PagedDatabaseTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "db.pages")

    def tearDown(self):
        self.dir.cleanup()

    def test_two_tables_round_trip_with_schema(self):
        from tinysql.paged import read_database, write_database
        from tinysql.table import Column, Table

        users = Table("users", [Column("id", int), Column("name", str, nullable=True)], "id")
        users.insert({"id": 1, "name": "al"})
        orders = Table("orders", [Column("oid", int)], "oid")
        orders.insert({"oid": 7})
        write_database({"users": users, "orders": orders}, self.path)

        loaded = read_database(self.path)
        self.assertEqual(sorted(loaded), ["orders", "users"])
        self.assertEqual(loaded["users"].get(1), {"id": 1, "name": "al"})
        self.assertEqual(loaded["users"].primary_key, "id")
        self.assertEqual([c.name for c in loaded["orders"].columns], ["oid"])


if __name__ == "__main__":
    unittest.main()
