from typing import Annotated, Literal

from pydantic import Field

from ...domain.base import DomainModel, Uuid4
from ...domain.messages import Citation, Message, MessageCompletionState


class SseEventModel(DomainModel):
    """Base for public chat events, correlated to persisted messages."""

    repository_id: Uuid4
    conversation_id: Uuid4
    message_id: Uuid4


class MessageStartedEvent(SseEventModel):
    type: Literal["message.started"]
    user_message_id: Uuid4


class MessageDeltaEvent(SseEventModel):
    type: Literal["message.delta"]
    text: str = Field(min_length=1)


class MessageCompletedEvent(SseEventModel):
    type: Literal["message.completed"]
    citations: list[Citation]


class MessageErrorEvent(SseEventModel):
    type: Literal["message.error"]
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)


ChatSseEvent = Annotated[
    MessageStartedEvent | MessageDeltaEvent | MessageCompletedEvent | MessageErrorEvent,
    Field(discriminator="type"),
]


__all__ = [
    "ChatSseEvent",
    "Citation",
    "Message",
    "MessageCompletedEvent",
    "MessageCompletionState",
    "MessageDeltaEvent",
    "MessageErrorEvent",
    "MessageStartedEvent",
    "SseEventModel",
]
