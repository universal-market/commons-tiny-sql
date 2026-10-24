import os
import tempfile
import unittest

from tinysql.pager import PAGE_SIZE, Pager


class PagerTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "db.pages")

    def tearDown(self):
        self.dir.cleanup()

    def test_new_file_has_header_and_root_page(self):
        with Pager(self.path, order=3) as p:
            self.assertEqual(p.order, 3)
            self.assertEqual(p.root, 1)
            self.assertEqual(p.page_count, 2)
        self.assertEqual(os.path.getsize(self.path), 2 * PAGE_SIZE)

    def test_write_then_read_page(self):
        with Pager(self.path, order=2) as p:
            p.write_page(2, b"hello")
            self.assertEqual(p.read_page(2)[:5], b"hello")
            self.assertEqual(p.page_count, 3)

    def test_reopen_keeps_header_and_pages(self):
        with Pager(self.path, order=4) as p:
            p.write_page(2, b"node")
            p.set_root(2)
        with Pager(self.path) as p:
            self.assertEqual(p.order, 4)
            self.assertEqual(p.root, 2)
            self.assertEqual(p.read_page(2)[:4], b"node")

    def test_oversized_page_is_rejected(self):
        with Pager(self.path, order=2) as p:
            with self.assertRaises(ValueError):
                p.write_page(1, bytes(PAGE_SIZE + 1))

    def test_missing_page_is_rejected(self):
        with Pager(self.path, order=2) as p:
            with self.assertRaises(IndexError):
                p.read_page(5)

    def test_foreign_file_is_rejected(self):
        with open(self.path, "wb") as f:
            f.write(b"x" * PAGE_SIZE)
        with self.assertRaises(ValueError):
            Pager(self.path)


if __name__ == "__main__":
    unittest.main()
