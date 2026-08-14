"""Workspace and source-file query services."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import unquote
from uuid import UUID

from ..domain.chat import Conversation
from ..domain.jobs import IndexingJob
from ..domain.messages import Message
from ..domain.repository import Repository, TreeNode
from .content import RepositoryContentSource
from .errors import FileNotFound, RepositoryNotFound, RepositoryNotReady
from .ports import UnitOfWorkFactory
from .repositories import validate_repository_segment


def repository_route(owner_segment: str, repository_segment: str) -> tuple[str, str] | None:
    owner = validate_repository_segment(owner_segment, owner=True)
    name = validate_repository_segment(repository_segment[:-4] if repository_segment.endswith(".git") else repository_segment)
    return (owner, name) if owner and name else None


def normalize_file_path(path: str) -> str | None:
    decoded = unquote(path)
    if not decoded or decoded.startswith(("/", "\\")) or "\\" in decoded:
        return None
    parts = decoded.split("/")
    if any(not part or part in {".", ".."} for part in parts):
        return None
    return "/".join(parts)


@dataclass(frozen=True, slots=True)
class Workspace:
    repository: Repository
    conversation: Conversation
    tree: list[TreeNode]
    selected_file: str
    starter_questions: tuple[str, ...]
    messages: list[Message]
    job: IndexingJob


@dataclass(frozen=True, slots=True)
class RepositoryFile:
    repository_id: UUID
    path: str
    content: str


class WorkspaceService:
    def __init__(self, uow_factory: UnitOfWorkFactory, content_source: RepositoryContentSource) -> None:
        self._uow_factory = uow_factory
        self._content_source = content_source

    def get(self, owner: str, name: str) -> Workspace:
        route = repository_route(owner, name)
        with self._uow_factory() as uow:
            repository = uow.repositories.get_by_route(*route) if route else None
            if repository is None:
                raise RepositoryNotFound()
            conversation = uow.conversations.get_active(repository.id)
            job = uow.jobs.current_for_repository(repository.id)
            if conversation is None or job is None:
                raise RepositoryNotReady()
            content = self._content_source.workspace(repository.id)
            return Workspace(
                repository=repository,
                conversation=conversation,
                tree=content.tree,
                selected_file=content.selected_file,
                starter_questions=content.starter_questions,
                messages=uow.messages.list_for_conversation(conversation.id),
                job=job,
            )


class FileService:
    def __init__(self, uow_factory: UnitOfWorkFactory, content_source: RepositoryContentSource) -> None:
        self._uow_factory = uow_factory
        self._content_source = content_source

    def get(self, owner: str, name: str, path: str) -> RepositoryFile:
        route = repository_route(owner, name)
        with self._uow_factory() as uow:
            repository = uow.repositories.get_by_route(*route) if route else None
            if repository is None:
                raise RepositoryNotFound()
            safe_path = normalize_file_path(path)
            content = self._content_source.get_file(repository.id, safe_path) if safe_path else None
            if content is None:
                raise FileNotFound()
            return RepositoryFile(repository_id=repository.id, path=safe_path, content=content)
