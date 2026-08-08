"""Small, replaceable persistence boundary for the Phase 1 demo."""

from __future__ import annotations

import time
import logging
from collections.abc import Iterable
from typing import Protocol
from uuid import UUID

from models.api.chat_sse import Message
from models.chat import Conversation
from models.jobs import IndexingJob
from models.models import utc_now
from models.repository import Repository, SourcePassage

logger = logging.getLogger(__name__)


class RepositoryStore(Protocol):
    def add(self, repository: Repository) -> Repository: ...
    def get(self, repository_id: UUID) -> Repository | None: ...
    def get_by_route(self, owner: str, name: str) -> Repository | None: ...


class ConversationStore(Protocol):
    def add(self, conversation: Conversation, *, active: bool = True) -> Conversation: ...
    def get(self, conversation_id: UUID) -> Conversation | None: ...
    def get_active(self, repository_id: UUID) -> Conversation | None: ...


class MessageStore(Protocol):
    def add(self, message: Message) -> Message: ...
    def get(self, message_id: UUID) -> Message | None: ...
    def replace(self, message: Message) -> Message: ...
    def list_for_conversation(self, conversation_id: UUID) -> list[Message]: ...


class PassageStore(Protocol):
    def add_many(self, passages: Iterable[SourcePassage]) -> None: ...
    def list_for_repository(self, repository_id: UUID) -> list[SourcePassage]: ...


class JobStore(Protocol):
    def add(self, job: IndexingJob) -> IndexingJob: ...
    def get(self, job_id: UUID) -> IndexingJob | None: ...
    def current_for_repository(self, repository_id: UUID) -> IndexingJob | None: ...
    def advance(self, job_id: UUID) -> IndexingJob | None: ...
    def cancel(self, job_id: UUID) -> IndexingJob | None: ...


class InvalidJobTransition(ValueError):
    """Raised when a terminal job is asked to transition again."""


class InMemoryRepositoryStore:
    def __init__(self) -> None:
        self._by_id: dict[UUID, Repository] = {}
        self._by_route: dict[tuple[str, str], UUID] = {}

    def add(self, repository: Repository) -> Repository:
        self._by_id[repository.id] = repository
        self._by_route[(repository.owner, repository.name)] = repository.id
        return repository

    def get(self, repository_id: UUID) -> Repository | None:
        return self._by_id.get(repository_id)

    def get_by_route(self, owner: str, name: str) -> Repository | None:
        repository_id = self._by_route.get((owner, name))
        return self.get(repository_id) if repository_id else None


class InMemoryConversationStore:
    def __init__(self) -> None:
        self._items: dict[UUID, Conversation] = {}
        self._active_by_repository: dict[UUID, UUID] = {}

    def add(self, conversation: Conversation, *, active: bool = True) -> Conversation:
        self._items[conversation.id] = conversation
        if active:
            self._active_by_repository[conversation.repository_id] = conversation.id
        return conversation

    def get(self, conversation_id: UUID) -> Conversation | None:
        return self._items.get(conversation_id)

    def get_active(self, repository_id: UUID) -> Conversation | None:
        conversation_id = self._active_by_repository.get(repository_id)
        return self.get(conversation_id) if conversation_id else None


class InMemoryMessageStore:
    def __init__(self) -> None:
        self._items: dict[UUID, list[Message]] = {}
        self._by_id: dict[UUID, Message] = {}

    def add(self, message: Message) -> Message:
        if message.id in self._by_id:
            raise ValueError("A message with this id already exists.")
        self._items.setdefault(message.conversation_id, []).append(message)
        self._by_id[message.id] = message
        return message

    def get(self, message_id: UUID) -> Message | None:
        return self._by_id.get(message_id)

    def replace(self, message: Message) -> Message:
        existing = self._by_id.get(message.id)
        if existing is None:
            raise ValueError("Cannot replace a message that does not exist.")
        if existing.conversation_id != message.conversation_id:
            raise ValueError("A message cannot move to another conversation.")
        messages = self._items[message.conversation_id]
        self._items[message.conversation_id] = [message if item.id == message.id else item for item in messages]
        self._by_id[message.id] = message
        return message

    def list_for_conversation(self, conversation_id: UUID) -> list[Message]:
        return list(self._items.get(conversation_id, []))


class InMemoryPassageStore:
    def __init__(self) -> None:
        self._items: dict[UUID, list[SourcePassage]] = {}

    def add_many(self, passages: Iterable[SourcePassage]) -> None:
        for passage in passages:
            self._items.setdefault(passage.repository_id, []).append(passage)

    def list_for_repository(self, repository_id: UUID) -> list[SourcePassage]:
        return list(self._items.get(repository_id, []))


class InMemoryJobStore:
    """A deterministic clock-driven job store with one-way lifecycle changes."""

    _terminal = {"completed", "failed", "cancelled"}

    def __init__(self, duration_seconds: float = 1.2) -> None:
        self.duration_seconds = duration_seconds
        self._items: dict[UUID, IndexingJob] = {}
        self._created_at_monotonic: dict[UUID, float] = {}
        self._by_repository: dict[UUID, list[UUID]] = {}

    def add(self, job: IndexingJob) -> IndexingJob:
        self._items[job.id] = job
        self._created_at_monotonic[job.id] = time.monotonic()
        self._by_repository.setdefault(job.repository_id, []).append(job.id)
        return job

    def get(self, job_id: UUID) -> IndexingJob | None:
        return self._items.get(job_id)

    def current_for_repository(self, repository_id: UUID) -> IndexingJob | None:
        job_ids = self._by_repository.get(repository_id, [])
        return self.get(job_ids[-1]) if job_ids else None

    def advance(self, job_id: UUID) -> IndexingJob | None:
        job = self.get(job_id)
        if job is None or job.status in self._terminal:
            return job
        elapsed = max(0.0, time.monotonic() - self._created_at_monotonic[job_id])
        progress = min(100, int((elapsed / self.duration_seconds) * 100))
        if progress >= 100:
            if job.status == "queued":
                job = self._replace(job, status="indexing", stage="indexing", progress=max(1, job.progress))
            return self._replace(job, status="completed", stage="completed", progress=100, completed=True)
        if progress > job.progress:
            return self._replace(job, status="indexing", stage="indexing", progress=progress, started=True)
        return job

    def cancel(self, job_id: UUID) -> IndexingJob | None:
        job = self.advance(job_id)
        if job is None:
            return None
        if job.status in self._terminal:
            raise InvalidJobTransition(f"Cannot cancel a {job.status} job.")
        return self._replace(job, status="cancelled", stage="cancelled", completed=True)

    def _replace(
        self,
        job: IndexingJob,
        *,
        status: str,
        stage: str,
        progress: int | None = None,
        started: bool = False,
        completed: bool = False,
    ) -> IndexingJob:
        if job.status in self._terminal:
            raise InvalidJobTransition(f"Cannot transition a {job.status} job.")
        now = utc_now()
        updated = job.model_copy(
            update={
                "status": status,
                "stage": stage,
                "progress": max(job.progress, progress if progress is not None else job.progress),
                "updated_at": now,
                "started_at": job.started_at or (job.created_at if started or status != "queued" else None),
                "completed_at": now if completed else job.completed_at,
            }
        )
        self._items[job.id] = updated
        logger.info(
            "Indexing job transitioned",
            extra={
                "event": "indexing_job_transition",
                "job_id": str(updated.id),
                "repository_id": str(updated.repository_id),
            },
        )
        return updated


class InMemoryStores:
    def __init__(self, *, job_duration_seconds: float = 1.2) -> None:
        self.repositories: RepositoryStore = InMemoryRepositoryStore()
        self.conversations: ConversationStore = InMemoryConversationStore()
        self.messages: MessageStore = InMemoryMessageStore()
        self.passages: PassageStore = InMemoryPassageStore()
        self.jobs: JobStore = InMemoryJobStore(duration_seconds=job_duration_seconds)
