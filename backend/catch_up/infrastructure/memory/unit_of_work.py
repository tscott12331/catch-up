"""Transactional in-memory unit of work for local and test environments."""

from __future__ import annotations

from copy import deepcopy
from threading import RLock
from types import TracebackType

from .repositories import (
    InMemoryConversationRepository,
    InMemoryJobRepository,
    InMemoryMessageRepository,
    InMemoryPassageRepository,
    InMemoryRepositoryRepository,
    MemoryState,
)


class InMemoryDatabase:
    """Shared committed state used by short-lived units of work."""

    def __init__(self) -> None:
        self._state = MemoryState()
        self._lock = RLock()

    def uow_factory(self) -> InMemoryUnitOfWorkFactory:
        return InMemoryUnitOfWorkFactory(self)


class InMemoryUnitOfWork:
    """Isolate changes until commit and discard uncommitted work on exit."""

    repositories: InMemoryRepositoryRepository
    conversations: InMemoryConversationRepository
    messages: InMemoryMessageRepository
    passages: InMemoryPassageRepository
    jobs: InMemoryJobRepository

    def __init__(self, database: InMemoryDatabase) -> None:
        self._database = database
        self._state: MemoryState | None = None
        self._committed_state: MemoryState | None = None
        self._active = False

    def __enter__(self) -> InMemoryUnitOfWork:
        if self._active:
            raise RuntimeError("This unit of work is already active.")
        self._database._lock.acquire()
        self._active = True
        self._committed_state = None
        self._state = deepcopy(self._database._state)
        self.repositories = InMemoryRepositoryRepository(self._state)
        self.conversations = InMemoryConversationRepository(self._state)
        self.messages = InMemoryMessageRepository(self._state)
        self.passages = InMemoryPassageRepository(self._state)
        self.jobs = InMemoryJobRepository(self._state)
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            if exception_type is None and self._committed_state is not None:
                self._database._state = self._committed_state
        finally:
            self._state = None
            self._committed_state = None
            self._active = False
            self._database._lock.release()

    def commit(self) -> None:
        self._committed_state = deepcopy(self._require_active())

    def rollback(self) -> None:
        self._require_active()
        self._committed_state = None

    def _require_active(self) -> MemoryState:
        if not self._active or self._state is None:
            raise RuntimeError("The unit of work is not active.")
        return self._state


class InMemoryUnitOfWorkFactory:
    def __init__(self, database: InMemoryDatabase) -> None:
        self._database = database

    def __call__(self) -> InMemoryUnitOfWork:
        return InMemoryUnitOfWork(self._database)
