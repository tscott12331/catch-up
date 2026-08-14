from __future__ import annotations

import httpx
import pytest


@pytest.mark.anyio
async def test_health_and_readiness_report_constructed_services(client: httpx.AsyncClient, runtime) -> None:
    assert (await client.get("/health")).json() == {"status": "ok", "service": "catch-up-backend"}
    assert (await client.get("/ready")).json() == {"status": "ready", "service": "catch-up-backend"}
    services = runtime.app.state.services
    runtime.app.state.services = None
    response = await client.get("/ready")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "not_ready"
    runtime.app.state.services = services


@pytest.mark.anyio
async def test_browser_reset_route_is_unavailable_outside_test(client: httpx.AsyncClient) -> None:
    response = await client.post("/__test/reset")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.anyio
async def test_test_reset_replaces_the_entire_service_container(runtime_factory) -> None:
    runtime = runtime_factory(environment="test")
    original = runtime.app.state.services
    transport = httpx.ASGITransport(app=runtime.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        assert (await client.post("/__test/reset")).status_code == 204
        assert runtime.app.state.services is not original
        assert (await client.get("/api/repositories/acme/checkout-service/workspace")).status_code == 200
