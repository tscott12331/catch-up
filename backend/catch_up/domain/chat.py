from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from pydantic import Field

from .base import DomainModel, Uuid4, utc_now


class Conversation(DomainModel):
    id: Uuid4 = Field(default_factory=uuid4)
    repository_id: Uuid4
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
