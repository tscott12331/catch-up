from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from catch_up.bootstrap import build_app
from catch_up.settings import load_settings


class MutableClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 1, 1, tzinfo=UTC)
        self.elapsed = 0.0

    def utc_now(self) -> datetime:
        return self.now

    def monotonic(self) -> float:
        return self.elapsed

    def advance(self, seconds: float) -> None:
        self.elapsed += seconds
        self.now += timedelta(seconds=seconds)


class ImmediateSleeper:
    async def sleep(self, delay_seconds: float) -> None:
        del delay_seconds


@dataclass(slots=True)
class ApiRuntime:
    app: FastAPI
    clock: MutableClock


@pytest.fixture
def runtime_factory() -> Callable[..., ApiRuntime]:
    def create(*, environment: str = "development", duration_seconds: float = 10) -> ApiRuntime:
        settings = load_settings(
            {
                "ENVIRONMENT": environment,
                "DEMO_JOB_DURATION_SECONDS": str(duration_seconds),
            }
        )
        clock = MutableClock()
        return ApiRuntime(build_app(settings, clock=clock, sleeper=ImmediateSleeper()), clock)

    return create


@pytest.fixture
def runtime(runtime_factory: Callable[..., ApiRuntime]) -> ApiRuntime:
    return runtime_factory()


@pytest.fixture
async def client(runtime: ApiRuntime) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=runtime.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client


@pytest.fixture
def register_repository(client: httpx.AsyncClient) -> Callable[..., Any]:
    async def register(url: str = "https://github.com/acme/checkout-service") -> dict[str, Any]:
        response = await client.post("/api/repositories", json={"url": url})
        assert response.status_code == 202
        return response.json()

    return register


@pytest.fixture
def parse_sse_events() -> Callable[[str], list[dict[str, Any]]]:
    def parse(body: str) -> list[dict[str, Any]]:
        return [json.loads(frame.removeprefix("data: ")) for frame in body.strip().split("\n\n")]

    return parse


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
