"""Conversation-scoped chat orchestration."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal, TypeAlias
from uuid import UUID, uuid4

from ..domain.messages import Citation, Message
from .answering import AnswerChunk, AnswerEvidence, AnswerStreamer
from .errors import (
    ConversationNotFound,
    ConversationRepositoryMismatch,
    QuestionRequired,
    RepositoryNotFound,
)
from .ports import Clock, UnitOfWorkFactory


@dataclass(frozen=True, slots=True)
class ChatStarted:
    repository_id: UUID
    conversation_id: UUID
    message_id: UUID
    user_message_id: UUID


@dataclass(frozen=True, slots=True)
class ChatDelta:
    repository_id: UUID
    conversation_id: UUID
    message_id: UUID
    text: str


@dataclass(frozen=True, slots=True)
class ChatCompleted:
    repository_id: UUID
    conversation_id: UUID
    message_id: UUID
    citations: tuple[Citation, ...]


@dataclass(frozen=True, slots=True)
class ChatFailed:
    """Failure marker whose public code and text are chosen by the API adapter."""

    repository_id: UUID
    conversation_id: UUID
    message_id: UUID


ChatEvent: TypeAlias = ChatStarted | ChatDelta | ChatCompleted | ChatFailed
TerminalState: TypeAlias = Literal["completed", "failed", "cancelled"]


class ChatService:
    def __init__(self, uow_factory: UnitOfWorkFactory, answer_streamer: AnswerStreamer, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._answer_streamer = answer_streamer
        self._clock = clock

    def validate_request(self, repository_id: UUID, conversation_id: UUID, question: str) -> None:
        """Validate a stream before the HTTP adapter commits response headers."""
        if not question.strip():
            raise QuestionRequired()
        with self._uow_factory() as uow:
            repository = uow.repositories.get(repository_id)
            if repository is None:
                raise RepositoryNotFound()
            conversation = uow.conversations.get(conversation_id)
            if conversation is None:
                raise ConversationNotFound()
            if conversation.repository_id != repository.id:
                raise ConversationRepositoryMismatch()

    async def stream_answer(
        self,
        repository_id: UUID,
        conversation_id: UUID,
        question: str,
    ) -> AsyncIterator[ChatEvent]:
        normalized_question = question.strip()
        self.validate_request(repository_id, conversation_id, normalized_question)

        now = self._clock.utc_now()
        with self._uow_factory() as uow:
            repository = uow.repositories.get(repository_id)
            if repository is None:
                raise RepositoryNotFound()

            conversation = uow.conversations.get(conversation_id)
            if conversation is None:
                raise ConversationNotFound()
            if conversation.repository_id != repository.id:
                raise ConversationRepositoryMismatch()

            passages = uow.passages.list_for_repository(repository.id)
            user_message = uow.messages.add(
                Message(
                    id=uuid4(),
                    conversation_id=conversation.id,
                    role="user",
                    content=normalized_question,
                    completion_state="completed",
                    created_at=now,
                    completed_at=now,
                )
            )
            assistant_message = uow.messages.add(
                Message(
                    id=uuid4(),
                    conversation_id=conversation.id,
                    role="assistant",
                    content="",
                    completion_state="streaming",
                    created_at=now,
                )
            )
            uow.commit()

        answer = ""
        citations: list[Citation] = []
        terminal_persisted = False

        def persist_terminal(state: TerminalState) -> None:
            nonlocal terminal_persisted
            if terminal_persisted:
                return

            completed_at = self._clock.utc_now()
            with self._uow_factory() as uow:
                current = uow.messages.get(assistant_message.id)
                if current is None:
                    raise RuntimeError("The streaming assistant message no longer exists.")
                if current.completion_state in {"completed", "failed", "cancelled"}:
                    terminal_persisted = True
                    return

                updated = current.model_copy(
                    update={
                        "content": answer,
                        "citations": citations if state == "completed" else current.citations,
                        "completion_state": state,
                        "completed_at": completed_at,
                    }
                )
                uow.messages.save(updated)
                uow.commit()
            terminal_persisted = True

        try:
            yield ChatStarted(
                repository_id=repository.id,
                conversation_id=conversation.id,
                message_id=assistant_message.id,
                user_message_id=user_message.id,
            )

            async for part in self._answer_streamer.stream(repository, normalized_question, passages):
                if isinstance(part, AnswerChunk):
                    if not part.text:
                        continue
                    answer += part.text
                    yield ChatDelta(
                        repository_id=repository.id,
                        conversation_id=conversation.id,
                        message_id=assistant_message.id,
                        text=part.text,
                    )
                elif isinstance(part, AnswerEvidence):
                    citations.extend(part.citations)

            persist_terminal("completed")
            yield ChatCompleted(
                repository_id=repository.id,
                conversation_id=conversation.id,
                message_id=assistant_message.id,
                citations=tuple(citations),
            )
        except (asyncio.CancelledError, GeneratorExit):
            persist_terminal("cancelled")
            raise
        except Exception:
            persist_terminal("failed")
            yield ChatFailed(
                repository_id=repository.id,
                conversation_id=conversation.id,
                message_id=assistant_message.id,
            )


__all__ = [
    "ChatCompleted",
    "ChatDelta",
    "ChatEvent",
    "ChatFailed",
    "ChatService",
    "ChatStarted",
]
