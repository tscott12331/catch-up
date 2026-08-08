"""Authoritative Pydantic domain contracts for the catch-up backend."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, ValidationInfo, field_validator



Uuid4 = Annotated[UUID, Field(description="A UUID version 4 identifier.")]
Progress = Annotated[int, Field(ge=0, le=100)]


def utc_now() -> datetime:
    """Return an aware datetime that serializes as a UTC ISO-8601 timestamp."""
    return datetime.now(timezone.utc)


class DomainModel(BaseModel):
    """Base contract with strict fields and UUID4 / UTC invariants."""

    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)

    @field_validator("*", mode="after")
    @classmethod
    def validate_domain_values(cls, value: Any, info: ValidationInfo) -> Any:
        if isinstance(value, UUID) and value.version != 4:
            raise ValueError(f"{info.field_name} must be a UUID4.")
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() != timedelta(0):
                raise ValueError(f"{info.field_name} must be a UTC timestamp.")
        return value
