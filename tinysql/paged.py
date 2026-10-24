"""Save a BTree to a page file and load it back, one node per page.

Layout: page 1 holds the root. The other nodes are written before their
parent, so children get lower page ids. Page 0 is the Pager header.
Each save rewrites the whole file; nothing is updated in place yet.
"""

import json
import os

from .btree import BTree, _Node
from .pager import Pager, decode_node, encode_node

ROOT_PAGE = 1


def write_tree(tree: BTree, path: str) -> None:
    if os.path.exists(path):
        os.remove(path)  # rewrite from scratch so old pages do not pile up
    with Pager(path, order=tree.order) as pager:
        _write_node(pager, tree._root, ROOT_PAGE)


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


def _write_node(pager: Pager, node: _Node, page_id: int = None) -> int:
    child_ids = [] if node.leaf else [_write_node(pager, c) for c in node.children]
    if page_id is None:
        page_id = pager.page_count
    pager.write_page(page_id, encode_node(node.leaf, node.keys, node.values, child_ids))
    return page_id


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
            root = _write_node(pager, table._rows._root)
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
