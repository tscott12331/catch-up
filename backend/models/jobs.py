from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import Field

from models.models import DomainModel, Progress, Uuid4, utc_now
from models.repository import IndexingError


JobStatus = Literal["queued", "indexing", "completed", "failed", "cancelled"]
JobStage = Literal["queued", "cloning", "discovering", "parsing", "indexing", "finalizing", "completed", "failed", "cancelled"]

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
