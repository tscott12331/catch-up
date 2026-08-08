from datetime import datetime
from typing import Annotated, Literal
from uuid import uuid4
from pydantic import Field, ValidationInfo, field_validator
from models.models import DomainModel, Uuid4, utc_now
from models.repository import PositiveLine

MessageRole = Literal["user", "assistant"]
MessageCompletionState = Literal["pending", "streaming", "completed", "failed", "cancelled"]

class Citation(DomainModel):
    id: Uuid4 = Field(default_factory=uuid4)
    passage_id: Uuid4
    revision: str = Field(min_length=1)
    path: str = Field(min_length=1)
    start_line: PositiveLine
    end_line: PositiveLine

    @field_validator("end_line")
    @classmethod
    def end_line_must_follow_start_line(cls, value: int, info: ValidationInfo) -> int:
        start_line = info.data.get("start_line")
        if start_line is not None and value < start_line:
            raise ValueError("end_line must be greater than or equal to start_line.")
        return value


class Message(DomainModel):
    id: Uuid4 = Field(default_factory=uuid4)
    conversation_id: Uuid4
    role: MessageRole
    content: str
    completion_state: MessageCompletionState
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    citations: list[Citation] = Field(default_factory=list)


class SseEventModel(DomainModel):
    """Base for public chat events, correlated to their persisted messages."""

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
