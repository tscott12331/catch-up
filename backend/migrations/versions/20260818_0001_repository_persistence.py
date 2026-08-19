"""Create repository snapshot and source content tables.

Revision ID: 20260818_0001
Revises:
Create Date: 2026-08-18
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260818_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the initial PostgreSQL persistence schema."""

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "repositories",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("owner", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("default_branch", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_repositories"),
        sa.UniqueConstraint("owner", "name", name="uq_repositories_owner_name"),
    )

    op.create_table(
        "source_blobs",
        sa.Column("sha256", sa.CHAR(length=64), nullable=False),
        sa.Column("content", postgresql.BYTEA(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "size_bytes >= 0",
            name="ck_source_blobs_size_non_negative",
        ),
        sa.CheckConstraint(
            "sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_source_blobs_sha256_format",
        ),
        sa.PrimaryKeyConstraint("sha256", name="pk_source_blobs"),
    )

    op.create_table(
        "repository_snapshots",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("repository_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("revision", sa.String(length=255), nullable=False),
        sa.Column("tree_oid", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            name="fk_repository_snapshots_repository_id_repositories",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_repository_snapshots"),
        sa.UniqueConstraint(
            "repository_id",
            "revision",
            name="uq_repository_snapshots_repository_id_revision",
        ),
    )
    op.create_index(
        "ix_repository_snapshots_repository_id",
        "repository_snapshots",
        ["repository_id"],
    )

    op.create_table(
        "source_files",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("path", sa.String(length=2048), nullable=False),
        sa.Column("blob_sha256", sa.CHAR(length=64), nullable=True),
        sa.Column("git_blob_oid", sa.String(length=64), nullable=True),
        sa.Column("language", sa.String(length=64), nullable=True),
        sa.Column("encoding", sa.String(length=64), nullable=True),
        sa.Column("exclusion_reason", sa.Text(), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "size_bytes >= 0",
            name="ck_source_files_size_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["blob_sha256"],
            ["source_blobs.sha256"],
            name="fk_source_files_blob_sha256_source_blobs",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["repository_snapshots.id"],
            name="fk_source_files_snapshot_id_repository_snapshots",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_source_files"),
        sa.UniqueConstraint(
            "snapshot_id",
            "path",
            name="uq_source_files_snapshot_id_path",
        ),
    )
    op.create_index("ix_source_files_snapshot_id", "source_files", ["snapshot_id"])
    op.create_index(
        "ix_source_files_blob_sha256",
        "source_files",
        ["blob_sha256"],
    )


def downgrade() -> None:
    """Remove tables while preserving the shared vector extension."""

    op.drop_index("ix_source_files_blob_sha256", table_name="source_files")
    op.drop_index("ix_source_files_snapshot_id", table_name="source_files")
    op.drop_table("source_files")
    op.drop_index(
        "ix_repository_snapshots_repository_id",
        table_name="repository_snapshots",
    )
    op.drop_table("repository_snapshots")
    op.drop_table("source_blobs")
    op.drop_table("repositories")
