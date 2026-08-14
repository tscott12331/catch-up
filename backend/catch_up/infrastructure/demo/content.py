"""Deterministic repository content for the Phase 1 demo."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID, uuid4

from ...application.content import RepositorySeedContent, WorkspaceContent
from .fixtures import DEMO_REVISION, FILE_CONTENT, STARTER_QUESTIONS, messages_fixture, passages_fixture, tree_fixture


class DemoRepositoryContentSource:
    """Serve demo files and construct internally consistent seed records."""

    def __init__(self, *, uuid_factory: Callable[[], UUID] = uuid4) -> None:
        self._uuid_factory = uuid_factory

    @property
    def revision(self) -> str:
        return DEMO_REVISION

    def workspace(self, repository_id: UUID) -> WorkspaceContent:
        del repository_id
        return WorkspaceContent(
            tree=tree_fixture(),
            selected_file="src/api/checkout.ts",
            starter_questions=tuple(STARTER_QUESTIONS),
        )

    def get_file(self, repository_id: UUID, path: str) -> str | None:
        del repository_id
        return FILE_CONTENT.get(path)

    def seed_content(
        self,
        repository_id: UUID,
        conversation_id: UUID,
        *,
        canonical: bool = False,
    ) -> RepositorySeedContent:
        passages = passages_fixture(repository_id)
        messages = messages_fixture(repository_id, conversation_id)
        if canonical:
            return RepositorySeedContent(passages=passages, messages=messages)

        passage_ids = {passage.id: self._uuid_factory() for passage in passages}
        scoped_passages = [passage.model_copy(update={"id": passage_ids[passage.id]}) for passage in passages]
        scoped_messages = []
        for message in messages:
            citations = [
                citation.model_copy(
                    update={
                        "id": self._uuid_factory(),
                        "passage_id": passage_ids[citation.passage_id],
                    }
                )
                for citation in message.citations
            ]
            scoped_messages.append(message.model_copy(update={"id": self._uuid_factory(), "citations": citations}))
        return RepositorySeedContent(passages=scoped_passages, messages=scoped_messages)
