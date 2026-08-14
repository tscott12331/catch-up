"""Transactional construction of the canonical checkout demo lifecycle."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import AnyHttpUrl

from ...application.content import RepositoryContentSource
from ...application.ports import UnitOfWorkFactory
from ...domain.chat import Conversation
from ...domain.jobs import IndexingJob
from ...domain.repository import Repository
from .fixtures import DEMO_CONVERSATION_ID, DEMO_REPOSITORY_ID


@dataclass(frozen=True, slots=True)
class SeededDemo:
    repository: Repository
    conversation: Conversation
    job: IndexingJob


def seed_demo_repository(uow_factory: UnitOfWorkFactory, content_source: RepositoryContentSource) -> SeededDemo:
    """Seed the canonical demo atomically through application-owned ports."""
    repository = Repository(
        id=DEMO_REPOSITORY_ID,
        source_url=AnyHttpUrl("https://github.com/acme/checkout-service"),
        owner="acme",
        name="checkout-service",
        default_branch="main",
        indexed_revision=content_source.revision,
    )
    conversation = Conversation(id=DEMO_CONVERSATION_ID, repository_id=repository.id)
    job = IndexingJob(repository_id=repository.id, status="queued", stage="queued", progress=0)
    content = content_source.seed_content(repository.id, conversation.id, canonical=True)

    with uow_factory() as uow:
        uow.repositories.add(repository)
        uow.conversations.add(conversation)
        uow.passages.add_many(content.passages)
        for message in content.messages:
            uow.messages.add(message)
        uow.jobs.add(job)
        uow.commit()
    return SeededDemo(repository=repository, conversation=conversation, job=job)
