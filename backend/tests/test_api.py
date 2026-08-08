from __future__ import annotations

import asyncio
import io
import json
import logging
from uuid import UUID

import httpx
import pytest

import main
import stores as stores_module
from main import app, reset_in_memory_stores, stream_demo_answer
from observability import JsonFormatter


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
    assert response.json() == {"status": "ok", "service": "catch-up-backend"}


@pytest.mark.anyio
async def test_readiness_is_independent_of_delivery_phase_and_reports_store_initialization(client: httpx.AsyncClient) -> None:
    assert (await client.get("/ready")).json() == {"status": "ready", "service": "catch-up-backend"}
    app.state.stores = None
    response = await client.get("/ready")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "not_ready"
    reset_in_memory_stores()


@pytest.mark.anyio
async def test_browser_test_reset_route_is_unavailable_outside_the_test_environment(client: httpx.AsyncClient) -> None:
    response = await client.post("/__test/reset")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.anyio
async def test_request_logs_are_json_correlated_and_do_not_include_source_or_questions(client: httpx.AsyncClient) -> None:
    output = io.StringIO()
    handler = logging.StreamHandler(output)
    handler.setFormatter(JsonFormatter())
    main.logger.addHandler(handler)
    main.logger.setLevel(logging.INFO)
    try:
        response = await client.get(
            "/api/repositories/acme/checkout-service/files?path=src/api/checkout.ts",
            headers={"X-Request-ID": "correlation-123"},
        )
        assert response.headers["X-Request-ID"] == "correlation-123"
        records = [json.loads(line) for line in output.getvalue().splitlines()]
        request_record = next(record for record in records if record["event"] == "request_completed")
        assert request_record["request_id"] == "correlation-123"
        assert request_record["method"] == "GET"
        assert request_record["route"] == "/api/repositories/{owner}/{repo}/files"
        assert request_record["status_code"] == 200
        assert isinstance(request_record["duration_ms"], float)
        assert request_record["repository_id"]
        encoded = output.getvalue()
        assert "export async function" not in encoded
        assert "checkout.ts" not in encoded
    finally:
        main.logger.removeHandler(handler)


@pytest.mark.anyio
async def test_invalid_request_id_is_replaced_and_stream_logs_do_not_include_question(client: httpx.AsyncClient) -> None:
    output = io.StringIO()
    handler = logging.StreamHandler(output)
    handler.setFormatter(JsonFormatter())
    main.logger.addHandler(handler)
    main.logger.setLevel(logging.INFO)
    try:
        workspace = (await client.get("/api/repositories/acme/checkout-service/workspace")).json()
        secret_question = "private question that must never reach logs"
        response = await client.post(
            "/api/chat/stream",
            json={"repository_id": workspace["repository"]["id"], "conversation_id": workspace["conversation"]["id"], "question": secret_question},
            headers={"X-Request-ID": "bad request id with spaces"},
        )
        assert response.headers["X-Request-ID"] != "bad request id with spaces"
        assert UUID(response.headers["X-Request-ID"]).version == 4
        records = [json.loads(line) for line in output.getvalue().splitlines()]
        terminal = next(record for record in records if record["event"] == "chat_stream_completed")
        assert terminal["repository_id"] == workspace["repository"]["id"]
        assert terminal["conversation_id"] == workspace["conversation"]["id"]
        assert "private question" not in output.getvalue()
    finally:
        main.logger.removeHandler(handler)


@pytest.mark.anyio
async def test_job_transition_log_inherits_the_request_correlation_id(client: httpx.AsyncClient) -> None:
    output = io.StringIO()
    handler = logging.StreamHandler(output)
    handler.setFormatter(JsonFormatter())
    stores_module.logger.addHandler(handler)
    stores_module.logger.setLevel(logging.INFO)
    try:
        created = await register(client, "https://github.com/acme/logged-service")
        job_id = UUID(created["job"]["id"])
        app.state.stores.jobs._created_at_monotonic[job_id] -= app.state.stores.jobs.duration_seconds
        response = await client.get(f"/api/jobs/{job_id}", headers={"X-Request-ID": "job-log-123"})
        assert response.status_code == 200
        records = [json.loads(line) for line in output.getvalue().splitlines()]
        transition = next(record for record in records if record["event"] == "indexing_job_transition")
        assert transition["request_id"] == "job-log-123"
        assert transition["job_id"] == str(job_id)
        assert transition["repository_id"] == created["repository"]["id"]
    finally:
        stores_module.logger.removeHandler(handler)


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
async def test_chat_requires_both_repository_and_conversation_identifiers(client: httpx.AsyncClient) -> None:
    for payload in (
        {"question": "How does checkout work?"},
        {"repository_id": "11111111-1111-4111-8111-111111111111", "question": "How does checkout work?"},
        {"conversation_id": "22222222-2222-4222-8222-222222222222", "question": "How does checkout work?"},
    ):
        response = await client.post("/api/chat/stream", json=payload)
        assert response.status_code == 422
        assert response.json()["error"] == {"code": "validation_error", "message": "Request validation failed."}


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


@pytest.mark.anyio
async def test_unexpected_errors_use_a_safe_public_envelope(client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(_: str) -> tuple[str, str] | None:
        raise RuntimeError("database password: do-not-leak")

    monkeypatch.setattr(main, "parse_repository_url", fail)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as safe_client:
        response = await safe_client.post("/api/repositories", json={"url": "https://github.com/acme/checkout-service"})
    assert response.status_code == 500
    assert response.json() == {"error": {"code": "internal_error", "message": "The server could not complete the request."}}
    assert "password" not in response.text


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
    assert {event["repository_id"] for event in events} == {payload["repository"]["id"]}
    assert {event["conversation_id"] for event in events} == {payload["conversation"]["id"]}
    assert {event["message_id"] for event in events} == {events[0]["message_id"]}
    assert UUID(events[0]["user_message_id"]).version == 4
    refreshed = await client.get("/api/repositories/acme/checkout-service/workspace")
    assert len(refreshed.json()["messages"]) == len(payload["messages"]) + 2
    assert [message["completion_state"] for message in refreshed.json()["messages"][-2:]] == ["completed", "completed"]


@pytest.mark.anyio
async def test_chat_stream_failure_is_ordered_deterministic_and_safe(client: httpx.AsyncClient) -> None:
    workspace = (await client.get("/api/repositories/acme/checkout-service/workspace")).json()
    response = await client.post(
        "/api/chat/stream",
        json={"repository_id": workspace["repository"]["id"], "conversation_id": workspace["conversation"]["id"], "question": "__stream_error__"},
    )
    events = sse_events(response.text)
    assert [event["type"] for event in events] == ["message.started", "message.error"]
    assert events[-1]["code"] == "stream_failed"
    assert events[-1]["message"] == "The answer stream could not be completed."
    assert "demo stream failed" not in response.text
    refreshed = await client.get("/api/repositories/acme/checkout-service/workspace")
    assert [message["completion_state"] for message in refreshed.json()["messages"][-2:]] == ["completed", "failed"]


@pytest.mark.anyio
async def test_cancelled_stream_persists_a_cancelled_assistant_message() -> None:
    stores = app.state.stores
    repository = stores.repositories.get(UUID("11111111-1111-4111-8111-111111111111"))
    conversation = stores.conversations.get(UUID("22222222-2222-4222-8222-222222222222"))
    assert repository is not None and conversation is not None
    stream = stream_demo_answer(stores, repository, conversation, "How does checkout work?")
    await anext(stream)
    pending = asyncio.create_task(anext(stream))
    await asyncio.sleep(0)
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
    messages = stores.messages.list_for_conversation(conversation.id)
    assert [message.completion_state for message in messages[-2:]] == ["completed", "cancelled"]
