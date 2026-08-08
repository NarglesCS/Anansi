# Anansi GraphQL UI

A React + TypeScript + Vite frontend for interacting with Anansi through a lightweight Flask HTTP proxy.

## Features

- Run GraphQL queries from the browser
- Run GraphQL mutations when `ANANSI_ALLOW_MUTATIONS=1`
- Pass variables as JSON
- Browse the schema via GraphQL introspection
- Inspect formatted JSON responses
- Start with example operations against the seed blog data

## Prerequisites

- Python 3.10+
- Node.js 18+

## Install

From the repository root:

```powershell
python -m pip install -e .
cd ui
npm install
```

## Start the backend proxy

From the repository root:

```powershell
python ui\proxy.py
```

This starts an HTTP GraphQL endpoint at `http://127.0.0.1:8000/graphql`.

To enable mutations:

```powershell
$env:ANANSI_ALLOW_MUTATIONS = "1"
python ui\proxy.py
```

## Start the UI

In a second terminal:

```powershell
cd ui
npm run dev
```

Open the printed local Vite URL in your browser. The UI defaults to `http://127.0.0.1:8000/graphql`.

## Build

```powershell
cd ui
npm run build
```

## Using the UI

1. Start `python ui\proxy.py`.
2. Start `npm run dev` inside `ui`.
3. Run the seeded query to browse users, posts, and comments from the mock blog dataset.
4. Edit the variables JSON to change filters or limits.
5. Switch to **Mutation** to create a draft post when mutations are enabled.
6. Use **Refresh schema** to reload the schema browser.

## Notes

- The proxy reuses `anansi.schema` and `anansi.engine`, so it matches the same schema and execution rules as the MCP server.
- The seed data comes from `src/anansi/data.py`.
- The data store is in-memory; restarting the proxy resets it.
