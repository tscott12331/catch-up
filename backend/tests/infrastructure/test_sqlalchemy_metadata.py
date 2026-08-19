from __future__ import annotations

from sqlalchemy import CheckConstraint, UniqueConstraint, event
from sqlalchemy.dialects.postgresql import dialect
from sqlalchemy.schema import CreateTable

from catch_up.infrastructure.sqlalchemy import Base, build_engine, build_session_factory
from catch_up.infrastructure.sqlalchemy.models import (
    RepositoryModel,
    RepositorySnapshotModel,
    SourceBlobModel,
    SourceFileModel,
)


def test_repository_persistence_tables_and_constraints_are_declared() -> None:
    assert set(Base.metadata.tables) == {
        "repositories",
        "repository_snapshots",
        "source_blobs",
        "source_files",
    }

    repositories = RepositoryModel.__table__
    snapshots = RepositorySnapshotModel.__table__
    blobs = SourceBlobModel.__table__
    files = SourceFileModel.__table__

    assert {column.name for column in repositories.columns} >= {
        "id",
        "source_url",
        "owner",
        "name",
        "default_branch",
        "created_at",
    }
    assert {column.name for column in snapshots.columns} >= {
        "id",
        "repository_id",
        "revision",
        "tree_oid",
        "created_at",
    }
    assert {column.name for column in blobs.columns} >= {
        "sha256",
        "content",
        "size_bytes",
        "created_at",
    }
    assert {column.name for column in files.columns} >= {
        "id",
        "snapshot_id",
        "path",
        "blob_sha256",
        "git_blob_oid",
        "language",
        "encoding",
        "exclusion_reason",
        "kind",
        "size_bytes",
        "status",
        "created_at",
    }

    assert {constraint.name for constraint in repositories.constraints if isinstance(constraint, UniqueConstraint)} == {
        "uq_repositories_owner_name"
    }
    assert {constraint.name for constraint in snapshots.constraints if isinstance(constraint, UniqueConstraint)} == {
        "uq_repository_snapshots_repository_id_revision"
    }
    assert {constraint.name for constraint in files.constraints if isinstance(constraint, UniqueConstraint)} == {
        "uq_source_files_snapshot_id_path"
    }
    assert {
        constraint.name
        for constraint in blobs.constraints
        if isinstance(constraint, CheckConstraint)
    } == {
        "ck_source_blobs_size_non_negative",
        "ck_source_blobs_sha256_format",
    }
    assert {constraint.name for constraint in files.constraints if isinstance(constraint, CheckConstraint)} == {
        "ck_source_files_size_non_negative"
    }


def test_foreign_keys_and_indexes_preserve_snapshot_and_blob_relationships() -> None:
    snapshots = RepositorySnapshotModel.__table__
    files = SourceFileModel.__table__

    snapshot_fk = next(iter(snapshots.c.repository_id.foreign_keys))
    assert snapshot_fk.target_fullname == "repositories.id"
    assert snapshot_fk.ondelete == "CASCADE"

    file_snapshot_fk = next(iter(files.c.snapshot_id.foreign_keys))
    assert file_snapshot_fk.target_fullname == "repository_snapshots.id"
    assert file_snapshot_fk.ondelete == "CASCADE"

    blob_fk = next(iter(files.c.blob_sha256.foreign_keys))
    assert blob_fk.target_fullname == "source_blobs.sha256"
    assert blob_fk.ondelete is None

    assert {index.name for index in snapshots.indexes} >= {
        "ix_repository_snapshots_repository_id"
    }
    assert {index.name for index in files.indexes} >= {
        "ix_source_files_snapshot_id",
        "ix_source_files_blob_sha256",
    }


def test_engine_and_session_factory_are_deferred_and_synchronous() -> None:
    engine = build_engine("sqlite+pysqlite:///:memory:")
    connections: list[object] = []
    event.listen(engine, "connect", lambda *_args: connections.append(object()))

    session_factory = build_session_factory(engine)
    session = session_factory()
    try:
        assert session.bind is engine
        assert session.expire_on_commit is False
        assert connections == []
    finally:
        session.close()
        engine.dispose()


def test_metadata_compiles_for_postgresql_without_database_access() -> None:
    postgres_dialect = dialect()
    for table in Base.metadata.sorted_tables:
        compiled = str(CreateTable(table).compile(dialect=postgres_dialect))
        assert f"CREATE TABLE {table.name}" in compiled
