from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest

from catch_up.application.answering import AnswerChunk, AnswerEvidence
from catch_up.domain.repository import Repository, SourcePassage
from catch_up.infrastructure.demo.answering import DEMO_ANSWER_CHUNKS, DemoAnswerStreamer


REPOSITORY_ID = UUID("11111111-1111-4111-8111-111111111111")
PASSAGE_ID = UUID("22222222-2222-4222-8222-222222222222")
CITATION_ID = UUID("33333333-3333-4333-8333-333333333333")


class FakeSleeper:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def sleep(self, delay_seconds: float) -> None:
        self.delays.append(delay_seconds)


def repository() -> Repository:
    return Repository(
        id=REPOSITORY_ID,
        source_url="https://github.com/acme/checkout-service",
        owner="acme",
        name="checkout-service",
        default_branch="main",
        indexed_revision="abc123",
    )


def passage() -> SourcePassage:
    return SourcePassage(
        id=PASSAGE_ID,
        repository_id=REPOSITORY_ID,
        revision="abc123",
        path="src/checkout.ts",
        start_line=5,
        end_line=20,
        content="checkout",
        created_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
    )


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_demo_streams_canned_chunks_and_repository_evidence_without_waiting() -> None:
    sleeper = FakeSleeper()
    streamer = DemoAnswerStreamer(sleeper, citation_id_factory=lambda: CITATION_ID)

    parts = [part async for part in streamer.stream(repository(), "Question", [passage()])]

    assert [part.text for part in parts if isinstance(part, AnswerChunk)] == list(DEMO_ANSWER_CHUNKS)
    evidence = next(part for part in parts if isinstance(part, AnswerEvidence))
    assert len(evidence.citations) == 1
    assert evidence.citations[0].model_dump() == {
        "id": CITATION_ID,
        "passage_id": PASSAGE_ID,
        "revision": "abc123",
        "path": "src/checkout.ts",
        "start_line": 5,
        "end_line": 20,
    }
    assert sleeper.delays == [0.04, 0.04, 0.04]


@pytest.mark.anyio
async def test_demo_failure_trigger_raises_before_chunks_or_evidence() -> None:
    sleeper = FakeSleeper()
    streamer = DemoAnswerStreamer(sleeper)

    with pytest.raises(RuntimeError, match="demo stream failed"):
        _ = [part async for part in streamer.stream(repository(), "__stream_error__", [passage()])]

    assert sleeper.delays == [0.04]
