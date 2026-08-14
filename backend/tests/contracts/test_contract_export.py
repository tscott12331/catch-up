from __future__ import annotations

import json

from export_contracts import render_contracts


def test_contract_render_is_byte_deterministic_and_workspace_excludes_passages() -> None:
    first = render_contracts()
    second = render_contracts()

    assert first == second
    openapi_content = next(content for path, content in first.items() if path.name == "openapi.json")
    openapi = json.loads(openapi_content)
    workspace = openapi["components"]["schemas"]["WorkspaceResponse"]
    assert "passages" not in workspace["properties"]
    assert "passages" not in workspace["required"]

    domain_content = next(content for path, content in first.items() if path.name == "domain-schemas.json")
    domain = json.loads(domain_content)
    assert "SourcePassage" in domain["schemas"]

    sse_content = next(content for path, content in first.items() if path.name == "sse-events.json")
    sse = json.loads(sse_content)
    assert "id" in sse["schema"]["$defs"]["Citation"]["required"]


def test_fresh_app_openapi_workspace_excludes_internal_passages(runtime) -> None:
    workspace_schema = runtime.app.openapi()["components"]["schemas"]["WorkspaceResponse"]
    assert "passages" not in workspace_schema["properties"]
    assert "passages" not in workspace_schema["required"]
