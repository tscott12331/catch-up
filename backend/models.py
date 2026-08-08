"""Authoritative Pydantic domain contracts for the catch-up backend."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator


JobStatus = Literal["queued", "indexing", "completed", "failed", "cancelled"]
JobStage = Literal["queued", "cloning", "discovering", "parsing", "indexing", "finalizing", "completed", "failed", "cancelled"]
MessageRole = Literal["user", "assistant"]
MessageCompletionState = Literal["pending", "streaming", "completed", "failed", "cancelled"]

Uuid4 = Annotated[UUID, Field(description="A UUID version 4 identifier.")]
PositiveLine = Annotated[int, Field(ge=1)]
Progress = Annotated[int, Field(ge=0, le=100)]


def utc_now() -> datetime:
    """Return an aware datetime that serializes as a UTC ISO-8601 timestamp."""
    return datetime.now(timezone.utc)


class DomainModel(BaseModel):
    """Base contract with strict fields and UUID4 / UTC invariants."""

    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)

    @field_validator("*", mode="after")
    @classmethod
    def validate_domain_values(cls, value: Any, info: Any) -> Any:
        if isinstance(value, UUID) and value.version != 4:
            raise ValueError(f"{info.field_name} must be a UUID4.")
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() != timedelta(0):
                raise ValueError(f"{info.field_name} must be a UTC timestamp.")
        return value


class Repository(DomainModel):
    id: Uuid4 = Field(default_factory=uuid4)
    source_url: AnyHttpUrl
    owner: str = Field(min_length=1)
    name: str = Field(min_length=1)
    default_branch: str = Field(min_length=1)
    indexed_revision: str = Field(min_length=1)


class IndexingError(DomainModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    details: dict[str, Any] | None = None
    retriable: bool = False


class IndexingJob(DomainModel):
    id: Uuid4 = Field(default_factory=uuid4)
    repository_id: Uuid4
    status: JobStatus
    stage: JobStage
    progress: Progress
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: IndexingError | None = None


class Conversation(DomainModel):
    id: Uuid4 = Field(default_factory=uuid4)
    repository_id: Uuid4
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class SourcePassage(DomainModel):
    id: Uuid4 = Field(default_factory=uuid4)
    repository_id: Uuid4
    revision: str = Field(min_length=1)
    path: str = Field(min_length=1)
    start_line: PositiveLine
    end_line: PositiveLine
    content: str
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("end_line")
    @classmethod
    def end_line_must_follow_start_line(cls, value: int, info: Any) -> int:
        start_line = info.data.get("start_line")
        if start_line is not None and value < start_line:
            raise ValueError("end_line must be greater than or equal to start_line.")
        return value


class Citation(DomainModel):
    id: Uuid4 = Field(default_factory=uuid4)
    passage_id: Uuid4
    revision: str = Field(min_length=1)
    path: str = Field(min_length=1)
    start_line: PositiveLine
    end_line: PositiveLine

    @field_validator("end_line")
    @classmethod
    def end_line_must_follow_start_line(cls, value: int, info: Any) -> int:
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
