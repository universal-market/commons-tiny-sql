"""Save a BTree to a page file and load it back, one node per page.

Layout: page 1 holds the root. The other nodes are written before their
parent, so children get lower page ids. Page 0 is the Pager header.
A save into an existing file of the same order updates it in place: a
page whose bytes are unchanged is not written, and pages past the new end
of the tree are truncated.
"""

import json
import os

from .btree import BTree, _Node
from .pager import PAGE_SIZE, Pager, decode_node, encode_node

ROOT_PAGE = 1


def write_tree(tree: BTree, path: str) -> None:
    if os.path.exists(path) and _file_order(path) != tree.order:
        os.remove(path)  # a different order cannot be updated in place
    pages = []
    _collect(tree._root, ROOT_PAGE, [ROOT_PAGE + 1], pages)
    with Pager(path, order=tree.order) as pager:
        for page_id, data in sorted(pages):  # ids are dense, so this is in order
            if page_id < pager.page_count and pager.read_page(page_id) == data.ljust(PAGE_SIZE, b"\0"):
                continue
            pager.write_page(page_id, data)
        if pager.page_count > len(pages) + 1:
            pager.truncate_pages(len(pages) + 1)


def _file_order(path: str) -> int:
    with Pager(path) as pager:
        return pager.order


def read_tree(path: str) -> BTree:
    with Pager(path) as pager:
        root = _read_node(pager, pager.root)
        tree = BTree(order=pager.order)
    tree._root = root
    tree._size = sum(1 for _ in root_items(root))
    return tree


def root_items(node: _Node):
    for i, key in enumerate(node.keys):
        if not node.leaf:
            yield from root_items(node.children[i])
        yield key, node.values[i]
    if not node.leaf:
        yield from root_items(node.children[-1])


def _collect(node: _Node, page_id: int, next_free: list, out: list) -> None:
    """Assign page ids in pre-order, so an unchanged tree gets the same ids and bytes."""
    child_ids = []
    if not node.leaf:
        for _ in node.children:
            child_ids.append(next_free[0])
            next_free[0] += 1
    out.append((page_id, encode_node(node.leaf, node.keys, node.values, child_ids)))
    if not node.leaf:
        for child_id, child in zip(child_ids, node.children):
            _collect(child, child_id, next_free, out)


def _write_subtree(pager: Pager, node: _Node) -> int:
    """Append a subtree's pages to the end of the file and return its root page id."""
    root_id = pager.page_count
    pages = []
    _collect(node, root_id, [root_id + 1], pages)
    for page_id, data in pages:
        pager.write_page(page_id, data)
    return root_id


def _read_node(pager: Pager, page_id: int) -> _Node:
    leaf, keys, values, child_ids = decode_node(pager.read_page(page_id))
    node = _Node(leaf=leaf)
    node.keys, node.values = keys, values
    if not leaf:
        node.children = [_read_node(pager, c) for c in child_ids]
    return node


CATALOG_PAGE = 1
_TYPE_NAMES = {int: "int", float: "float", str: "str", bool: "bool"}
_TYPES = {name: t for t, name in _TYPE_NAMES.items()}


def write_database(tables: dict, path: str) -> None:
    """Write several tables to one page file: a JSON catalog on page 1, then each table's nodes."""
    if os.path.exists(path):
        os.remove(path)
    with Pager(path, order=8) as pager:
        catalog = {}
        for name, table in tables.items():
            root = _write_subtree(pager, table._rows._root)
            catalog[name] = {
                "root": root,
                "primary_key": table.primary_key,
                "columns": [
                    {"name": c.name, "type": _TYPE_NAMES[c.type], "nullable": c.nullable}
                    for c in table.columns
                ],
            }
        pager.write_page(CATALOG_PAGE, json.dumps(catalog).encode("utf-8"))


def read_database(path: str) -> dict:
    from .table import Column, Table

    with Pager(path) as pager:
        catalog = json.loads(pager.read_page(CATALOG_PAGE).rstrip(b"\x00"))
        tables = {}
        for name, meta in catalog.items():
            columns = [
                Column(c["name"], _TYPES[c["type"]], c["nullable"]) for c in meta["columns"]
            ]
            table = Table(name, columns, meta["primary_key"])
            root = _read_node(pager, meta["root"])
            tree = BTree(order=pager.order)
            tree._root = root
            tree._size = sum(1 for _ in root_items(root))
            for _, row in tree.items():
                table.insert(row)
            tables[name] = table
    return tables
