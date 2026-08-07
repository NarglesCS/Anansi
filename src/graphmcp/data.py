"""In-memory demo dataset.

This module is the swappable backend layer: replace these lists and helpers
with SQL queries, REST fan-out, or service calls without touching the schema,
engine, or MCP wiring.
"""

from __future__ import annotations

import itertools
from copy import deepcopy
from typing import Any

Row = dict[str, Any]

_USERS0: list[Row] = [
    {"id": "u1", "name": "Ada Lovelace", "email": "ada@example.com", "role": "ADMIN"},
    {"id": "u2", "name": "Grace Hopper", "email": "grace@example.com", "role": "MEMBER"},
    {"id": "u3", "name": "Alan Turing", "email": "alan@example.com", "role": "MEMBER"},
    {"id": "u4", "name": "Katherine Johnson", "email": "katherine@example.com", "role": "MEMBER"},
]

_POSTS0: list[Row] = [
    {"id": "p1", "authorId": "u1", "title": "Notes on the Analytical Engine",
     "body": "The engine weaves algebraic patterns as the loom weaves flowers.", "published": True},
    {"id": "p2", "authorId": "u1", "title": "Poetry and Programming",
     "body": "On imagination as an instrument of discovery.", "published": False},
    {"id": "p3", "authorId": "u2", "title": "The First Compiler",
     "body": "A-0 translates symbolic code into machine instructions.", "published": True},
    {"id": "p4", "authorId": "u3", "title": "On Computable Numbers",
     "body": "An application to the Entscheidungsproblem.", "published": True},
    {"id": "p5", "authorId": "u4", "title": "Orbital Mechanics by Hand",
     "body": "Verifying trajectories for the Friendship 7 mission.", "published": True},
    {"id": "p6", "authorId": "u2", "title": "Debugging: The Actual Moth",
     "body": "First actual case of bug being found.", "published": False},
]

_COMMENTS0: list[Row] = [
    {"id": "c1", "postId": "p1", "authorId": "u2", "text": "Brilliant — the loom analogy holds up."},
    {"id": "c2", "postId": "p1", "authorId": "u3", "text": "This anticipates universal machines."},
    {"id": "c3", "postId": "p3", "authorId": "u1", "text": "COBOL walked so the rest could run."},
    {"id": "c4", "postId": "p4", "authorId": "u4", "text": "The halting problem section is my favorite."},
    {"id": "c5", "postId": "p5", "authorId": "u1", "text": "Checked the math — flawless."},
    {"id": "c6", "postId": "p3", "authorId": "u4", "text": "A compiler in 1952. Astonishing."},
]

USERS: list[Row] = deepcopy(_USERS0)
POSTS: list[Row] = deepcopy(_POSTS0)
COMMENTS: list[Row] = deepcopy(_COMMENTS0)

_post_ids = itertools.count(100)


def reset() -> None:
    """Restore the pristine dataset (used by tests)."""
    global _post_ids
    USERS[:] = deepcopy(_USERS0)
    POSTS[:] = deepcopy(_POSTS0)
    COMMENTS[:] = deepcopy(_COMMENTS0)
    _post_ids = itertools.count(100)


def user_by_id(uid: str) -> Row | None:
    return next((u for u in USERS if u["id"] == uid), None)


def post_by_id(pid: str) -> Row | None:
    return next((p for p in POSTS if p["id"] == pid), None)


def posts_by_author(uid: str) -> list[Row]:
    return [p for p in POSTS if p["authorId"] == uid]


def comments_for_post(pid: str) -> list[Row]:
    return [c for c in COMMENTS if c["postId"] == pid]


def create_post(author_id: str, title: str, body: str) -> Row:
    post: Row = {
        "id": f"p{next(_post_ids)}",
        "authorId": author_id,
        "title": title,
        "body": body,
        "published": False,
    }
    POSTS.append(post)
    return post
