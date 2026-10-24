"""Page-based storage for the B-tree (milestone 10).

File layout
-----------
The file is a sequence of fixed-size pages of PAGE_SIZE = 4096 bytes.
Page n starts at byte offset n * PAGE_SIZE. Page ids are 0-based.

Page 0 is the header:
    offset  size  field
    0       8     magic, b"TINYSQL1"
    8       4     order (unsigned, big-endian)
    12      4     root page id
    16      4     page count (pages in use, including the header)

Node pages (all other pages): node encoding is not implemented yet.

Open questions (to settle before code):
- Does the pager cache pages, or read and write each page on access?
- Is the free list needed now, or can deleted pages be leaked for this milestone?
"""

import json
import os
import struct
from typing import Optional

PAGE_SIZE = 4096
MAGIC = b"TINYSQL1"
_HEADER = struct.Struct(">8sIII")


class Pager:
    """Reads and writes fixed-size pages of one file."""

    def __init__(self, path: str, order: Optional[int] = None):
        self.path = path
        if os.path.exists(path) and os.path.getsize(path) > 0:
            self._file = open(path, "r+b")
            self.order, self.root, self.page_count = self._read_header()
        else:
            if order is None:
                raise ValueError("order is required when creating a new file")
            self._file = open(path, "w+b")
            self.order = order
            self.root = 1
            self.page_count = 2
            self._write_header()
            self.write_page(1, bytes(PAGE_SIZE))

    def close(self) -> None:
        self._file.close()

    def __enter__(self) -> "Pager":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def read_page(self, page_id: int) -> bytes:
        if not 0 <= page_id < self.page_count:
            raise IndexError(f"page {page_id} out of range")
        self._file.seek(page_id * PAGE_SIZE)
        data = self._file.read(PAGE_SIZE)
        if len(data) != PAGE_SIZE:
            raise ValueError(f"page {page_id} is truncated")
        return data

    def write_page(self, page_id: int, data: bytes) -> None:
        if len(data) > PAGE_SIZE:
            raise ValueError(f"page data is {len(data)} bytes, limit is {PAGE_SIZE}")
        if page_id == self.page_count:
            self.page_count += 1
        elif not 0 <= page_id < self.page_count:
            raise IndexError(f"page {page_id} out of range")
        self._file.seek(page_id * PAGE_SIZE)
        self._file.write(data.ljust(PAGE_SIZE, b"\x00"))
        self._write_header()
        self._file.flush()

    def set_root(self, page_id: int) -> None:
        self.root = page_id
        self._write_header()
        self._file.flush()

    def _write_header(self) -> None:
        header = _HEADER.pack(MAGIC, self.order, self.root, self.page_count)
        self._file.seek(0)
        self._file.write(header.ljust(PAGE_SIZE, b"\x00"))

    def _read_header(self):
        self._file.seek(0)
        magic, order, root, page_count = _HEADER.unpack(
            self._file.read(_HEADER.size)
        )
        if magic != MAGIC:
            raise ValueError(f"{self.path} is not a tinysql page file")
        return order, root, page_count


_NODE_HEAD = struct.Struct(">BH")
_LEN = struct.Struct(">H")
_CHILD = struct.Struct(">I")


def encode_node(leaf: bool, keys: list, values: list, child_ids: list) -> bytes:
    """Encode one node as a page body (see the layout in the module docstring)."""
    parts = [_NODE_HEAD.pack(1 if leaf else 0, len(keys))]
    for key, value in zip(keys, values):
        for item in (json.dumps(key).encode("utf-8"), json.dumps(value).encode("utf-8")):
            parts.append(_LEN.pack(len(item)))
            parts.append(item)
    if not leaf:
        parts.extend(_CHILD.pack(child) for child in child_ids)
    data = b"".join(parts)
    if len(data) > PAGE_SIZE:
        raise ValueError(f"node is {len(data)} bytes, page limit is {PAGE_SIZE}")
    return data


def decode_node(data: bytes):
    """Return (leaf, keys, values, child_ids) from a page body."""
    flag, count = _NODE_HEAD.unpack_from(data, 0)
    pos = _NODE_HEAD.size
    keys, values = [], []
    for _ in range(count):
        pair = []
        for _ in range(2):
            (length,) = _LEN.unpack_from(data, pos)
            pos += _LEN.size
            pair.append(json.loads(data[pos:pos + length].decode("utf-8")))
            pos += length
        keys.append(pair[0])
        values.append(pair[1])
    child_ids = []
    if not flag:
        for _ in range(count + 1):
            (child,) = _CHILD.unpack_from(data, pos)
            child_ids.append(child)
            pos += _CHILD.size
    return bool(flag), keys, values, child_ids
