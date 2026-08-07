"""GraphQL schema: SDL (with doc strings that travel to the model) + resolvers."""

from __future__ import annotations

from typing import Any

from graphql import GraphQLError, GraphQLObjectType, GraphQLSchema, build_schema

from . import data

SDL = '''\
type Query {
  "List users, optionally filtered by role."
  users(role: Role, limit: Int): [User!]!
  "Fetch a single user by id."
  user(id: ID!): User
  "List posts, optionally filtered by author and/or published state."
  posts(authorId: ID, published: Boolean, limit: Int): [Post!]!
  "Fetch a single post by id."
  post(id: ID!): Post
}

type Mutation {
  "Create a draft (unpublished) post for an existing author."
  createPost(input: CreatePostInput!): Post!
  "Mark an existing post as published."
  publishPost(id: ID!): Post!
}

enum Role {
  ADMIN
  MEMBER
}

"A blog author."
type User {
  id: ID!
  name: String!
  email: String!
  role: Role!
  "Posts written by this user."
  posts(limit: Int): [Post!]!
}

"An article written by a User."
type Post {
  id: ID!
  title: String!
  body: String!
  published: Boolean!
  author: User!
  "Comments left on this post."
  comments(limit: Int): [Comment!]!
}

"A comment left by a User on a Post."
type Comment {
  id: ID!
  text: String!
  author: User!
  post: Post!
}

input CreatePostInput {
  authorId: ID!
  title: String!
  body: String!
}
'''


def _limited(rows: list[dict[str, Any]], limit: int | None) -> list[dict[str, Any]]:
    return rows if limit is None else rows[:limit]


# --- Query resolvers -------------------------------------------------------

def _users(_src: Any, _info: Any, role: str | None = None, limit: int | None = None):
    rows = [u for u in data.USERS if role is None or u["role"] == role]
    return _limited(rows, limit)


def _user(_src: Any, _info: Any, id: str):
    return data.user_by_id(id)


def _posts(_src: Any, _info: Any, authorId: str | None = None,
           published: bool | None = None, limit: int | None = None):
    rows = [
        p for p in data.POSTS
        if (authorId is None or p["authorId"] == authorId)
        and (published is None or p["published"] == published)
    ]
    return _limited(rows, limit)


def _post(_src: Any, _info: Any, id: str):
    return data.post_by_id(id)


# --- Relation resolvers ----------------------------------------------------

def _user_posts(user: dict[str, Any], _info: Any, limit: int | None = None):
    return _limited(data.posts_by_author(user["id"]), limit)


def _post_author(post: dict[str, Any], _info: Any):
    return data.user_by_id(post["authorId"])


def _post_comments(post: dict[str, Any], _info: Any, limit: int | None = None):
    return _limited(data.comments_for_post(post["id"]), limit)


def _comment_author(comment: dict[str, Any], _info: Any):
    return data.user_by_id(comment["authorId"])


def _comment_post(comment: dict[str, Any], _info: Any):
    return data.post_by_id(comment["postId"])


# --- Mutation resolvers ----------------------------------------------------

def _create_post(_src: Any, _info: Any, input: dict[str, Any]):
    author_id = input["authorId"]
    if data.user_by_id(author_id) is None:
        raise GraphQLError(f"Unknown authorId: {author_id!r}")
    return data.create_post(author_id, input["title"], input["body"])


def _publish_post(_src: Any, _info: Any, id: str):
    post = data.post_by_id(id)
    if post is None:
        raise GraphQLError(f"Unknown post id: {id!r}")
    post["published"] = True
    return post


def build_executable_schema() -> GraphQLSchema:
    """Build the schema from SDL and attach resolvers."""
    schema = build_schema(SDL)

    def fields(type_name: str):
        type_ = schema.type_map[type_name]
        assert isinstance(type_, GraphQLObjectType)
        return type_.fields

    query = fields("Query")
    query["users"].resolve = _users
    query["user"].resolve = _user
    query["posts"].resolve = _posts
    query["post"].resolve = _post

    mutation = fields("Mutation")
    mutation["createPost"].resolve = _create_post
    mutation["publishPost"].resolve = _publish_post

    fields("User")["posts"].resolve = _user_posts
    post_fields = fields("Post")
    post_fields["author"].resolve = _post_author
    post_fields["comments"].resolve = _post_comments
    comment_fields = fields("Comment")
    comment_fields["author"].resolve = _comment_author
    comment_fields["post"].resolve = _comment_post

    return schema
