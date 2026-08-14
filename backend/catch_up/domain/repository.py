from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import uuid4

from pydantic import AnyHttpUrl, BaseModel, Field, ValidationInfo, field_validator

from .base import DomainModel, Uuid4, utc_now


PositiveLine = Annotated[int, Field(ge=1)]


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
    def end_line_must_follow_start_line(cls, value: int, info: ValidationInfo) -> int:
        start_line = info.data.get("start_line")
        if start_line is not None and value < start_line:
            raise ValueError("end_line must be greater than or equal to start_line.")
        return value


TreeNodeType = Literal["file", "folder"]


class TreeNode(BaseModel):
    name: str
    type: TreeNodeType
    children: list["TreeNode"] | None = None


TreeNode.model_rebuild()

