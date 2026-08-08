"""Export backend-owned API contracts for frontend generation and review."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from main import (
    ChatRequest,
    ChatSseEvent,
    Citation,
    Conversation,
    ErrorDetail,
    ErrorResponse,
    FileResponse,
    IndexingError,
    IndexingJob,
    Message,
    RepositoryCreateResponse,
    Repository,
    RepositoryRequest,
    SourcePassage,
    TreeNode,
    WorkspaceResponse,
    app,
)


CONTRACTS_DIR = Path(__file__).resolve().parent.parent / "contracts"

DOMAIN_MODELS = (
    Repository,
    IndexingError,
    IndexingJob,
    Conversation,
    Message,
    SourcePassage,
    Citation,
    TreeNode,
    RepositoryCreateResponse,
    WorkspaceResponse,
    FileResponse,
    ErrorDetail,
    ErrorResponse,
    RepositoryRequest,
    ChatRequest,
)


def render_contracts() -> dict[Path, str]:
    domain_schemas: dict[str, Any] = {
        model.__name__: model.model_json_schema(ref_template="#/$defs/{model}") for model in DOMAIN_MODELS
    }
    sse_schema = TypeAdapter(ChatSseEvent).json_schema(ref_template="#/$defs/{model}")
    outputs = {
        CONTRACTS_DIR / "openapi.json": app.openapi(),
        CONTRACTS_DIR / "domain-schemas.json": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Catch-up domain schemas",
            "schemas": domain_schemas,
        },
        CONTRACTS_DIR / "sse-events.json": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Catch-up chat SSE events",
            "framing": "Each event is emitted as a single Server-Sent Events data frame containing JSON.",
            "schema": sse_schema,
        },
    }
    return {path: json.dumps(payload, indent=2, sort_keys=True) + "\n" for path, payload in outputs.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if tracked contracts are stale")
    args = parser.parse_args()
    rendered = render_contracts()
    stale = [path for path, content in rendered.items() if not path.is_file() or path.read_text(encoding="utf-8") != content]

    if args.check:
        if stale:
            print("Contract artifacts are stale:", file=sys.stderr)
            for path in stale:
                print(f"  {path.relative_to(CONTRACTS_DIR.parent)}", file=sys.stderr)
            return 1
        return 0

    for path, content in rendered.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
