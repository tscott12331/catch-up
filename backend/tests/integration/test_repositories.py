from __future__ import annotations

from uuid import UUID

import httpx
import pytest


@pytest.mark.anyio
async def test_repository_registration_creates_lifecycle_records(register_repository) -> None:
    body = await register_repository("https://github.com/acme/new-service")
    assert UUID(body["repository"]["id"]).version == 4
    assert body["conversation"]["repository_id"] == body["repository"]["id"]
    assert body["job"]["repository_id"] == body["repository"]["id"]
    assert body["job"]["status"] == "queued"


@pytest.mark.anyio
async def test_workspace_and_files_require_registered_repository(client: httpx.AsyncClient) -> None:
    for path in (
        "/api/repositories/unregistered/repository/workspace",
        "/api/repositories/unregistered/repository/files?path=README.md",
    ):
        response = await client.get(path)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "repository_not_found"


@pytest.mark.anyio
async def test_new_conversation_becomes_active_and_isolates_messages(client: httpx.AsyncClient, register_repository) -> None:
    created = await register_repository("https://github.com/acme/new-service")
    before = await client.get("/api/repositories/acme/new-service/workspace")
    assert len(before.json()["messages"]) == 3
    response = await client.post("/api/conversations", json={"repository_id": created["repository"]["id"]})
    assert response.status_code == 201
    after = await client.get("/api/repositories/acme/new-service/workspace")
    assert after.json()["conversation"]["id"] == response.json()["id"]
    assert after.json()["messages"] == []
