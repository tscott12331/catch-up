"""Synchronous SQLAlchemy infrastructure for repository persistence.

This package contains the database metadata and connection factories only.  It
does not create an engine or connect to a database at import time; application
composition can choose when and how to use these building blocks.
"""

from .base import Base
from .database import build_engine, build_session_factory
from .models import (
    RepositoryModel,
    RepositorySnapshotModel,
    SourceBlobModel,
    SourceFileModel,
)

__all__ = [
    "Base",
    "RepositoryModel",
    "RepositorySnapshotModel",
    "SourceBlobModel",
    "SourceFileModel",
    "build_engine",
    "build_session_factory",
]
