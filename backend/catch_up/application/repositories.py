"""Repository registration and conversation application services."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit
from uuid import UUID

from pydantic import AnyHttpUrl

from ..domain.chat import Conversation
from ..domain.jobs import IndexingJob
from ..domain.repository import Repository
from .content import RepositoryContentSource
from .errors import InvalidRepositoryUrl, RepositoryNotFound, RepositoryNotReady
from .ports import UnitOfWorkFactory


SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
OWNER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*$")


def validate_repository_segment(value: str, *, owner: bool = False) -> str | None:
    decoded = unquote(value).strip()
    pattern = OWNER_PATTERN if owner else SEGMENT_PATTERN
    if not decoded or decoded in {".", ".."} or "/" in decoded or "\\" in decoded or not pattern.fullmatch(decoded):
        return None
    return decoded


def parse_repository_url(value: str) -> tuple[str, str] | None:
    """Return the owner/name of a supported public GitHub URL."""
    try:
        parsed = urlsplit(value.strip())
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or hostname not in {"github.com", "www.github.com"}:
        return None
    if parsed.username or parsed.password or port or parsed.query or parsed.fragment:
        return None
    raw_segments = parsed.path.split("/")[1:]
    if raw_segments and raw_segments[-1] == "":
        raw_segments.pop()
    if len(raw_segments) != 2 or any(not segment for segment in raw_segments):
        return None
    segments = [unquote(segment) for segment in raw_segments]
    owner = validate_repository_segment(segments[0], owner=True)
    name = validate_repository_segment(segments[1][:-4] if segments[1].endswith(".git") else segments[1])
    return (owner, name) if owner and name else None


@dataclass(frozen=True, slots=True)
class RepositoryRegistration:
    repository: Repository
    conversation: Conversation
    job: IndexingJob


class RepositoryService:
    def __init__(self, uow_factory: UnitOfWorkFactory, content_source: RepositoryContentSource) -> None:
        self._uow_factory = uow_factory
        self._content_source = content_source

    def register(self, source_url: str) -> RepositoryRegistration:
        parsed = parse_repository_url(source_url)
        if parsed is None:
            raise InvalidRepositoryUrl()
        owner, name = parsed
        normalized_url = AnyHttpUrl(source_url.strip().rstrip("/"))

        with self._uow_factory() as uow:
            repository = uow.repositories.get_by_route(owner, name)
            if repository is None:
                repository = uow.repositories.add(
                    Repository(
                        source_url=normalized_url,
                        owner=owner,
                        name=name,
                        default_branch="main",
                        indexed_revision=self._content_source.revision,
                    )
                )
                conversation = uow.conversations.add(Conversation(repository_id=repository.id))
                seed = self._content_source.seed_content(repository.id, conversation.id)
                uow.passages.add_many(seed.passages)
                for message in seed.messages:
                    uow.messages.add(message)
            else:
                conversation = uow.conversations.get_active(repository.id)
                if conversation is None:
                    raise RepositoryNotReady()

            job = uow.jobs.add(IndexingJob(repository_id=repository.id, status="queued", stage="queued", progress=0))
            uow.commit()
            return RepositoryRegistration(repository=repository, conversation=conversation, job=job)


class ConversationService:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    def create(self, repository_id: UUID) -> Conversation:
        with self._uow_factory() as uow:
            if uow.repositories.get(repository_id) is None:
                raise RepositoryNotFound()
            conversation = uow.conversations.add(Conversation(repository_id=repository_id))
            uow.commit()
            return conversation

