"""Execution pipeline: parse → gate operations → validate → depth-check → execute.

No MCP dependency here; this module is testable standalone.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any, NamedTuple

from graphql import GraphQLError, GraphQLSchema, execute_sync, parse, validate
from graphql.language import (
    DocumentNode,
    FieldNode,
    FragmentDefinitionNode,
    FragmentSpreadNode,
    InlineFragmentNode,
    OperationDefinitionNode,
    OperationType,
    SelectionSetNode,
)


def _env_int(name: str, default: int) -> int:
    """Read an int env var; fall back to the default on missing/garbage values."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def default_max_depth() -> int:
    return _env_int("ANANSI_MAX_DEPTH", 10)


def default_max_complexity() -> int:
    return _env_int("ANANSI_MAX_COMPLEXITY", 100)


def default_max_result_bytes() -> int:
    return _env_int("ANANSI_MAX_RESULT_BYTES", 262_144)  # 256 KiB; 0 disables


def measure_depth(document: DocumentNode) -> int:
    """Maximum field-nesting depth across all operations (fragment-cycle safe)."""
    fragments = {
        d.name.value: d
        for d in document.definitions
        if isinstance(d, FragmentDefinitionNode)
    }

    def depth_of(selection_set: SelectionSetNode | None, seen: frozenset[str]) -> int:
        if selection_set is None:
            return 0
        depth = 0
        for sel in selection_set.selections:
            if isinstance(sel, FieldNode):
                depth = max(depth, 1 + depth_of(sel.selection_set, seen))
            elif isinstance(sel, InlineFragmentNode):
                depth = max(depth, depth_of(sel.selection_set, seen))
            elif isinstance(sel, FragmentSpreadNode):
                name = sel.name.value
                if name in seen:
                    continue
                fragment = fragments.get(name)
                if fragment is not None:
                    depth = max(depth, depth_of(fragment.selection_set, seen | {name}))
        return depth

    return max(
        (
            depth_of(d.selection_set, frozenset())
            for d in document.definitions
            if isinstance(d, OperationDefinitionNode)
        ),
        default=0,
    )


def measure_complexity(document: DocumentNode) -> int:
    """Total field selections across all operations (fragments expanded, cycle-safe).

    A breadth guard to complement the depth limit: wide-but-shallow queries
    slip past depth checks but still produce huge responses.
    """
    fragments = {
        d.name.value: d
        for d in document.definitions
        if isinstance(d, FragmentDefinitionNode)
    }

    def count(selection_set: SelectionSetNode | None, seen: frozenset[str]) -> int:
        if selection_set is None:
            return 0
        total = 0
        for sel in selection_set.selections:
            if isinstance(sel, FieldNode):
                total += 1 + count(sel.selection_set, seen)
            elif isinstance(sel, InlineFragmentNode):
                total += count(sel.selection_set, seen)
            elif isinstance(sel, FragmentSpreadNode):
                name = sel.name.value
                if name in seen:
                    continue
                fragment = fragments.get(name)
                if fragment is not None:
                    total += count(fragment.selection_set, seen | {name})
        return total

    return sum(
        count(d.selection_set, frozenset())
        for d in document.definitions
        if isinstance(d, OperationDefinitionNode)
    )


class _Prepared(NamedTuple):
    document: DocumentNode
    validation_errors: tuple[dict[str, Any], ...]
    depth: int
    complexity: int


@lru_cache(maxsize=256)
def _prepare(schema: GraphQLSchema, query: str) -> _Prepared:
    """Parse, validate, and measure a query, memoized per (schema, query).

    Agents frequently retry identical queries; this skips re-parse/re-validate.
    Only static analysis is cached — execution never is. Raises GraphQLError
    on syntax errors (lru_cache does not cache raising calls).
    """
    document = parse(query)
    errors = tuple(e.formatted for e in validate(schema, document))
    return _Prepared(
        document, errors, measure_depth(document), measure_complexity(document)
    )


def _error_payload(message: str) -> dict[str, Any]:
    return {"data": None, "errors": [{"message": message}]}


def run_operation(
    schema: GraphQLSchema,
    query: str,
    variables: dict[str, Any] | None = None,
    *,
    allow_mutations: bool = False,
    max_depth: int | None = None,
    max_complexity: int | None = None,
    max_result_bytes: int | None = None,
) -> dict[str, Any]:
    """Execute a GraphQL operation, returning the standard {data, errors} shape."""
    depth_limit = default_max_depth() if max_depth is None else max_depth
    complexity_limit = (
        default_max_complexity() if max_complexity is None else max_complexity
    )
    byte_limit = (
        default_max_result_bytes() if max_result_bytes is None else max_result_bytes
    )

    try:
        prepared = _prepare(schema, query)
    except GraphQLError as exc:
        return {"data": None, "errors": [exc.formatted]}

    operations = [
        d
        for d in prepared.document.definitions
        if isinstance(d, OperationDefinitionNode)
    ]
    if not operations:
        return _error_payload(
            "Document contains no executable operation. "
            "Send a query like '{ fieldName { subField } }'."
        )
    for op in operations:
        if op.operation is OperationType.SUBSCRIPTION:
            return _error_payload(
                "Subscriptions are not supported over this interface. "
                "Use a query to fetch the current state instead."
            )
        if op.operation is OperationType.MUTATION and not allow_mutations:
            return _error_payload(
                "Mutations are not allowed through graphql_query. "
                "Use the graphql_mutate tool (requires ANANSI_ALLOW_MUTATIONS=1)."
            )

    if prepared.validation_errors:
        return {"data": None, "errors": list(prepared.validation_errors)}

    if prepared.depth > depth_limit:
        return _error_payload(
            f"Query depth {prepared.depth} exceeds the limit of {depth_limit}. "
            "Select fewer nested levels."
        )
    if prepared.complexity > complexity_limit:
        return _error_payload(
            f"Query complexity {prepared.complexity} (total fields selected) "
            f"exceeds the limit of {complexity_limit}. "
            "Request fewer fields or split the work into smaller queries."
        )

    result = execute_sync(schema, prepared.document, variable_values=variables)
    payload: dict[str, Any] = {"data": result.data}
    if result.errors:
        payload["errors"] = [e.formatted for e in result.errors]

    if byte_limit:
        size = len(json.dumps(payload, default=str).encode("utf-8"))
        if size > byte_limit:
            return _error_payload(
                f"Result is {size} bytes, over the {byte_limit}-byte limit. "
                "Narrow the query: select fewer fields, add limit arguments, "
                "or filter the results."
            )
    return payload


def validate_only(schema: GraphQLSchema, query: str) -> dict[str, Any]:
    """Parse + validate without executing. Cheap pre-flight for self-correction."""
    try:
        prepared = _prepare(schema, query)
    except GraphQLError as exc:
        return {"valid": False, "errors": [exc.formatted]}

    if prepared.validation_errors:
        return {"valid": False, "errors": list(prepared.validation_errors)}

    return {
        "valid": True,
        "errors": [],
        "depth": prepared.depth,
        "complexity": prepared.complexity,
    }
