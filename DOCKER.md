# Dockerizing Anansi

Anansi comes with two Docker setups:

1. **MCP stdio server** (`Dockerfile`) — for use with MCP clients (Claude Desktop, VS Code)
2. **UI stack** (`ui/Dockerfile`) — React web interface + Flask GraphQL proxy, includes built UI assets

You can run them separately or together via `docker-compose.yml`.

## Quick start: Web UI only

```powershell
docker compose up ui
```

Visit `http://localhost:8000` in your browser. Query the GraphQL API interactively.

## Quick start: Full stack (UI + MCP stdio server)

```powershell
# Build both images and start the UI
docker compose up ui

# In another terminal, use the MCP server with your client:
docker compose run --rm -T anansi
```

## Files

- `Dockerfile` — MCP stdio server (Python 3.11, no HTTP port)
- `ui/Dockerfile` — UI service (builds React app + serves Flask proxy on port 8000)
- `docker-compose.yml` — Orchestrates both services

## Build images

```powershell
# Build UI image only
docker compose build ui

# Build MCP server image only
docker compose build anansi

# Build both
docker compose build
```

## Run the UI service

Serves the React app + GraphQL proxy endpoint on port 8000:

```powershell
docker compose up ui
```

Then open `http://localhost:8000`.

To use a different port, set `UI_PORT`:

```powershell
docker compose -e UI_PORT=9000 up ui
```

Then open `http://localhost:9000`.

### Environment variables for UI

| Variable | Default | Purpose |
| --- | --- | --- |
| `ANANSI_ALLOW_MUTATIONS` | `0` | Enable `graphql_mutate` |
| `ANANSI_MAX_DEPTH` | `10` | Max query nesting |
| `ANANSI_MAX_COMPLEXITY` | `100` | Max fields per request |
| `ANANSI_MAX_RESULT_BYTES` | `262144` | Max response size |
| `FLASK_HOST` | `0.0.0.0` | Flask bind address |
| `FLASK_PORT` | `8000` | Flask port |
| `FLASK_DEBUG` | `0` | Flask debug mode |

Example:

```powershell
docker compose -e ANANSI_ALLOW_MUTATIONS=1 up ui
```

Or use a `.env` file:

```sh
# .env
ANANSI_ALLOW_MUTATIONS=1
UI_PORT=9000
```

Then:

```powershell
docker compose up ui
```

## Run the MCP server

The `anansi` service is a stdio-based MCP server (no HTTP port). It's designed to be launched by MCP clients:

```powershell
docker compose run --rm -T anansi
```

Use `-T` to avoid allocating a TTY (required for MCP).

### MCP client integration

#### Claude Desktop

Add to your Claude Desktop config:

```json
{
  "mcpServers": {
    "anansi": {
      "command": "docker",
      "args": ["compose", "run", "--rm", "-T", "anansi"],
      "env": {
        "ANANSI_ALLOW_MUTATIONS": "1"
      }
    }
  }
}
```

Location:
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

#### VS Code

Add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "anansi-docker": {
      "type": "stdio",
      "command": "docker",
      "args": ["compose", "run", "--rm", "-T", "anansi"],
      "env": {
        "ANANSI_ALLOW_MUTATIONS": "1",
        "ANANSI_MAX_DEPTH": "10",
        "ANANSI_MAX_COMPLEXITY": "100"
      }
    }
  }
}
```

## Environment variables (both services)

| Variable | Default | Purpose |
| --- | --- | --- |
| `ANANSI_ALLOW_MUTATIONS` | `0` | Set to `1`/`true`/`yes`/`on` to enable `graphql_mutate` |
| `ANANSI_MAX_DEPTH` | `10` | Maximum query nesting depth |
| `ANANSI_MAX_COMPLEXITY` | `100` | Maximum total selected fields per request |
| `ANANSI_MAX_RESULT_BYTES` | `262144` | Maximum serialized response size; `0` disables |

## Extending the stack

Add your own services to `docker-compose.yml`:

```yaml
services:
  my-agent:
    image: ghcr.io/example/agent
    depends_on:
      - ui  # or anansi
    environment:
      GRAPHQL_ENDPOINT: http://ui:8000/graphql
```

## Verification

### UI service

```powershell
docker compose up ui
```

```powershell
curl http://localhost:8000/
curl http://localhost:8000/graphql
```

### MCP server

```powershell
docker compose run --rm anansi --help
```

Or check imports:

```powershell
docker run --rm --entrypoint python anansi-mcp:local -c "import anansi.server; print('OK')"
```

### Build & compose config

```powershell
docker compose config
docker compose build --dry-run
```

## Troubleshooting

**"Cannot find ui/dist"** when building UI image:
- Run `npm run build` locally in the `ui/` folder first, or
- The Dockerfile build stage will do it automatically

**Port already in use:**
```powershell
docker compose down  # Stop containers
# Or use a different port:
docker compose -e UI_PORT=9000 up ui
```

**Permission denied on stdio:**
```powershell
docker compose run --rm -T anansi  # Use -T flag
```

## Notes

- The `anansi` service uses `profile: ["mcp"]` by default (won't start unless explicitly referenced)
- The `ui` service starts by default with `docker compose up`
- Example services (`claude-desktop-example`, etc.) use `profile: ["examples"]` for reference only
