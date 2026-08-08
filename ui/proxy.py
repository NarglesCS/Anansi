from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory, send_file
from flask_cors import CORS
from graphql import print_schema

from anansi.engine import run_operation
from anansi.schema import build_executable_schema

# Serve built React app from dist folder
DIST_DIR = Path(__file__).parent / "dist"
STATIC_FOLDER = DIST_DIR if DIST_DIR.exists() else None

app = Flask(__name__, static_folder=STATIC_FOLDER, static_url_path="")
CORS(app)
SCHEMA = build_executable_schema()


def mutations_enabled() -> bool:
    return os.getenv("ANANSI_ALLOW_MUTATIONS", "").strip().lower() in {"1", "true", "yes", "on"}


@app.get("/graphql")
def graphql_get():
    return jsonify({
        "message": "Send POST requests with a GraphQL query.",
        "schema": print_schema(SCHEMA),
        "mutationsEnabled": mutations_enabled(),
    })


@app.post("/graphql")
def graphql_post():
    payload = request.get_json(silent=True) or {}
    query = payload.get("query")
    variables = payload.get("variables")

    if not isinstance(query, str) or not query.strip():
        return jsonify({"data": None, "errors": [{"message": "Request body must include a non-empty 'query' string."}]}), 400

    allow_mutations = mutations_enabled()
    result = run_operation(SCHEMA, query, variables, allow_mutations=allow_mutations)
    status = 200 if not result.get("errors") else 400 if result.get("data") is None else 200
    return jsonify(result), status


# Serve static assets (JS, CSS, etc.)
@app.get("/<path:path>")
def serve_static(path: str):
    if STATIC_FOLDER and (STATIC_FOLDER / path).is_file():
        return send_from_directory(STATIC_FOLDER, path)
    # SPA: fallback to index.html for client-side routing
    if STATIC_FOLDER and (STATIC_FOLDER / "index.html").exists():
        return send_file(STATIC_FOLDER / "index.html")
    return jsonify({"error": "Not found"}), 404


# Serve index.html for root
@app.get("/")
def serve_root():
    if STATIC_FOLDER and (STATIC_FOLDER / "index.html").exists():
        return send_file(STATIC_FOLDER / "index.html")
    return jsonify({"message": "Anansi UI not built. Run 'npm run build' in the ui/ directory.", "graphql_endpoint": "/graphql"})



if __name__ == "__main__":
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_PORT", "8000"))
    debug = os.getenv("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}
    app.run(host=host, port=port, debug=debug)
