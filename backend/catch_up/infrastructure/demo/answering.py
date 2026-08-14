"""Deterministic Phase 1 answer generator."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Sequence
from uuid import UUID, uuid4

from ...application.answering import AnswerChunk, AnswerEvidence, AnswerPart
from ...application.ports import Sleeper
from ...domain.messages import Citation
from ...domain.repository import Repository, SourcePassage


DEMO_ANSWER_CHUNKS = (
    "The checkout flow starts in the API layer, validates the cart, and coordinates payment with inventory. ",
    "The controller creates the order only after both side effects succeed; a failed inventory reservation refunds the payment.",
)


class DemoAnswerStreamer:
    def __init__(
        self,
        sleeper: Sleeper,
        *,
        delay_seconds: float = 0.04,
        citation_id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._sleeper = sleeper
        self._delay_seconds = delay_seconds
        self._citation_id_factory = citation_id_factory

    async def stream(
        self,
        repository: Repository,
        question: str,
        passages: Sequence[SourcePassage],
    ) -> AsyncIterator[AnswerPart]:
        await self._sleeper.sleep(self._delay_seconds)
        if "__stream_error__" in question:
            raise RuntimeError("The demo stream failed before completion.")

        for text in DEMO_ANSWER_CHUNKS:
            yield AnswerChunk(text=text)
            await self._sleeper.sleep(self._delay_seconds)

        evidence = tuple(
            Citation(
                id=self._citation_id_factory(),
                passage_id=passage.id,
                revision=passage.revision,
                path=passage.path,
                start_line=passage.start_line,
                end_line=passage.end_line,
            )
            for passage in passages
            if passage.repository_id == repository.id and passage.revision == repository.indexed_revision
        )
        yield AnswerEvidence(citations=evidence)


__all__ = ["DEMO_ANSWER_CHUNKS", "DemoAnswerStreamer"]
