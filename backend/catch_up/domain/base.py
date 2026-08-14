from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


Uuid4 = Annotated[UUID, Field(description="A UUID version 4 identifier.")]
Progress = Annotated[int, Field(ge=0, le=100)]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)

    @field_validator("*", mode="after")
    @classmethod
    def validate_domain_values(cls, value: Any, info: ValidationInfo) -> Any:
        if isinstance(value, UUID) and value.version != 4:
            raise ValueError(f"{info.field_name} must be a UUID4.")
        if isinstance(value, datetime) and (value.tzinfo is None or value.utcoffset() != timedelta(0)):
            raise ValueError(f"{info.field_name} must be a UTC timestamp.")
        return value
