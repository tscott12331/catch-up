"""Deterministic, clock-driven indexing lifecycle for the demo adapter."""

from __future__ import annotations

from uuid import UUID

from ...application.ports import Clock
from ...domain.jobs import IndexingJob, JobStage


class DemoIndexingLifecycle:
    _terminal_statuses = frozenset({"completed", "failed", "cancelled"})
    _stages: tuple[tuple[int, JobStage], ...] = (
        (10, "cloning"),
        (30, "discovering"),
        (55, "parsing"),
        (85, "indexing"),
        (100, "finalizing"),
    )

    def __init__(self, clock: Clock, *, duration_seconds: float = 1.2) -> None:
        if duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive.")
        self._clock = clock
        self._duration_seconds = duration_seconds
        self._started_at: dict[UUID, float] = {}

    def track(self, job: IndexingJob) -> None:
        if job.status not in self._terminal_statuses:
            self._started_at.setdefault(job.id, self._clock.monotonic())

    def advance(self, job: IndexingJob) -> IndexingJob:
        if job.status in self._terminal_statuses:
            return job
        self.track(job)
        elapsed = max(0.0, self._clock.monotonic() - self._started_at[job.id])
        progress = max(job.progress, min(100, int(elapsed / self._duration_seconds * 100)))
        if progress == job.progress and not (progress == 100 and job.status != "completed"):
            return job

        now = self._clock.utc_now()
        if progress >= 100:
            return job.model_copy(
                update={
                    "status": "completed",
                    "stage": "completed",
                    "progress": 100,
                    "updated_at": now,
                    "started_at": job.started_at or job.created_at,
                    "completed_at": now,
                }
            )
        return job.model_copy(
            update={
                "status": "indexing",
                "stage": self._stage_for(progress),
                "progress": progress,
                "updated_at": now,
                "started_at": job.started_at or now,
            }
        )

    def cancel(self, job: IndexingJob) -> IndexingJob:
        now = self._clock.utc_now()
        return job.model_copy(
            update={
                "status": "cancelled",
                "stage": "cancelled",
                "updated_at": now,
                "completed_at": now,
            }
        )

    def _stage_for(self, progress: int) -> JobStage:
        for upper_bound, stage in self._stages:
            if progress < upper_bound:
                return stage
        return "finalizing"
