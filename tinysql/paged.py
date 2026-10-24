"""Save a BTree to a page file and load it back, one node per page.

Layout: page 1 holds the root. The other nodes are written before their
parent, so children get lower page ids. Page 0 is the Pager header.
Each save rewrites the whole file; nothing is updated in place yet.
"""

from .btree import BTree, _Node
from .pager import Pager, decode_node, encode_node

ROOT_PAGE = 1


def write_tree(tree: BTree, path: str) -> None:
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
