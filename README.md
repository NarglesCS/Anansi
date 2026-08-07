# Anansi

[![CI](https://github.com/NarglesCS/anansi/actions/workflows/ci.yml/badge.svg)](https://github.com/NarglesCS/anansi/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/anansi)](https://pypi.org/project/anansi/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**An MCP server that speaks GraphQL.** Named for the spider who owns all stories:
instead of exposing one tool per endpoint, Anansi spins your backend into a single
typed web. The agent reads the schema, then composes exactly the query it needs —
nested relations in one call, only the fields it wants.

Ships with a mock blog dataset (users → posts → comments) so you can try it the
moment you clone it.

## Why

| Concern | Tool-per-endpoint MCP server | Anansi |
| --- | --- | --- |
| Tool count | Grows with the API (tool explosion) | 4 fixed tools |
| Over-fetching | Full payloads → wasted tokens | Agent selects only needed fields |
| Related data | One round trip per relation | Nested selections, single call |
| Discoverability | Prose tool descriptions | Typed schema (SDL) with doc strings |
| Self-correction | Errors only after execution | Pre-flight `graphql_validate` + structured GraphQL errors |

## Quickstart

### No clone needed (any MCP client)

With [uv](https://docs.astral.sh/uv/) installed, add this to your MCP client
config (Claude Desktop, VS Code, etc.):

```json
{
  "mcpServers": {
    "anansi": {
      "command": "uvx",
      "args": ["anansi"],
      "env": { "ANANSI_ALLOW_MUTATIONS": "1" }
    }
  }
}
```

### From source

Requires Python 3.10+.

```sh
git clone https://github.com/NarglesCS/anansi.git
cd anansi
python -m venv .venv

# Windows
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\python.exe -m pytest -q     # verify: 12 tests

# macOS / Linux
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m pytest -q
```

## Interacting with it

### Option 1 — MCP Inspector (fastest way to poke at the mock data)

```sh
npx @modelcontextprotocol/inspector .venv/Scripts/python.exe -m anansi.server
```

Opens a browser UI where you can list the tools, read the `graphql://schema`
resource, and run queries by hand.

### Option 2 — VS Code agent mode

[.vscode/mcp.json](.vscode/mcp.json) is preconfigured. Open the repo in VS Code,
start the `anansi` server from the MCP view, then ask Copilot agent mode things
like *"Who commented on Grace Hopper's posts?"* and watch it discover the schema
and compose queries.

### Option 3 — Any MCP client (Claude Desktop, etc.)

```json
{
  "mcpServers": {
    "anansi": {
      "command": "/absolute/path/to/anansi/.venv/bin/python",
      "args": ["-m", "anansi.server"],
      "env": { "ANANSI_ALLOW_MUTATIONS": "1" }
    }
  }
}
```

(On Windows the command is `...\anansi\.venv\Scripts\python.exe`.)

## What the server exposes

| Kind | Name | Purpose |
| --- | --- | --- |
| Resource | `graphql://schema` | The SDL, loadable as context up front |
| Tool | `graphql_schema()` | Same SDL for clients that prefer tools over resources |
| Tool | `graphql_validate(query)` | Parse + validate + measure depth **without executing** |
| Tool | `graphql_query(query, variables?)` | Read-only execution; mutations rejected |
| Tool | `graphql_mutate(mutation, variables?)` | Writes, only when `ANANSI_ALLOW_MUTATIONS=1` |

### Example: query the mock data

```graphql
query($role: Role) {
  users(role: $role) {
    name
    posts(limit: 2) {
      title
      comments { author { name } text }
    }
  }
}
```

with variables `{"role": "ADMIN"}` returns, in one round trip:

```json
{"data": {"users": [{"name": "Ada Lovelace", "posts": [{"title": "...", "comments": [...]}]}]}}
```

### Example: write to the mock data

```graphql
mutation($input: CreatePostInput!) {
  createPost(input: $input) { id published }
}
```

with `{"input": {"authorId": "u3", "title": "Hello", "body": "..."}}`.
The store is in-memory — restart the server and you're back to the seed data.

## Configuration

| Env var | Default | Effect |
| --- | --- | --- |
| `ANANSI_ALLOW_MUTATIONS` | off | Set to `1` to enable `graphql_mutate` |
| `ANANSI_MAX_DEPTH` | `10` | Max query nesting depth (fragment-cycle safe) |

Other rails: `graphql_query` hard-rejects mutations, subscriptions are always
rejected, and all errors come back as standard GraphQL `{message, locations, path}`
shapes that models know how to read and repair.

## How it's built

```mermaid
flowchart LR
    Agent["AI agent (MCP client)"] -- "MCP stdio" --> Tools

    subgraph Anansi["Anansi server"]
        direction TB
        Tools["Tools: graphql_query / graphql_validate / graphql_mutate / graphql_schema"]
        Schema["Resource: graphql://schema (SDL)"]
        Engine["Engine: parse → gate ops → validate → depth-check → execute"]
        Resolvers["Resolvers"]
    end

    Tools --> Engine --> Resolvers --> Store[("In-memory mock store<br/>(swap for DB / REST fan-out / services)")]
    Agent -. "reads schema" .-> Schema
```

Each layer is independently swappable:

- [src/anansi/data.py](src/anansi/data.py) — in-memory mock dataset. Replace with any real backend.
- [src/anansi/schema.py](src/anansi/schema.py) — SDL with doc strings (they travel to the model) + resolver wiring.
- [src/anansi/engine.py](src/anansi/engine.py) — execution pipeline with safety rails; no MCP dependency.
- [src/anansi/server.py](src/anansi/server.py) — thin MCP wiring: tools, resource, instructions.

## Roadmap ideas

- Swap `data.py` for a real datasource (SQL, REST fan-out, microservices) — the
  classic GraphQL gateway pattern, now agent-facing.
- Per-field auth, query cost analysis, timeouts, result-size caps.
- Persisted-query allowlists for high-trust deployments.
- GraphQL subscriptions mapped onto MCP notifications.

## License

[MIT](LICENSE)

Contributions and issues welcome.
