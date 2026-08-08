from __future__ import annotations

import json
from uuid import UUID

import httpx
import pytest

from main import app, reset_in_memory_stores


@pytest.fixture(autouse=True)
def reset_stores() -> None:
    reset_in_memory_stores()


@pytest.fixture
async def client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client


async def register(client: httpx.AsyncClient, url: str = "https://github.com/acme/checkout-service") -> dict[str, object]:
    response = await client.post("/api/repositories", json={"url": url})
    assert response.status_code == 202
    return response.json()


@pytest.mark.anyio
async def test_health_reports_service_metadata(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")
    assert response.json() == {"status": "ok", "service": "catch-up-backend", "phase": 3}


@pytest.mark.anyio
async def test_creating_a_repository_registers_its_initial_lifecycle_records(client: httpx.AsyncClient) -> None:
    body = await register(client, "https://github.com/acme/new-service")
    repository = body["repository"]
    conversation = body["conversation"]
    job = body["job"]
    assert UUID(repository["id"]).version == 4
    assert conversation["repository_id"] == repository["id"]
    assert job["repository_id"] == repository["id"]
    assert job["status"] == "queued"


@pytest.mark.anyio
async def test_workspace_and_files_require_a_registered_repository(client: httpx.AsyncClient) -> None:
    for path in (
        "/api/repositories/unregistered/repository/workspace",
        "/api/repositories/unregistered/repository/files?path=README.md",
    ):
        response = await client.get(path)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "repository_not_found"


@pytest.mark.anyio
async def test_new_chat_becomes_active_and_isolated_from_prior_messages(client: httpx.AsyncClient) -> None:
    created = await register(client, "https://github.com/acme/new-service")
    repository = created["repository"]
    before = await client.get("/api/repositories/acme/new-service/workspace")
    assert len(before.json()["messages"]) == 3

    conversation_response = await client.post("/api/conversations", json={"repository_id": repository["id"]})
    assert conversation_response.status_code == 201
    conversation = conversation_response.json()
    after = await client.get("/api/repositories/acme/new-service/workspace")
    assert after.json()["conversation"]["id"] == conversation["id"]
    assert after.json()["messages"] == []


@pytest.mark.anyio
async def test_chat_rejects_a_conversation_owned_by_another_repository(client: httpx.AsyncClient) -> None:
    first = await register(client, "https://github.com/acme/first")
    second = await register(client, "https://github.com/acme/second")
    response = await client.post(
        "/api/chat/stream",
        json={
            "repository_id": first["repository"]["id"],
            "conversation_id": second["conversation"]["id"],
            "question": "How does checkout work?",
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conversation_repository_mismatch"


@pytest.mark.anyio
async def test_retry_creates_a_new_current_job(client: httpx.AsyncClient) -> None:
    created = await register(client, "https://github.com/acme/new-service")
    repository_id = created["repository"]["id"]
    original_job = created["job"]
    retry = await client.post(f"/api/repositories/{repository_id}/indexing-jobs")
    assert retry.status_code == 202
    assert retry.json()["id"] != original_job["id"]
    workspace = await client.get("/api/repositories/acme/new-service/workspace")
    assert workspace.json()["job"]["id"] == retry.json()["id"]


@pytest.mark.anyio
async def test_cancelling_a_job_is_terminal(client: httpx.AsyncClient) -> None:
    created = await register(client, "https://github.com/acme/new-service")
    job_id = created["job"]["id"]
    response = await client.post(f"/api/jobs/{job_id}/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == response.json()["stage"] == "cancelled"
    assert (await client.get(f"/api/jobs/{job_id}")).json()["status"] == "cancelled"


@pytest.mark.anyio
async def test_terminal_jobs_cannot_transition_again(client: httpx.AsyncClient) -> None:
    created = await register(client, "https://github.com/acme/new-service")
    job_id = UUID(created["job"]["id"])
    job_store = app.state.stores.jobs
    job_store._created_at_monotonic[job_id] -= job_store.duration_seconds
    completed = await client.get(f"/api/jobs/{job_id}")
    assert completed.json()["status"] == "completed"
    invalid = await client.post(f"/api/jobs/{job_id}/cancel")
    assert invalid.status_code == 409
    assert invalid.json()["error"]["code"] == "invalid_job_transition"


@pytest.mark.anyio
async def test_errors_use_the_public_error_envelope(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/repositories", json={"url": "https://example.com/acme/repo"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_repository_url"
    response = await client.get("/api/jobs/11111111-1111-4111-8111-111111111111")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "job_not_found"


def sse_events(body: str) -> list[dict[str, object]]:
    return [json.loads(frame.removeprefix("data: ")) for frame in body.strip().split("\n\n")]


@pytest.mark.anyio
async def test_chat_stream_persists_messages_in_the_active_conversation(client: httpx.AsyncClient) -> None:
    workspace = await client.get("/api/repositories/acme/checkout-service/workspace")
    payload = workspace.json()
    response = await client.post(
        "/api/chat/stream",
        json={"repository_id": payload["repository"]["id"], "conversation_id": payload["conversation"]["id"], "question": "How does checkout work?"},
    )
    events = sse_events(response.text)
    assert [event["type"] for event in events] == ["message.started", "message.delta", "message.delta", "message.completed"]
    refreshed = await client.get("/api/repositories/acme/checkout-service/workspace")
    assert len(refreshed.json()["messages"]) == len(payload["messages"]) + 2
