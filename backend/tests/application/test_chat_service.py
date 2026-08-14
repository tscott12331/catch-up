from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from datetime import datetime, timezone
from types import TracebackType
from uuid import UUID

import pytest

from catch_up.application.answering import AnswerChunk, AnswerEvidence, AnswerPart
from catch_up.application.chat import ChatCompleted, ChatDelta, ChatFailed, ChatService, ChatStarted
from catch_up.application.errors import (
    ConversationNotFound,
    ConversationRepositoryMismatch,
    QuestionRequired,
    RepositoryNotFound,
)
from catch_up.domain.chat import Conversation
from catch_up.domain.messages import Citation, Message
from catch_up.domain.repository import Repository, SourcePassage


REPOSITORY_ID = UUID("11111111-1111-4111-8111-111111111111")
OTHER_REPOSITORY_ID = UUID("22222222-2222-4222-8222-222222222222")
CONVERSATION_ID = UUID("33333333-3333-4333-8333-333333333333")
PASSAGE_ID = UUID("44444444-4444-4444-8444-444444444444")
CITATION_ID = UUID("55555555-5555-4555-8555-555555555555")
NOW = datetime(2026, 8, 10, 12, tzinfo=timezone.utc)


class FakeClock:
    def utc_now(self) -> datetime:
        return NOW

    def monotonic(self) -> float:
        return 0.0


class ObjectRepository:
    def __init__(self, values: dict[UUID, object]) -> None:
        self.values = values

    def add(self, value: object) -> object:
        self.values[value.id] = value  # type: ignore[attr-defined]
        return value

    def get(self, identifier: UUID) -> object | None:
        return self.values.get(identifier)


class FakeRepositories(ObjectRepository):
    def get_by_route(self, owner: str, name: str) -> Repository | None:
        return next((item for item in self.values.values() if isinstance(item, Repository) and item.owner == owner and item.name == name), None)


class FakeConversations(ObjectRepository):
    def get_active(self, repository_id: UUID) -> Conversation | None:
        return next((item for item in self.values.values() if isinstance(item, Conversation) and item.repository_id == repository_id), None)


class FakeMessages(ObjectRepository):
    def __init__(self) -> None:
        super().__init__({})
        self.add_calls: list[Message] = []
        self.save_calls: list[Message] = []

    def add(self, value: Message) -> Message:
        self.add_calls.append(value)
        self.values[value.id] = value
        return value

    def save(self, value: Message) -> Message:
        self.save_calls.append(value)
        self.values[value.id] = value
        return value

    def list_for_conversation(self, conversation_id: UUID) -> list[Message]:
        return [item for item in self.values.values() if isinstance(item, Message) and item.conversation_id == conversation_id]


class FakePassages:
    def __init__(self, passages: list[SourcePassage]) -> None:
        self.passages = passages

    def add_many(self, passages: Sequence[SourcePassage]) -> None:
        self.passages.extend(passages)

    def list_for_repository(self, repository_id: UUID) -> list[SourcePassage]:
        return [passage for passage in self.passages if passage.repository_id == repository_id]


class FakeJobs:
    pass


class FakeDatabase:
    def __init__(self) -> None:
        repository = Repository(
            id=REPOSITORY_ID,
            source_url="https://github.com/acme/checkout-service",
            owner="acme",
            name="checkout-service",
            default_branch="main",
            indexed_revision="abc123",
        )
        conversation = Conversation(id=CONVERSATION_ID, repository_id=REPOSITORY_ID)
        passage = SourcePassage(
            id=PASSAGE_ID,
            repository_id=REPOSITORY_ID,
            revision="abc123",
            path="src/checkout.ts",
            start_line=1,
            end_line=4,
            content="checkout",
        )
        self.repositories = FakeRepositories({REPOSITORY_ID: repository})
        self.conversations = FakeConversations({CONVERSATION_ID: conversation})
        self.messages = FakeMessages()
        self.passages = FakePassages([passage])
        self.jobs = FakeJobs()
        self.commits = 0
        self.rollbacks = 0


class FakeUnitOfWork:
    def __init__(self, database: FakeDatabase) -> None:
        self._database = database
        self.repositories = database.repositories
        self.conversations = database.conversations
        self.messages = database.messages
        self.passages = database.passages
        self.jobs = database.jobs
        self._committed = False

    def __enter__(self) -> FakeUnitOfWork:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exception_type is not None or not self._committed:
            self.rollback()

    def commit(self) -> None:
        self._committed = True
        self._database.commits += 1

    def rollback(self) -> None:
        self._database.rollbacks += 1


class ScriptedAnswerStreamer:
    def __init__(self, parts: Sequence[AnswerPart], failure: Exception | None = None) -> None:
        self.parts = parts
        self.failure = failure

    async def stream(
        self,
        repository: Repository,
        question: str,
        passages: Sequence[SourcePassage],
    ) -> AsyncIterator[AnswerPart]:
        for part in self.parts:
            yield part
        if self.failure is not None:
            raise self.failure


class BlockingAnswerStreamer:
    def __init__(self) -> None:
        self.blocked = asyncio.Event()
        self.release = asyncio.Event()

    async def stream(
        self,
        repository: Repository,
        question: str,
        passages: Sequence[SourcePassage],
    ) -> AsyncIterator[AnswerPart]:
        yield AnswerChunk("Partial answer")
        self.blocked.set()
        await self.release.wait()


def citation() -> Citation:
    return Citation(
        id=CITATION_ID,
        passage_id=PASSAGE_ID,
        revision="abc123",
        path="src/checkout.ts",
        start_line=1,
        end_line=4,
    )


def service(database: FakeDatabase, streamer: object) -> ChatService:
    return ChatService(lambda: FakeUnitOfWork(database), streamer, FakeClock())  # type: ignore[arg-type]


async def collect(stream: AsyncIterator[object]) -> list[object]:
    return [event async for event in stream]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_success_persists_one_completed_terminal_message() -> None:
    database = FakeDatabase()
    events = await collect(
        service(database, ScriptedAnswerStreamer([AnswerChunk("First "), AnswerChunk("second."), AnswerEvidence((citation(),))])).stream_answer(
            REPOSITORY_ID,
            CONVERSATION_ID,
            "  How does checkout work?  ",
        )
    )

    assert [type(event) for event in events] == [ChatStarted, ChatDelta, ChatDelta, ChatCompleted]
    assert [event.text for event in events if isinstance(event, ChatDelta)] == ["First ", "second."]
    assert isinstance(events[-1], ChatCompleted) and events[-1].citations == (citation(),)
    assert [message.role for message in database.messages.add_calls] == ["user", "assistant"]
    assert database.messages.add_calls[0].content == "How does checkout work?"
    assert len(database.messages.save_calls) == 1
    terminal = database.messages.save_calls[0]
    assert terminal.completion_state == "completed"
    assert terminal.content == "First second."
    assert terminal.citations == [citation()]
    assert terminal.completed_at == NOW


@pytest.mark.anyio
async def test_partial_failure_persists_one_failed_terminal_message_and_returns_marker() -> None:
    database = FakeDatabase()
    events = await collect(
        service(database, ScriptedAnswerStreamer([AnswerChunk("Partial")], RuntimeError("internal details"))).stream_answer(
            REPOSITORY_ID,
            CONVERSATION_ID,
            "Question",
        )
    )

    assert [type(event) for event in events] == [ChatStarted, ChatDelta, ChatFailed]
    assert not hasattr(events[-1], "message")
    assert len(database.messages.save_calls) == 1
    terminal = database.messages.save_calls[0]
    assert terminal.completion_state == "failed"
    assert terminal.content == "Partial"
    assert terminal.citations == []


@pytest.mark.anyio
async def test_cancellation_persists_one_cancelled_terminal_message_and_is_reraised() -> None:
    database = FakeDatabase()
    streamer = BlockingAnswerStreamer()
    task = asyncio.create_task(collect(service(database, streamer).stream_answer(REPOSITORY_ID, CONVERSATION_ID, "Question")))
    await streamer.blocked.wait()

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert len(database.messages.save_calls) == 1
    terminal = database.messages.save_calls[0]
    assert terminal.completion_state == "cancelled"
    assert terminal.content == "Partial answer"


@pytest.mark.anyio
async def test_blank_question_is_rejected_before_persistence() -> None:
    database = FakeDatabase()

    with pytest.raises(QuestionRequired):
        await collect(service(database, ScriptedAnswerStreamer([])).stream_answer(REPOSITORY_ID, CONVERSATION_ID, " \n "))

    assert database.messages.add_calls == []
    assert database.commits == 0


@pytest.mark.anyio
async def test_missing_repository_is_rejected_before_persistence() -> None:
    database = FakeDatabase()

    with pytest.raises(RepositoryNotFound):
        await collect(service(database, ScriptedAnswerStreamer([])).stream_answer(OTHER_REPOSITORY_ID, CONVERSATION_ID, "Question"))

    assert database.messages.add_calls == []


@pytest.mark.anyio
async def test_missing_conversation_is_rejected_before_persistence() -> None:
    database = FakeDatabase()

    with pytest.raises(ConversationNotFound):
        await collect(
            service(database, ScriptedAnswerStreamer([])).stream_answer(
                REPOSITORY_ID,
                UUID("66666666-6666-4666-8666-666666666666"),
                "Question",
            )
        )

    assert database.messages.add_calls == []


@pytest.mark.anyio
async def test_repository_mismatch_is_rejected_before_persistence() -> None:
    database = FakeDatabase()
    database.conversations.values[CONVERSATION_ID] = Conversation(id=CONVERSATION_ID, repository_id=OTHER_REPOSITORY_ID)

    with pytest.raises(ConversationRepositoryMismatch):
        await collect(service(database, ScriptedAnswerStreamer([])).stream_answer(REPOSITORY_ID, CONVERSATION_ID, "Question"))

    assert database.messages.add_calls == []
