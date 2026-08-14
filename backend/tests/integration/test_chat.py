from __future__ import annotations

import httpx
import pytest


@pytest.mark.anyio
async def test_chat_preflight_rejects_mismatch_and_missing_ids(client: httpx.AsyncClient, register_repository) -> None:
    first = await register_repository("https://github.com/acme/first")
    second = await register_repository("https://github.com/acme/second")
    mismatch = await client.post(
        "/api/chat/stream",
        json={"repository_id": first["repository"]["id"], "conversation_id": second["conversation"]["id"], "question": "Question"},
    )
    assert mismatch.status_code == 409
    assert mismatch.json()["error"]["code"] == "conversation_repository_mismatch"
    missing = await client.post(
        "/api/chat/stream",
        json={"repository_id": first["repository"]["id"], "conversation_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "question": "Question"},
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "conversation_not_found"


@pytest.mark.anyio
async def test_chat_requires_identifiers_and_nonblank_question(client: httpx.AsyncClient) -> None:
    for payload in (
        {"question": "Question"},
        {"repository_id": "11111111-1111-4111-8111-111111111111", "question": "Question"},
        {"conversation_id": "22222222-2222-4222-8222-222222222222", "question": "Question"},
    ):
        response = await client.post("/api/chat/stream", json=payload)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"
    blank = await client.post(
        "/api/chat/stream",
        json={"repository_id": "11111111-1111-4111-8111-111111111111", "conversation_id": "22222222-2222-4222-8222-222222222222", "question": " "},
    )
    assert blank.status_code == 422
    assert blank.json()["error"]["code"] == "question_required"


@pytest.mark.anyio
async def test_chat_stream_persists_messages_and_emits_ordered_events(
    client: httpx.AsyncClient,
    parse_sse_events,
) -> None:
    workspace = (await client.get("/api/repositories/acme/checkout-service/workspace")).json()
    response = await client.post(
        "/api/chat/stream",
        json={"repository_id": workspace["repository"]["id"], "conversation_id": workspace["conversation"]["id"], "question": "How does checkout work?"},
    )
    events = parse_sse_events(response.text)
    assert [event["type"] for event in events] == ["message.started", "message.delta", "message.delta", "message.completed"]
    assert {event["message_id"] for event in events} == {events[0]["message_id"]}
    refreshed = (await client.get("/api/repositories/acme/checkout-service/workspace")).json()
    assert len(refreshed["messages"]) == len(workspace["messages"]) + 2
    assert [message["completion_state"] for message in refreshed["messages"][-2:]] == ["completed", "completed"]


@pytest.mark.anyio
async def test_chat_stream_failure_is_deterministic_and_safe(client: httpx.AsyncClient, parse_sse_events) -> None:
    workspace = (await client.get("/api/repositories/acme/checkout-service/workspace")).json()
    response = await client.post(
        "/api/chat/stream",
        json={"repository_id": workspace["repository"]["id"], "conversation_id": workspace["conversation"]["id"], "question": "__stream_error__"},
    )
    events = parse_sse_events(response.text)
    assert [event["type"] for event in events] == ["message.started", "message.error"]
    assert events[-1]["code"] == "stream_failed"
    assert "demo stream failed" not in response.text
    refreshed = (await client.get("/api/repositories/acme/checkout-service/workspace")).json()
    assert [message["completion_state"] for message in refreshed["messages"][-2:]] == ["completed", "failed"]
