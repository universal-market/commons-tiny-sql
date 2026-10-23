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

    def test_delete_missing_key(self):
        t = BTree()
        self.assertFalse(t.delete(1))
        t.insert(1, "a")
        self.assertFalse(t.delete(2))
        self.assertEqual(len(t), 1)

    def test_delete_all_in_random_order_match_dict(self):
        rng = random.Random(7)
        for order in (2, 3, 8):
            t = BTree(order=order)
            ref = {}
            keys = list(range(1500))
            rng.shuffle(keys)
            for k in keys:
                t.insert(k, k)
                ref[k] = k
            rng.shuffle(keys)
            for n, k in enumerate(keys):
                self.assertTrue(t.delete(k))
                del ref[k]
                if n % 150 == 0:
                    self.assertEqual(len(t), len(ref))
                    self.assertEqual(list(t.items()), sorted(ref.items()))
                    self.assert_balanced(t)
            self.assertEqual(len(t), 0)
            self.assertEqual(list(t.items()), [])
            self.assertTrue(t._root.leaf)

    def test_interleaved_insert_delete_match_dict(self):
        rng = random.Random(3)
        t = BTree(order=2)
        ref = {}
        for _ in range(5000):
            k = rng.randrange(300)
            if rng.random() < 0.5:
                t.insert(k, k)
                ref[k] = k
            else:
                self.assertEqual(t.delete(k), k in ref)
                ref.pop(k, None)
        self.assertEqual(len(t), len(ref))
        self.assertEqual(list(t.items()), sorted(ref.items()))
        self.assert_balanced(t)

    def test_root_shrinks_after_deletes(self):
        t = BTree(order=2)
        for k in range(50):
            t.insert(k, k)
        height_before = self.height(t._root)
        for k in range(45):
            t.delete(k)
        self.assertLess(self.height(t._root), height_before)
        self.assertEqual([k for k, _ in t.items()], list(range(45, 50)))

    def assert_balanced(self, t):
        def walk(node, lo, hi):
            self.assertTrue(all(lo is None or lo < k for k in node.keys))
            self.assertTrue(all(hi is None or k < hi for k in node.keys))
            self.assertLessEqual(len(node.keys), 2 * t.order - 1)
            if node is not t._root:
                self.assertGreaterEqual(len(node.keys), t.order - 1)
            if node.leaf:
                return {0}
            self.assertEqual(len(node.children), len(node.keys) + 1)
            depths = set()
            bounds = [lo] + node.keys + [hi]
            for i, c in enumerate(node.children):
                for d in walk(c, bounds[i], bounds[i + 1]):
                    depths.add(d + 1)
            return depths

        self.assertEqual(len(walk(t._root, None, None)), 1)

    def height(self, node):
        h = 0
        while not node.leaf:
            node = node.children[0]
            h += 1
        return h


if __name__ == "__main__":
    unittest.main()
