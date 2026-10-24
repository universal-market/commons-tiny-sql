import os
import random
import tempfile
import unittest

from tinysql.btree import BTree
from tinysql.paged import read_tree, write_tree


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


if __name__ == "__main__":
    unittest.main()
