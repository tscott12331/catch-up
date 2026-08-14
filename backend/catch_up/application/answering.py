"""Transport-neutral answer generation boundary."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Protocol, TypeAlias

from ..domain.messages import Citation
from ..domain.repository import Repository, SourcePassage


@dataclass(frozen=True, slots=True)
class AnswerChunk:
    text: str


@dataclass(frozen=True, slots=True)
class AnswerEvidence:
    citations: tuple[Citation, ...]


AnswerPart: TypeAlias = AnswerChunk | AnswerEvidence


class AnswerStreamer(Protocol):
    """Produce answer content without knowledge of HTTP or SSE framing."""

    def stream(
        self,
        repository: Repository,
        question: str,
        passages: Sequence[SourcePassage],
    ) -> AsyncIterator[AnswerPart]: ...


__all__ = ["AnswerChunk", "AnswerEvidence", "AnswerPart", "AnswerStreamer"]
