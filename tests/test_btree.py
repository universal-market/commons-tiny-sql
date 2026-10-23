import random
import unittest

from tinysql.btree import BTree


class BTreeTests(unittest.TestCase):
    def test_empty_tree(self):
        t = BTree()
        self.assertEqual(len(t), 0)
        self.assertIsNone(t.get(1))
        self.assertNotIn(1, t)
        self.assertEqual(list(t.items()), [])

    def test_insert_and_get(self):
        t = BTree()
        t.insert(2, "b")
        t.insert(1, "a")
        self.assertEqual(t.get(1), "a")
        self.assertEqual(t.get(2), "b")
        self.assertEqual(t.get(3, "missing"), "missing")
        self.assertEqual(len(t), 2)

    def test_overwrite_does_not_grow(self):
        t = BTree()
        t.insert(1, "a")
        t.insert(1, "z")
        self.assertEqual(t.get(1), "z")
        self.assertEqual(len(t), 1)

    def test_order_validation(self):
        with self.assertRaises(ValueError):
            BTree(order=1)

    def test_many_keys_random_order_match_dict(self):
        rng = random.Random(42)
        keys = list(range(2000))
        rng.shuffle(keys)
        for order in (2, 3, 8):
            t = BTree(order=order)
            ref = {}
            for k in keys:
                t.insert(k, k * 10)
                ref[k] = k * 10
            self.assertEqual(len(t), len(ref))
            self.assertEqual(list(t.items()), sorted(ref.items()))
            for k in range(-5, 2005):
                self.assertEqual(t.get(k), ref.get(k))

    def test_overwrites_across_splits(self):
        t = BTree(order=2)
        for k in range(100):
            t.insert(k, 0)
        for k in range(0, 100, 3):
            t.insert(k, 1)
        self.assertEqual(len(t), 100)
        for k in range(100):
            self.assertEqual(t.get(k), 1 if k % 3 == 0 else 0)

    def test_range_scan(self):
        t = BTree(order=2)
        for k in range(0, 50):
            t.insert(k, str(k))
        got = [k for k, _ in t.range(10, 20)]
        self.assertEqual(got, list(range(10, 21)))
        self.assertEqual([k for k, _ in t.range(None, 2)], [0, 1, 2])
        self.assertEqual([k for k, _ in t.range(47, None)], [47, 48, 49])
        self.assertEqual(list(t.range(60, 70)), [])

    def test_string_keys(self):
        t = BTree(order=2)
        for w in ["pear", "apple", "fig", "kiwi", "banana"]:
            t.insert(w, len(w))
        self.assertEqual([k for k, _ in t.items()],
                         ["apple", "banana", "fig", "kiwi", "pear"])
        self.assertEqual(t.get("fig"), 3)

    def test_leaves_are_at_same_depth(self):
        t = BTree(order=2)
        for k in range(500):
            t.insert(k, k)

        def depths(node, d):
            if node.leaf:
                return {d}
            out = set()
            for c in node.children:
                out |= depths(c, d + 1)
            return out

        self.assertEqual(len(depths(t._root, 0)), 1)
        self.assertEqual(len(t._root.keys) <= 2 * t.order - 1, True)


if __name__ == "__main__":
    unittest.main()
