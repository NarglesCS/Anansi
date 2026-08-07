# Example: swapping in a custom backend

Anansi is layered so that the only file you need to replace to serve **your**
data is the backend module:

```
data.py    ← swappable backend (this guide)
schema.py  ← SDL + resolvers (edit to match your domain)
engine.py  ← guards + execution (no changes needed)
server.py  ← MCP wiring (no changes needed)
```

The demo ships with an in-memory blog dataset. Below is a minimal "core" you
can copy to back the same schema with SQLite instead.

## 1. Replace the data layer

Create `my_backend.py` implementing the same function surface as
`anansi.data`:

```python
"""SQLite-backed data layer with the same surface as anansi.data."""

from __future__ import annotations

import sqlite3
from typing import Any

Row = dict[str, Any]

_conn = sqlite3.connect("blog.db", check_same_thread=False)
_conn.row_factory = sqlite3.Row


def _rows(sql: str, params: tuple = ()) -> list[Row]:
    return [dict(r) for r in _conn.execute(sql, params).fetchall()]


def _one(sql: str, params: tuple) -> Row | None:
    rows = _rows(sql, params)
    return rows[0] if rows else None


def user_by_id(uid: str) -> Row | None:
    return _one("SELECT * FROM users WHERE id = ?", (uid,))


def post_by_id(pid: str) -> Row | None:
    return _one("SELECT * FROM posts WHERE id = ?", (pid,))


def posts_by_author(uid: str) -> list[Row]:
    return _rows("SELECT * FROM posts WHERE authorId = ?", (uid,))


def comments_for_post(pid: str) -> list[Row]:
    return _rows("SELECT * FROM comments WHERE postId = ?", (pid,))


def create_post(author_id: str, title: str, body: str) -> Row:
    cur = _conn.execute(
        "INSERT INTO posts (authorId, title, body, published) VALUES (?, ?, ?, 0)",
        (author_id, title, body),
    )
    _conn.commit()
    return post_by_id(str(cur.lastrowid))  # type: ignore[return-value]
```

Notes:

- **Always use parameterized queries** (`?` placeholders) — never format user
  input into SQL strings.
- Resolvers receive plain dicts, so any backend that returns
  `dict[str, Any]` rows works: SQLAlchemy, an internal REST API, a gRPC
  service, etc.

## 2. Point the schema at your backend

In `schema.py`, change the import:

```python
from . import data          # before
import my_backend as data   # after
```

If your domain differs from the blog demo, edit the `SDL` string and the
resolver functions in `schema.py` to match. Keep the doc strings in the SDL —
they are what the model reads to understand your API.

## 3. Nothing else changes

`engine.py` (mutation gating, depth limits, validation) and `server.py`
(MCP tools/resources) are schema-agnostic. Run as usual:

```
python -m anansi.server
```

## Tips for real backends

- **Filter in the backend, not in resolvers.** Push `role`, `published`, and
  `limit` arguments down into your queries instead of fetching everything and
  slicing in Python.
- **Watch for N+1.** Nested selections (`posts { author { … } }`) call
  relation resolvers per row. For SQL backends, add a small per-request cache
  or batch lookups (DataLoader pattern) once datasets grow.
- **Keep mutations gated.** `ANANSI_ALLOW_MUTATIONS=1` is opt-in for a reason;
  leave writes disabled unless the agent genuinely needs them.
- **Read-only credentials.** If your backend is a shared database, connect
  with a read-only user for query-only deployments.
