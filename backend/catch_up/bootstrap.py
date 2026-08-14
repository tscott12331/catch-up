"""Composition root for production and deterministic test applications."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime

import uvicorn
from fastapi import FastAPI

from .api.app import ApplicationServices, create_app
from .application.chat import ChatService
from .application.indexing import IndexingService
from .application.ports import Clock, Sleeper
from .application.repositories import ConversationService, RepositoryService
from .application.workspace import FileService, WorkspaceService
from .infrastructure.demo.answering import DemoAnswerStreamer
from .infrastructure.demo.content import DemoRepositoryContentSource
from .infrastructure.demo.indexing import DemoIndexingLifecycle
from .infrastructure.demo.seeding import seed_demo_repository
from .infrastructure.memory import InMemoryDatabase
from .observability import configure_json_logging
from .settings import Settings, load_settings


logger = logging.getLogger(__name__)


class SystemClock:
    def utc_now(self) -> datetime:
        return datetime.now(UTC)

    def monotonic(self) -> float:
        return time.monotonic()


class AsyncioSleeper:
    async def sleep(self, delay_seconds: float) -> None:
        await asyncio.sleep(delay_seconds)


def build_services(
    settings: Settings,
    *,
    clock: Clock | None = None,
    sleeper: Sleeper | None = None,
    seed: bool = True,
) -> ApplicationServices:
    service_clock = clock or SystemClock()
    service_sleeper = sleeper or AsyncioSleeper()
    database = InMemoryDatabase()
    uow_factory = database.uow_factory()
    content = DemoRepositoryContentSource()
    lifecycle = DemoIndexingLifecycle(service_clock, duration_seconds=settings.demo_job_duration_seconds)
    services = ApplicationServices(
        repositories=RepositoryService(uow_factory, content),
        conversations=ConversationService(uow_factory),
        indexing=IndexingService(uow_factory, lifecycle, service_clock),
        workspaces=WorkspaceService(uow_factory, content),
        files=FileService(uow_factory, content),
        chat=ChatService(uow_factory, DemoAnswerStreamer(service_sleeper), service_clock),
    )
    if seed:
        seeded = seed_demo_repository(uow_factory, content)
        services.indexing.track(seeded.job)
    return services


def build_app(
    settings: Settings,
    *,
    clock: Clock | None = None,
    sleeper: Sleeper | None = None,
    seed: bool = True,
) -> FastAPI:
    def service_factory() -> ApplicationServices:
        return build_services(settings, clock=clock, sleeper=sleeper, seed=seed)

    return create_app(settings, service_factory(), service_factory=service_factory)


def main(settings: Settings | None = None) -> None:
    runtime_settings = settings or load_settings()
    configure_json_logging(runtime_settings.log_level)
    logger.info("Backend starting", extra={"event": "backend_starting", "environment": runtime_settings.environment})
    uvicorn.run(
        build_app(runtime_settings),
        host=runtime_settings.host,
        port=runtime_settings.port,
        log_config=None,
        access_log=False,
    )


__all__ = ["AsyncioSleeper", "SystemClock", "build_app", "build_services", "main"]

