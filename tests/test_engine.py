"""End-to-end tests for the GraphQL engine and safety rails (no MCP transport)."""

from __future__ import annotations

import pytest

from anansi import data
from anansi.engine import (
    default_max_complexity,
    default_max_depth,
    default_max_result_bytes,
    measure_complexity,
    measure_depth,
    run_operation,
    validate_only,
)
from anansi.schema import build_executable_schema

SCHEMA = build_executable_schema()


@pytest.fixture(autouse=True)
def _reset_data():
    data.reset()
    yield
    data.reset()


def test_nested_query_returns_only_requested_fields():
    result = run_operation(
        SCHEMA, "{ users(role: ADMIN) { name posts { title } } }"
    )
    assert "errors" not in result
    assert result["data"] == {
        "users": [
            {
                "name": "Ada Lovelace",
                "posts": [
                    {"title": "Notes on the Analytical Engine"},
                    {"title": "Poetry and Programming"},
                ],
            }
        ]
    }


def test_variables_and_relation_traversal():
    result = run_operation(
        SCHEMA,
        "query($id: ID!) { post(id: $id) { title author { name } comments(limit: 1) { text } } }",
        {"id": "p3"},
    )
    assert "errors" not in result
    post = result["data"]["post"]
    assert post["title"] == "The First Compiler"
    assert post["author"]["name"] == "Grace Hopper"
    assert len(post["comments"]) == 1


def test_filter_arguments():
    result = run_operation(SCHEMA, "{ posts(published: false) { id } }")
    assert {p["id"] for p in result["data"]["posts"]} == {"p2", "p6"}


def test_validation_catches_unknown_field():
    check = validate_only(SCHEMA, "{ users { nickname } }")
    assert check["valid"] is False
    assert "nickname" in check["errors"][0]["message"]


def test_validate_reports_depth_and_complexity():
    check = validate_only(SCHEMA, "{ users { posts { title } } }")
    assert check == {"valid": True, "errors": [], "depth": 3, "complexity": 3}


def test_syntax_error_is_structured():
    result = run_operation(SCHEMA, "{ users {")
    assert result["data"] is None
    assert result["errors"]


def test_depth_limit_blocks_deep_queries():
    deep = "{ users { posts { comments { author { name } } } } }"
    result = run_operation(SCHEMA, deep, max_depth=3)
    assert result["data"] is None
    assert "depth" in result["errors"][0]["message"].lower()


def test_complexity_limit_blocks_wide_queries():
    result = run_operation(SCHEMA, "{ users { id name email role } }", max_complexity=3)
    assert result["data"] is None
    message = result["errors"][0]["message"]
    assert "complexity" in message.lower()
    assert "fewer fields" in message  # remediation hint for the model


def test_complexity_within_limit_executes():
    result = run_operation(SCHEMA, "{ users { id } }", max_complexity=3)
    assert "errors" not in result
    assert len(result["data"]["users"]) == 4


def test_complexity_counts_fragment_fields():
    from graphql import parse

    doc = parse("query { users { ...F } } fragment F on User { id name }")
    assert measure_complexity(doc) == 3  # users + id + name


def test_complexity_fragment_cycles_terminate():
    from graphql import parse

    doc = parse(
        """
        query { users { ...A } }
        fragment A on User { name ...B }
        fragment B on User { email ...A }
        """
    )
    assert measure_complexity(doc) == 3  # users + name + email, cycle skipped


def test_result_size_cap_blocks_large_payloads():
    result = run_operation(SCHEMA, "{ posts { title body } }", max_result_bytes=50)
    assert result["data"] is None
    message = result["errors"][0]["message"]
    assert "bytes" in message
    assert "limit arguments" in message  # remediation hint for the model


def test_result_size_cap_zero_disables_check():
    result = run_operation(SCHEMA, "{ posts { title body } }", max_result_bytes=0)
    assert "errors" not in result
    assert len(result["data"]["posts"]) == 6


def test_env_limits_fall_back_on_garbage(monkeypatch):
    monkeypatch.setenv("ANANSI_MAX_DEPTH", "banana")
    monkeypatch.setenv("ANANSI_MAX_COMPLEXITY", "")
    monkeypatch.setenv("ANANSI_MAX_RESULT_BYTES", "12.5")
    assert default_max_depth() == 10
    assert default_max_complexity() == 100
    assert default_max_result_bytes() == 262_144


def test_env_depth_limit_honored(monkeypatch):
    monkeypatch.setenv("ANANSI_MAX_DEPTH", "2")
    result = run_operation(SCHEMA, "{ users { posts { title } } }")
    assert result["data"] is None
    assert "depth" in result["errors"][0]["message"].lower()


def test_repeated_queries_hit_cache_but_execution_stays_fresh():
    from anansi.engine import _prepare

    _prepare.cache_clear()
    query = "{ posts(published: false) { id } }"

    first = run_operation(SCHEMA, query)
    assert _prepare.cache_info().misses == 1
    assert {p["id"] for p in first["data"]["posts"]} == {"p2", "p6"}

    run_operation(
        SCHEMA, 'mutation { publishPost(id: "p2") { id } }', allow_mutations=True
    )

    second = run_operation(SCHEMA, query)
    assert _prepare.cache_info().hits >= 1  # static analysis reused
    assert {p["id"] for p in second["data"]["posts"]} == {"p6"}  # data not stale


def test_fragment_cycles_do_not_hang_depth_measurement():
    from graphql import parse

    doc = parse(
        """
        query { users { ...A } }
        fragment A on User { name ...B }
        fragment B on User { email ...A }
        """
    )
    assert measure_depth(doc) >= 2  # terminates despite the A<->B cycle


def test_mutation_rejected_without_allow_flag():
    result = run_operation(
        SCHEMA,
        'mutation { publishPost(id: "p2") { published } }',
    )
    assert result["data"] is None
    assert "not allowed" in result["errors"][0]["message"]
    assert data.post_by_id("p2")["published"] is False  # nothing executed


def test_subscription_always_rejected():
    result = run_operation(
        SCHEMA, "subscription { anything }", allow_mutations=True
    )
    assert "not supported" in result["errors"][0]["message"]


def test_mutation_roundtrip_when_allowed():
    created = run_operation(
        SCHEMA,
        "mutation($input: CreatePostInput!) { createPost(input: $input) { id published } }",
        {"input": {"authorId": "u3", "title": "New", "body": "..."}},
        allow_mutations=True,
    )
    assert "errors" not in created
    new_id = created["data"]["createPost"]["id"]
    assert created["data"]["createPost"]["published"] is False

    published = run_operation(
        SCHEMA,
        f'mutation {{ publishPost(id: "{new_id}") {{ published }} }}',
        allow_mutations=True,
    )
    assert published["data"]["publishPost"]["published"] is True


def test_resolver_error_surfaces_as_graphql_error():
    result = run_operation(
        SCHEMA,
        'mutation { publishPost(id: "nope") { id } }',
        allow_mutations=True,
    )
    assert "Unknown post id" in result["errors"][0]["message"]
