"""A small in-memory B-tree mapping keys to values.

Each node holds at most ``2 * order - 1`` keys. A node that overflows is split
around its median key, which moves up into the parent. The root splits into a
new root, so the tree grows at the top and stays balanced.
"""

import json
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

    def delete(self, key: Any) -> bool:
        """Remove ``key``. Return True when it was present."""
        if key not in self:
            return False
        self._delete(self._root, key)
        if not self._root.keys and not self._root.leaf:
            self._root = self._root.children[0]
        self._size -= 1
        return True

    def items(self) -> Iterator[Tuple[Any, Any]]:
        """Yield (key, value) pairs in ascending key order."""
        yield from self._walk(self._root, None, None)

    def range(self, low: Any = None, high: Any = None) -> Iterator[Tuple[Any, Any]]:
        """Yield pairs with low <= key <= high in order. None means unbounded."""
        yield from self._walk(self._root, low, high)

    def save(self, path: str) -> None:
        """Write the order and all pairs to ``path`` as JSON.

        This is a snapshot, not page storage: keys and values must be
        JSON-serialisable, and the file is rewritten in full each time.
        """
        payload = {"order": self.order, "items": list(self.items())}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)

    @classmethod
    def load(cls, path: str) -> "BTree":
        """Rebuild a tree from a file written by ``save``."""
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
        tree = cls(order=payload["order"])
        for key, value in payload["items"]:
            tree.insert(key, value)
        return tree

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

    def _is_thin(self, node: _Node) -> bool:
        """True when a non-root node has fewer than ``order`` keys."""
        return len(node.keys) < self.order

    def _delete(self, node: _Node, key: Any) -> None:
        """Delete ``key`` from the subtree at ``node``, which has >= order keys
        unless it is the root. The key must be present in the subtree."""
        i = bisect_left(node.keys, key)
        found = i < len(node.keys) and node.keys[i] == key
        if found and node.leaf:
            del node.keys[i]
            del node.values[i]
            return
        if found:
            left, right = node.children[i], node.children[i + 1]
            if not self._is_thin(left):
                k, v = self._max_pair(left)
                node.keys[i], node.values[i] = k, v
                self._delete(left, k)
            elif not self._is_thin(right):
                k, v = self._min_pair(right)
                node.keys[i], node.values[i] = k, v
                self._delete(right, k)
            else:
                self._merge(node, i)
                self._delete(left, key)
            return
        child = node.children[i]
        if self._is_thin(child):
            self._fill(node, i)
            self._delete(node, key)  # the fill may have moved the key
            return
        self._delete(child, key)

    def _max_pair(self, node: _Node) -> Tuple[Any, Any]:
        while not node.leaf:
            node = node.children[-1]
        return node.keys[-1], node.values[-1]

    def _min_pair(self, node: _Node) -> Tuple[Any, Any]:
        while not node.leaf:
            node = node.children[0]
        return node.keys[0], node.values[0]

    def _fill(self, node: _Node, i: int) -> None:
        """Give thin child ``i`` one more key by borrowing or merging."""
        child = node.children[i]
        if i > 0 and not self._is_thin(node.children[i - 1]):
            left = node.children[i - 1]
            child.keys.insert(0, node.keys[i - 1])
            child.values.insert(0, node.values[i - 1])
            if not child.leaf:
                child.children.insert(0, left.children.pop())
            node.keys[i - 1] = left.keys.pop()
            node.values[i - 1] = left.values.pop()
        elif i < len(node.keys) and not self._is_thin(node.children[i + 1]):
            right = node.children[i + 1]
            child.keys.append(node.keys[i])
            child.values.append(node.values[i])
            if not child.leaf:
                child.children.append(right.children.pop(0))
            node.keys[i] = right.keys.pop(0)
            node.values[i] = right.values.pop(0)
        elif i < len(node.keys):
            self._merge(node, i)
        else:
            self._merge(node, i - 1)

    def _merge(self, node: _Node, i: int) -> None:
        """Fold separator i and child i+1 into child i."""
        left, right = node.children[i], node.children[i + 1]
        left.keys.append(node.keys.pop(i))
        left.values.append(node.values.pop(i))
        left.keys.extend(right.keys)
        left.values.extend(right.values)
        if not left.leaf:
            left.children.extend(right.children)
        del node.children[i + 1]

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
