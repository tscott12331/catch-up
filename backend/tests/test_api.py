from __future__ import annotations

import json

import httpx
import pytest

from main import JOB_DURATION_SECONDS, JOBS, app


@pytest.fixture(autouse=True)
def reset_jobs() -> None:
    JOBS.clear()


@pytest.fixture
async def client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client


@pytest.mark.anyio
async def test_health_reports_service_metadata(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "catch-up-backend", "phase": 2}


@pytest.mark.anyio
async def test_creating_a_repository_returns_identity_and_indexing_job(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/repositories", json={"url": "https://github.com/acme/checkout-service"})

    assert response.status_code == 202
    body = response.json()
    assert body["repository"] == {
        "id": "repo_acme_checkout-service",
        "owner": "acme",
        "name": "checkout-service",
        "url": "https://github.com/acme/checkout-service",
        "default_branch": "main",
    }
    assert body["job"]["id"] == "job_acme_checkout-service"
    assert body["job"]["status"] in {"queued", "indexing"}
    assert 0 <= body["job"]["progress"] < 100


@pytest.mark.anyio
async def test_job_progress_reaches_completed(client: httpx.AsyncClient) -> None:
    created = await client.post("/api/repositories", json={"url": "https://github.com/acme/checkout-service"})
    job_id = created.json()["job"]["id"]
    JOBS[job_id].created_at -= JOB_DURATION_SECONDS

    response = await client.get(f"/api/jobs/{job_id}")

    assert response.status_code == 200
    assert response.json() == {"id": job_id, "status": "completed", "progress": 100}


@pytest.mark.anyio
async def test_workspace_returns_repository_content_and_current_job(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/repositories/acme/checkout-service/workspace")

    assert response.status_code == 200
    body = response.json()
    assert body["repository"]["id"] == "repo_acme_checkout-service"
    assert body["selected_file"] == "src/api/checkout.ts"
    assert body["tree"][0]["name"] == "src"
    assert body["messages"][0]["id"] == "message_welcome"
    assert body["job"]["id"] == "job_acme_checkout-service"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("method", "path", "payload", "status", "code"),
    [
        ("post", "/api/repositories", {"url": "https://example.com/acme/repo"}, 422, "invalid_repository_url"),
        ("get", "/api/jobs/missing", None, 404, "job_not_found"),
        ("get", "/api/repositories/acme/checkout-service/files?path=../secret", None, 404, "file_not_found"),
        ("post", "/api/chat/stream", {"repository_id": "", "question": "hello"}, 422, "repository_required"),
    ],
)
async def test_errors_use_the_public_error_envelope(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    payload: dict[str, str] | None,
    status: int,
    code: str,
) -> None:
    response = await client.request(method, path, json=payload)

    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert isinstance(response.json()["error"]["message"], str)


def sse_events(body: str) -> list[dict[str, object]]:
    return [json.loads(frame.removeprefix("data: ")) for frame in body.strip().split("\n\n")]


@pytest.mark.anyio
async def test_chat_stream_emits_started_delta_and_completed_events(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/chat/stream", json={"repository_id": "repo_acme_checkout-service", "question": "How does checkout work?"})

    events = sse_events(response.text)
    assert response.headers["content-type"].startswith("text/event-stream")
    assert [event["type"] for event in events] == ["message.started", "message.delta", "message.delta", "message.completed"]
    assert isinstance(events[0]["message_id"], str)
    assert events[-1]["citations"] == [
        {"file": "src/api/checkout.ts", "start_line": 5, "end_line": 20},
        {"file": "src/services/payment-service.ts", "start_line": 1, "end_line": 13},
    ]


@pytest.mark.anyio
async def test_chat_stream_emits_error_event(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/chat/stream", json={"repository_id": "repo_acme_checkout-service", "question": "__stream_error__"})

    events = sse_events(response.text)
    assert [event["type"] for event in events] == ["message.started", "message.error"]
    assert events[-1] == {
        "type": "message.error",
        "code": "stream_failed",
        "message": "The demo stream failed before completion.",
    }
