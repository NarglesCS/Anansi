"""Execution pipeline: parse → gate operations → validate → depth-check → execute.

No MCP dependency here; this module is testable standalone.
"""

from __future__ import annotations

import os
from typing import Any

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


def default_max_depth() -> int:
    return int(os.getenv("ANANSI_MAX_DEPTH", "10"))


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


def _error_payload(message: str) -> dict[str, Any]:
    return {"data": None, "errors": [{"message": message}]}


def run_operation(
    schema: GraphQLSchema,
    query: str,
    variables: dict[str, Any] | None = None,
    *,
    allow_mutations: bool = False,
    max_depth: int | None = None,
) -> dict[str, Any]:
    """Execute a GraphQL operation, returning the standard {data, errors} shape."""
    limit = default_max_depth() if max_depth is None else max_depth

    try:
        document = parse(query)
    except GraphQLError as exc:
        return {"data": None, "errors": [exc.formatted]}

    operations = [
        d for d in document.definitions if isinstance(d, OperationDefinitionNode)
    ]
    if not operations:
        return _error_payload("Document contains no executable operation.")
    for op in operations:
        if op.operation is OperationType.SUBSCRIPTION:
            return _error_payload("Subscriptions are not supported over this interface.")
        if op.operation is OperationType.MUTATION and not allow_mutations:
            return _error_payload(
                "Mutations are not allowed through graphql_query. "
                "Use the graphql_mutate tool (requires ANANSI_ALLOW_MUTATIONS=1)."
            )

    validation_errors = validate(schema, document)
    if validation_errors:
        return {"data": None, "errors": [e.formatted for e in validation_errors]}

    depth = measure_depth(document)
    if depth > limit:
        return _error_payload(
            f"Query depth {depth} exceeds the limit of {limit}. "
            "Select fewer nested levels."
        )

    result = execute_sync(schema, document, variable_values=variables)
    payload: dict[str, Any] = {"data": result.data}
    if result.errors:
        payload["errors"] = [e.formatted for e in result.errors]
    return payload


def validate_only(schema: GraphQLSchema, query: str) -> dict[str, Any]:
    """Parse + validate without executing. Cheap pre-flight for self-correction."""
    try:
        document = parse(query)
    except GraphQLError as exc:
        return {"valid": False, "errors": [exc.formatted]}

    validation_errors = validate(schema, document)
    if validation_errors:
        return {"valid": False, "errors": [e.formatted for e in validation_errors]}

    return {"valid": True, "errors": [], "depth": measure_depth(document)}
