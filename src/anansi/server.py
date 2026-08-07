"""Thin MCP wiring: MCPServer exposing the GraphQL surface."""

from __future__ import annotations

import os
from typing import Any

from graphql import print_schema
from mcp.server import MCPServer

from .engine import run_operation, validate_only
from .schema import build_executable_schema

SCHEMA = build_executable_schema()
SCHEMA_SDL = print_schema(SCHEMA)  # includes SDL doc strings for the model

INSTRUCTIONS = """\
This server exposes a typed GraphQL API over MCP.

Workflow:
1. Read the resource graphql://schema (or call graphql_schema) to learn the types.
2. Optionally call graphql_validate to check a query before spending an execution.
3. Call graphql_query, selecting only the fields you need; use nested selections
   to fetch related data in one call instead of many.
4. For writes, call graphql_mutate (only available when the host enables it).
"""

mcp = MCPServer("anansi", instructions=INSTRUCTIONS)


def _mutations_enabled() -> bool:
    return os.getenv("ANANSI_ALLOW_MUTATIONS", "").strip().lower() in {
        "1", "true", "yes", "on",
    }


@mcp.resource("graphql://schema", mime_type="text/plain")
def schema_resource() -> str:
    """The GraphQL schema (SDL) served by this server."""
    return SCHEMA_SDL


@mcp.tool()
def graphql_schema() -> str:
    """Return the GraphQL schema (SDL). Call this before writing queries."""
    return SCHEMA_SDL


@mcp.tool()
def graphql_validate(query: str) -> dict[str, Any]:
    """Validate a GraphQL query without executing it.

    Returns {"valid": bool, "errors": [...], "depth": int, "complexity": int}.
    Use this to catch typos and invalid fields cheaply before calling
    graphql_query. Depth and complexity must stay within the server limits.
    """
    return validate_only(SCHEMA, query)


@mcp.tool()
def graphql_query(query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute a read-only GraphQL query and return {"data", "errors"}.

    Select only the fields you need. Example:

        query($role: Role) {
          users(role: $role) { name posts(limit: 2) { title } }
        }

    with variables {"role": "ADMIN"}. Mutations are rejected here.
    """
    return run_operation(SCHEMA, query, variables, allow_mutations=False)


@mcp.tool()
def graphql_mutate(mutation: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute a GraphQL mutation (write operation).

    Only permitted when the server is started with ANANSI_ALLOW_MUTATIONS=1.
    Example:

        mutation($input: CreatePostInput!) { createPost(input: $input) { id } }
    """
    if not _mutations_enabled():
        return {
            "data": None,
            "errors": [{
                "message": "Mutations are disabled. Start the server with "
                           "ANANSI_ALLOW_MUTATIONS=1 to enable writes."
            }],
        }
    return run_operation(SCHEMA, mutation, variables, allow_mutations=True)


def main() -> None:
    """Run the server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
