"""Repository-content boundary and application-facing content values."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol
from uuid import UUID

from ..domain.messages import Message
from ..domain.repository import SourcePassage, TreeNode


@dataclass(frozen=True, slots=True)
class WorkspaceContent:
    tree: list[TreeNode]
    selected_file: str
    starter_questions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RepositorySeedContent:
    passages: list[SourcePassage]
    messages: list[Message]


class RepositoryContentSource(Protocol):
    """Read repository content without exposing fixture or filesystem details."""

    @property
    def revision(self) -> str: ...

    def workspace(self, repository_id: UUID) -> WorkspaceContent: ...

    def get_file(self, repository_id: UUID, path: str) -> str | None: ...

    def seed_content(
        self,
        repository_id: UUID,
        conversation_id: UUID,
        *,
        canonical: bool = False,
    ) -> RepositorySeedContent: ...

