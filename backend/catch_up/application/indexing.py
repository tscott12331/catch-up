"""Indexing lifecycle use cases."""

from __future__ import annotations

import logging
from typing import Protocol
from uuid import UUID

from .errors import InvalidJobTransition, JobNotFound, RepositoryNotFound, RepositoryNotReady
from .ports import Clock, UnitOfWorkFactory
from ..domain.jobs import IndexingJob


logger = logging.getLogger(__name__)


class IndexingLifecycle(Protocol):
    def track(self, job: IndexingJob) -> None: ...
    def advance(self, job: IndexingJob) -> IndexingJob: ...
    def cancel(self, job: IndexingJob) -> IndexingJob: ...


class IndexingService:
    def __init__(self, uow_factory: UnitOfWorkFactory, lifecycle: IndexingLifecycle, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._lifecycle = lifecycle
        self._clock = clock

    def track(self, job: IndexingJob) -> None:
        self._lifecycle.track(job)

    def start(self, repository_id: UUID) -> IndexingJob:
        now = self._clock.utc_now()
        with self._uow_factory() as uow:
            if uow.repositories.get(repository_id) is None:
                raise RepositoryNotFound()
            job = uow.jobs.add(
                IndexingJob(
                    repository_id=repository_id,
                    status="queued",
                    stage="queued",
                    progress=0,
                    created_at=now,
                    updated_at=now,
                )
            )
            uow.commit()
        self._lifecycle.track(job)
        return job

    def get(self, job_id: UUID) -> IndexingJob:
        with self._uow_factory() as uow:
            job = uow.jobs.get(job_id)
            if job is None:
                raise JobNotFound()
            advanced = self._lifecycle.advance(job)
            if advanced != job:
                advanced = uow.jobs.save(advanced)
                uow.commit()
                self._log_transition(advanced)
            return advanced

    def current(self, repository_id: UUID) -> IndexingJob:
        with self._uow_factory() as uow:
            if uow.repositories.get(repository_id) is None:
                raise RepositoryNotFound()
            job = uow.jobs.current_for_repository(repository_id)
            if job is None:
                raise RepositoryNotReady()
        return self.get(job.id)

    def cancel(self, job_id: UUID) -> IndexingJob:
        with self._uow_factory() as uow:
            job = uow.jobs.get(job_id)
            if job is None:
                raise JobNotFound()
            advanced = self._lifecycle.advance(job)
            if advanced.status in {"completed", "failed", "cancelled"}:
                if advanced != job:
                    uow.jobs.save(advanced)
                    uow.commit()
            else:
                cancelled = uow.jobs.save(self._lifecycle.cancel(advanced))
                uow.commit()
                self._log_transition(cancelled)
                return cancelled
        raise InvalidJobTransition()

    @staticmethod
    def _log_transition(job: IndexingJob) -> None:
        logger.info(
            "Indexing job transitioned",
            extra={
                "event": "indexing_job_transition",
                "job_id": str(job.id),
                "repository_id": str(job.repository_id),
            },
        )
