"""Replaceable persistence and time boundaries used by application services."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from ..domain.chat import Conversation
from ..domain.jobs import IndexingJob
from ..domain.messages import Message
from ..domain.repository import Repository, SourcePassage


class RepositoryRepository(Protocol):
    def add(self, repository: Repository) -> Repository: ...
    def get(self, repository_id: UUID) -> Repository | None: ...
    def get_by_route(self, owner: str, name: str) -> Repository | None: ...


class ConversationRepository(Protocol):
    def add(self, conversation: Conversation, *, active: bool = True) -> Conversation: ...
    def get(self, conversation_id: UUID) -> Conversation | None: ...
    def get_active(self, repository_id: UUID) -> Conversation | None: ...


class MessageRepository(Protocol):
    def add(self, message: Message) -> Message: ...
    def get(self, message_id: UUID) -> Message | None: ...
    def save(self, message: Message) -> Message: ...
    def list_for_conversation(self, conversation_id: UUID) -> list[Message]: ...


class PassageRepository(Protocol):
    def add_many(self, passages: Iterable[SourcePassage]) -> None: ...
    def list_for_repository(self, repository_id: UUID) -> list[SourcePassage]: ...


class JobRepository(Protocol):
    def add(self, job: IndexingJob) -> IndexingJob: ...
    def get(self, job_id: UUID) -> IndexingJob | None: ...
    def save(self, job: IndexingJob) -> IndexingJob: ...
    def current_for_repository(self, repository_id: UUID) -> IndexingJob | None: ...


class UnitOfWork(Protocol):
    """Transaction boundary for a complete application operation."""

    repositories: RepositoryRepository
    conversations: ConversationRepository
    messages: MessageRepository
    passages: PassageRepository
    jobs: JobRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...

    def commit(self) -> None: ...
    def rollback(self) -> None: ...


UnitOfWorkFactory = Callable[[], UnitOfWork]


class Clock(Protocol):
    def utc_now(self) -> datetime: ...
    def monotonic(self) -> float: ...


class Sleeper(Protocol):
    async def sleep(self, delay_seconds: float) -> None: ...

