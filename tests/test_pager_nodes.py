import unittest

from tinysql.pager import decode_node, encode_node


class NodeCodecTest(unittest.TestCase):
    def test_leaf_round_trip(self):
        data = encode_node(True, ["a", 2], ["x", {"n": 1}], [])
        self.assertEqual(decode_node(data), (True, ["a", 2], ["x", {"n": 1}], []))

    def test_internal_round_trip_keeps_child_ids(self):
        data = encode_node(False, ["m"], ["v"], [4, 7])
        self.assertEqual(decode_node(data), (False, ["m"], ["v"], [4, 7]))

    def test_oversized_node_is_rejected(self):
        with self.assertRaises(ValueError):
            encode_node(True, ["k"], ["x" * 5000], [])


if __name__ == "__main__":
    unittest.main()
