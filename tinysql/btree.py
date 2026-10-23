"""A small in-memory B-tree mapping keys to values.

Each node holds at most ``2 * order - 1`` keys. A node that overflows is split
around its median key, which moves up into the parent. The root splits into a
new root, so the tree grows at the top and stays balanced.
"""

from bisect import bisect_left, bisect_right
from typing import Any, Iterator, List, Optional, Tuple


class _Node:
    __slots__ = ("keys", "values", "children")

    def __init__(self, leaf: bool = True):
        self.keys: List[Any] = []
        self.values: List[Any] = []
        self.children: Optional[List["_Node"]] = None if leaf else []

    @property
    def leaf(self) -> bool:
        return self.children is None


class BTree:
    def __init__(self, order: int = 2):
        if order < 2:
            raise ValueError("order must be at least 2")
        self.order = order
        self._root = _Node()
        self._size = 0

    def __len__(self) -> int:
        return self._size

    def get(self, key: Any, default: Any = None) -> Any:
        node = self._root
        while True:
            i = bisect_left(node.keys, key)
            if i < len(node.keys) and node.keys[i] == key:
                return node.values[i]
            if node.leaf:
                return default
            node = node.children[i]

    def __contains__(self, key: Any) -> bool:
        sentinel = object()
        return self.get(key, sentinel) is not sentinel

    def insert(self, key: Any, value: Any) -> None:
        """Insert or overwrite ``key``."""
        if self._is_full(self._root):
            new_root = _Node(leaf=False)
            new_root.children.append(self._root)
            self._split_child(new_root, 0)
            self._root = new_root
        if self._insert_nonfull(self._root, key, value):
            self._size += 1

    def items(self) -> Iterator[Tuple[Any, Any]]:
        """Yield (key, value) pairs in ascending key order."""
        yield from self._walk(self._root, None, None)

    def range(self, low: Any = None, high: Any = None) -> Iterator[Tuple[Any, Any]]:
        """Yield pairs with low <= key <= high in order. None means unbounded."""
        yield from self._walk(self._root, low, high)

    # internals

    def _is_full(self, node: _Node) -> bool:
        return len(node.keys) == 2 * self.order - 1

    def _split_child(self, parent: _Node, i: int) -> None:
        child = parent.children[i]
        mid = self.order - 1
        sibling = _Node(leaf=child.leaf)
        sibling.keys = child.keys[mid + 1:]
        sibling.values = child.values[mid + 1:]
        if not child.leaf:
            sibling.children = child.children[mid + 1:]
            child.children = child.children[:mid + 1]
        parent.keys.insert(i, child.keys[mid])
        parent.values.insert(i, child.values[mid])
        parent.children.insert(i + 1, sibling)
        child.keys = child.keys[:mid]
        child.values = child.values[:mid]

    def _insert_nonfull(self, node: _Node, key: Any, value: Any) -> bool:
        """Return True when a new key was added, False when one was overwritten."""
        while True:
            i = bisect_left(node.keys, key)
            if i < len(node.keys) and node.keys[i] == key:
                node.values[i] = value
                return False
            if node.leaf:
                node.keys.insert(i, key)
                node.values.insert(i, value)
                return True
            if self._is_full(node.children[i]):
                self._split_child(node, i)
                if key == node.keys[i]:
                    node.values[i] = value
                    return False
                if key > node.keys[i]:
                    i += 1
            node = node.children[i]

    def _walk(self, node: _Node, low: Any, high: Any) -> Iterator[Tuple[Any, Any]]:
        start = 0 if low is None else bisect_left(node.keys, low)
        stop = len(node.keys) if high is None else bisect_right(node.keys, high)
        if node.leaf:
            for i in range(start, stop):
                yield node.keys[i], node.values[i]
            return
        for i in range(start, stop + 1):
            yield from self._walk(node.children[i], low, high)
            if i < stop:
                yield node.keys[i], node.values[i]
