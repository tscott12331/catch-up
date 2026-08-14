from __future__ import annotations

import io
import json
import logging
from uuid import UUID

import httpx
import pytest

from catch_up.api import app as api_module
from catch_up.application import indexing as indexing_module
from catch_up.observability import JsonFormatter


def capture(logger: logging.Logger) -> tuple[io.StringIO, logging.Handler, int]:
    output = io.StringIO()
    handler = logging.StreamHandler(output)
    handler.setFormatter(JsonFormatter())
    original_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return output, handler, original_level


@pytest.mark.anyio
async def test_request_logs_are_correlated_and_exclude_source_content(client: httpx.AsyncClient) -> None:
    output, handler, original_level = capture(api_module.logger)
    try:
        response = await client.get(
            "/api/repositories/acme/checkout-service/files?path=src/api/checkout.ts",
            headers={"X-Request-ID": "correlation-123"},
        )
        assert response.headers["X-Request-ID"] == "correlation-123"
        records = [json.loads(line) for line in output.getvalue().splitlines()]
        request_record = next(record for record in records if record["event"] == "request_completed")
        assert request_record["route"] == "/api/repositories/{owner}/{repo}/files"
        assert request_record["repository_id"]
        assert "export async function" not in output.getvalue()
        assert "checkout.ts" not in output.getvalue()
    finally:
        api_module.logger.removeHandler(handler)
        api_module.logger.setLevel(original_level)


@pytest.mark.anyio
async def test_invalid_request_id_is_replaced_and_question_is_not_logged(client: httpx.AsyncClient) -> None:
    output, handler, original_level = capture(api_module.logger)
    try:
        workspace = (await client.get("/api/repositories/acme/checkout-service/workspace")).json()
        response = await client.post(
            "/api/chat/stream",
            json={"repository_id": workspace["repository"]["id"], "conversation_id": workspace["conversation"]["id"], "question": "private question"},
            headers={"X-Request-ID": "bad request id with spaces"},
        )
        assert UUID(response.headers["X-Request-ID"]).version == 4
        terminal = next(json.loads(line) for line in output.getvalue().splitlines() if "chat_stream_completed" in line)
        assert terminal["conversation_id"] == workspace["conversation"]["id"]
        assert "private question" not in output.getvalue()
    finally:
        api_module.logger.removeHandler(handler)
        api_module.logger.setLevel(original_level)


@pytest.mark.anyio
async def test_job_transition_log_inherits_request_id(client: httpx.AsyncClient, runtime, register_repository) -> None:
    output, handler, original_level = capture(indexing_module.logger)
    try:
        created = await register_repository("https://github.com/acme/logged-service")
        runtime.clock.advance(10)
        response = await client.get(f"/api/jobs/{created['job']['id']}", headers={"X-Request-ID": "job-log-123"})
        assert response.status_code == 200
        transition = next(json.loads(line) for line in output.getvalue().splitlines() if "indexing_job_transition" in line)
        assert transition["request_id"] == "job-log-123"
        assert transition["job_id"] == created["job"]["id"]
    finally:
        indexing_module.logger.removeHandler(handler)
        indexing_module.logger.setLevel(original_level)
