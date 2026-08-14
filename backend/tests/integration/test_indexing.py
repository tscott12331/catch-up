from __future__ import annotations

import httpx
import pytest


@pytest.mark.anyio
async def test_retry_becomes_current_job(client: httpx.AsyncClient, register_repository) -> None:
    created = await register_repository("https://github.com/acme/new-service")
    retry = await client.post(f"/api/repositories/{created['repository']['id']}/indexing-jobs")
    assert retry.status_code == 202
    assert retry.json()["id"] != created["job"]["id"]
    workspace = await client.get("/api/repositories/acme/new-service/workspace")
    assert workspace.json()["job"]["id"] == retry.json()["id"]


@pytest.mark.anyio
async def test_cancel_and_terminal_transition_rules(client: httpx.AsyncClient, runtime, register_repository) -> None:
    cancelled = await register_repository("https://github.com/acme/cancelled")
    response = await client.post(f"/api/jobs/{cancelled['job']['id']}/cancel")
    assert response.json()["status"] == response.json()["stage"] == "cancelled"
    assert (await client.get(f"/api/jobs/{cancelled['job']['id']}")).json()["status"] == "cancelled"

    completed = await register_repository("https://github.com/acme/completed")
    runtime.clock.advance(10)
    assert (await client.get(f"/api/jobs/{completed['job']['id']}")).json()["status"] == "completed"
    invalid = await client.post(f"/api/jobs/{completed['job']['id']}/cancel")
    assert invalid.status_code == 409
    assert invalid.json()["error"]["code"] == "invalid_job_transition"
