"""Page-based storage design for the B-tree (milestone 10, design only).

Status: design only. No reader or writer exists yet.

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

Node pages (all other pages):
    offset  size  field
    0       1     flags: 1 = leaf, 0 = internal
    1       2     key count n (unsigned, big-endian)
    3       ...   n entries, each:
                    2 bytes  key length k
                    k bytes  key, JSON-encoded UTF-8
                    2 bytes  value length v
                    v bytes  value, JSON-encoded UTF-8
    after entries, internal nodes only: n + 1 child page ids (4 bytes each)

A node must fit in one page. With order m, a node holds at most 2m - 1 keys.
Values larger than the remaining page space are an error in this milestone
(no overflow pages), so the design caps row size at roughly 4096 / (2m - 1)
bytes per entry minus the child-id overhead.

Open questions (to settle before code):
- Does the pager cache pages, or read and write each page on access?
- Is the free list needed now, or can deleted pages be leaked for this milestone?
"""

PAGE_SIZE = 4096
MAGIC = b"TINYSQL1"
