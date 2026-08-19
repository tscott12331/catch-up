"""SQLAlchemy models for repository snapshots and source content."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CHAR,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import BYTEA
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class RepositoryModel(Base):
    """A repository identity, independent of any particular revision."""

    __tablename__ = "repositories"
    __table_args__ = (
        UniqueConstraint("owner", "name", name="uq_repositories_owner_name"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    default_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    snapshots: Mapped[list[RepositorySnapshotModel]] = relationship(
        back_populates="repository",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class RepositorySnapshotModel(Base):
    """An immutable indexed revision of a repository."""

    __tablename__ = "repository_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "repository_id",
            "revision",
            name="uq_repository_snapshots_repository_id_revision",
        ),
        Index("ix_repository_snapshots_repository_id", "repository_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    repository_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
    )
    revision: Mapped[str] = mapped_column(String(255), nullable=False)
    tree_oid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    repository: Mapped[RepositoryModel] = relationship(back_populates="snapshots")
    files: Mapped[list[SourceFileModel]] = relationship(
        back_populates="snapshot",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class SourceBlobModel(Base):
    """Content-addressed source bytes shared across snapshots and paths."""

    __tablename__ = "source_blobs"
    __table_args__ = (
        CheckConstraint("size_bytes >= 0", name="ck_source_blobs_size_non_negative"),
        CheckConstraint(
            "sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_source_blobs_sha256_format",
        ),
    )

    sha256: Mapped[str] = mapped_column(CHAR(64), primary_key=True)
    content: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    files: Mapped[list[SourceFileModel]] = relationship(back_populates="blob")


class SourceFileModel(Base):
    """A path in a snapshot, optionally backed by a deduplicated blob."""

    __tablename__ = "source_files"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id",
            "path",
            name="uq_source_files_snapshot_id_path",
        ),
        Index("ix_source_files_snapshot_id", "snapshot_id"),
        Index("ix_source_files_blob_sha256", "blob_sha256"),
        CheckConstraint("size_bytes >= 0", name="ck_source_files_size_non_negative"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("repository_snapshots.id", ondelete="CASCADE"),
        nullable=False,
    )
    path: Mapped[str] = mapped_column(String(2048), nullable=False)
    blob_sha256: Mapped[str | None] = mapped_column(
        CHAR(64), ForeignKey("source_blobs.sha256"), nullable=True
    )
    git_blob_oid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    language: Mapped[str | None] = mapped_column(String(64), nullable=True)
    encoding: Mapped[str | None] = mapped_column(String(64), nullable=True)
    exclusion_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    snapshot: Mapped[RepositorySnapshotModel] = relationship(back_populates="files")
    blob: Mapped[SourceBlobModel | None] = relationship(back_populates="files")


# These aliases make the persistence terminology convenient for callers while
# retaining explicit ``*Model`` class names to distinguish ORM records from
# the Pydantic domain models with similar names.
RepositoryRecord = RepositoryModel
RepositorySnapshotRecord = RepositorySnapshotModel
SourceBlobRecord = SourceBlobModel
SourceFileRecord = SourceFileModel


__all__ = [
    "RepositoryModel",
    "RepositoryRecord",
    "RepositorySnapshotModel",
    "RepositorySnapshotRecord",
    "SourceBlobModel",
    "SourceBlobRecord",
    "SourceFileModel",
    "SourceFileRecord",
]
