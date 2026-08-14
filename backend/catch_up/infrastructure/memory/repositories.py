"""In-memory implementations of the application persistence ports."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from uuid import UUID

from ...domain.chat import Conversation
from ...domain.jobs import IndexingJob
from ...domain.messages import Message
from ...domain.repository import Repository, SourcePassage


def _copy[ModelT: Repository | Conversation | Message | SourcePassage | IndexingJob](model: ModelT) -> ModelT:
    return model.model_copy(deep=True)


@dataclass
class MemoryState:
    repositories: dict[UUID, Repository] = field(default_factory=dict)
    repository_routes: dict[tuple[str, str], UUID] = field(default_factory=dict)
    conversations: dict[UUID, Conversation] = field(default_factory=dict)
    active_conversations: dict[UUID, UUID] = field(default_factory=dict)
    messages: dict[UUID, Message] = field(default_factory=dict)
    conversation_messages: dict[UUID, list[UUID]] = field(default_factory=dict)
    passages: dict[UUID, list[SourcePassage]] = field(default_factory=dict)
    jobs: dict[UUID, IndexingJob] = field(default_factory=dict)
    repository_jobs: dict[UUID, list[UUID]] = field(default_factory=dict)


class InMemoryRepositoryRepository:
    def __init__(self, state: MemoryState) -> None:
        self._state = state

    def add(self, repository: Repository) -> Repository:
        route = (repository.owner, repository.name)
        if repository.id in self._state.repositories:
            raise ValueError("A repository with this id already exists.")
        if route in self._state.repository_routes:
            raise ValueError("A repository with this route already exists.")
        stored = _copy(repository)
        self._state.repositories[stored.id] = stored
        self._state.repository_routes[route] = stored.id
        return _copy(stored)

    def get(self, repository_id: UUID) -> Repository | None:
        repository = self._state.repositories.get(repository_id)
        return _copy(repository) if repository is not None else None

    def get_by_route(self, owner: str, name: str) -> Repository | None:
        repository_id = self._state.repository_routes.get((owner, name))
        return self.get(repository_id) if repository_id is not None else None


class InMemoryConversationRepository:
    def __init__(self, state: MemoryState) -> None:
        self._state = state

    def add(self, conversation: Conversation, *, active: bool = True) -> Conversation:
        if conversation.id in self._state.conversations:
            raise ValueError("A conversation with this id already exists.")
        stored = _copy(conversation)
        self._state.conversations[stored.id] = stored
        if active:
            self._state.active_conversations[stored.repository_id] = stored.id
        return _copy(stored)

    def get(self, conversation_id: UUID) -> Conversation | None:
        conversation = self._state.conversations.get(conversation_id)
        return _copy(conversation) if conversation is not None else None

    def get_active(self, repository_id: UUID) -> Conversation | None:
        conversation_id = self._state.active_conversations.get(repository_id)
        return self.get(conversation_id) if conversation_id is not None else None


class InMemoryMessageRepository:
    def __init__(self, state: MemoryState) -> None:
        self._state = state

    def add(self, message: Message) -> Message:
        if message.id in self._state.messages:
            raise ValueError("A message with this id already exists.")
        stored = _copy(message)
        self._state.messages[stored.id] = stored
        self._state.conversation_messages.setdefault(stored.conversation_id, []).append(stored.id)
        return _copy(stored)

    def get(self, message_id: UUID) -> Message | None:
        message = self._state.messages.get(message_id)
        return _copy(message) if message is not None else None

    def save(self, message: Message) -> Message:
        existing = self._state.messages.get(message.id)
        if existing is None:
            raise ValueError("Cannot save a message that does not exist.")
        if existing.conversation_id != message.conversation_id:
            raise ValueError("A message cannot move to another conversation.")
        stored = _copy(message)
        self._state.messages[stored.id] = stored
        return _copy(stored)

    def list_for_conversation(self, conversation_id: UUID) -> list[Message]:
        return [_copy(self._state.messages[item_id]) for item_id in self._state.conversation_messages.get(conversation_id, [])]


class InMemoryPassageRepository:
    def __init__(self, state: MemoryState) -> None:
        self._state = state

    def add_many(self, passages: Iterable[SourcePassage]) -> None:
        for passage in passages:
            self._state.passages.setdefault(passage.repository_id, []).append(_copy(passage))

    def list_for_repository(self, repository_id: UUID) -> list[SourcePassage]:
        return [_copy(passage) for passage in self._state.passages.get(repository_id, [])]


class InMemoryJobRepository:
    def __init__(self, state: MemoryState) -> None:
        self._state = state

    def add(self, job: IndexingJob) -> IndexingJob:
        if job.id in self._state.jobs:
            raise ValueError("An indexing job with this id already exists.")
        stored = _copy(job)
        self._state.jobs[stored.id] = stored
        self._state.repository_jobs.setdefault(stored.repository_id, []).append(stored.id)
        return _copy(stored)

    def get(self, job_id: UUID) -> IndexingJob | None:
        job = self._state.jobs.get(job_id)
        return _copy(job) if job is not None else None

    def save(self, job: IndexingJob) -> IndexingJob:
        existing = self._state.jobs.get(job.id)
        if existing is None:
            raise ValueError("Cannot save an indexing job that does not exist.")
        if existing.repository_id != job.repository_id:
            raise ValueError("An indexing job cannot move to another repository.")
        stored = _copy(job)
        self._state.jobs[stored.id] = stored
        return _copy(stored)

    def current_for_repository(self, repository_id: UUID) -> IndexingJob | None:
        job_ids = self._state.repository_jobs.get(repository_id, [])
        return self.get(job_ids[-1]) if job_ids else None
