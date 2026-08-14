from __future__ import annotations

import httpx
import pytest


@pytest.mark.anyio
async def test_errors_use_public_envelope(client: httpx.AsyncClient) -> None:
    invalid = await client.post("/api/repositories", json={"url": "https://example.com/acme/repo"})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "invalid_repository_url"
    missing = await client.get("/api/jobs/11111111-1111-4111-8111-111111111111")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "job_not_found"
    malformed = await client.post("/api/repositories", content="{", headers={"Content-Type": "application/json"})
    assert malformed.status_code == 400
    assert malformed.json()["error"]["code"] == "invalid_json"


@pytest.mark.anyio
async def test_unexpected_errors_use_safe_envelope(
    runtime,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(source_url: str):
        del source_url
        raise RuntimeError("database password: do-not-leak")

    monkeypatch.setattr(runtime.app.state.services.repositories, "register", fail)
    transport = httpx.ASGITransport(app=runtime.app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as safe_client:
        response = await safe_client.post("/api/repositories", json={"url": "https://github.com/acme/service"})
    assert response.status_code == 500
    assert response.json() == {"error": {"code": "internal_error", "message": "The server could not complete the request."}}
    assert "password" not in response.text
