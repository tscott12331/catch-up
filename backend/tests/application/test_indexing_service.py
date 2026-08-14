from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from catch_up.application.errors import InvalidJobTransition, JobNotFound, RepositoryNotFound, RepositoryNotReady
from catch_up.application.indexing import IndexingService
from catch_up.domain.repository import Repository
from catch_up.infrastructure.demo.indexing import DemoIndexingLifecycle
from catch_up.infrastructure.memory import InMemoryDatabase


@dataclass
class FakeClock:
    now: datetime = datetime(2026, 8, 10, tzinfo=timezone.utc)
    elapsed: float = 100.0

    def utc_now(self) -> datetime:
        return self.now

    def monotonic(self) -> float:
        return self.elapsed

    def advance(self, seconds: float) -> None:
        self.elapsed += seconds
        self.now += timedelta(seconds=seconds)


def build_service(duration_seconds: float = 10.0) -> tuple[IndexingService, FakeClock, InMemoryDatabase, UUID]:
    clock = FakeClock()
    database = InMemoryDatabase()
    repository = Repository(
        source_url="https://github.com/acme/service",
        owner="acme",
        name="service",
        default_branch="main",
        indexed_revision="abc123",
    )
    with database.uow_factory()() as uow:
        uow.repositories.add(repository)
        uow.commit()
    lifecycle = DemoIndexingLifecycle(clock, duration_seconds=duration_seconds)
    return IndexingService(database.uow_factory(), lifecycle, clock), clock, database, repository.id


def test_start_and_get_advance_with_an_injected_clock() -> None:
    service, clock, _, repository_id = build_service()

    queued = service.start(repository_id)
    assert queued.status == queued.stage == "queued"
    assert queued.progress == 0
    assert service.get(queued.id) == queued

    clock.advance(4)
    indexing = service.get(queued.id)
    assert indexing.status == "indexing"
    assert indexing.stage == "parsing"
    assert indexing.progress == 40
    assert indexing.started_at == clock.now

    clock.advance(6)
    completed = service.get(queued.id)
    assert completed.status == completed.stage == "completed"
    assert completed.progress == 100
    assert completed.completed_at == clock.now


def test_progress_never_moves_backwards_when_the_clock_does() -> None:
    service, clock, _, repository_id = build_service()
    job = service.start(repository_id)
    clock.advance(7)
    progressed = service.get(job.id)

    clock.elapsed -= 5

    assert service.get(job.id).progress == progressed.progress


def test_current_returns_the_latest_job_and_advances_it() -> None:
    service, clock, _, repository_id = build_service()
    first = service.start(repository_id)
    second = service.start(repository_id)
    clock.advance(5)

    current = service.current(repository_id)

    assert current.id == second.id
    assert current.progress == 50
    assert service.get(first.id).progress == 50


def test_cancel_is_terminal_and_persisted_without_private_store_mutation() -> None:
    service, clock, _, repository_id = build_service()
    job = service.start(repository_id)
    clock.advance(2)

    cancelled = service.cancel(job.id)

    assert cancelled.status == cancelled.stage == "cancelled"
    assert cancelled.progress == 20
    assert cancelled.completed_at == clock.now
    assert service.get(job.id) == cancelled
    with pytest.raises(InvalidJobTransition):
        service.cancel(job.id)


def test_completed_jobs_cannot_be_cancelled() -> None:
    service, clock, database, repository_id = build_service()
    job = service.start(repository_id)
    clock.advance(10)

    with pytest.raises(InvalidJobTransition):
        service.cancel(job.id)

    with database.uow_factory()() as uow:
        persisted = uow.jobs.get(job.id)
    assert persisted is not None
    assert persisted.status == "completed"


def test_missing_entities_raise_typed_application_errors() -> None:
    service, _, _, repository_id = build_service()

    with pytest.raises(JobNotFound):
        service.get(uuid4())
    with pytest.raises(JobNotFound):
        service.cancel(uuid4())
    with pytest.raises(RepositoryNotFound):
        service.start(uuid4())
    with pytest.raises(RepositoryNotReady):
        service.current(repository_id)


def test_lifecycle_rejects_non_positive_duration() -> None:
    with pytest.raises(ValueError, match="positive"):
        DemoIndexingLifecycle(FakeClock(), duration_seconds=0)
