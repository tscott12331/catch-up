"""Opt-in PostgreSQL migration and persistence smoke test.

The test creates a unique disposable database on the configured PostgreSQL
server. It never upgrades or downgrades the application's ``catch_up``
database directly.
"""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import DBAPIError


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_CONFIG = REPOSITORY_ROOT / "backend" / "alembic.ini"
DEFAULT_DATABASE_URL = "postgresql+psycopg://catch_up:catch_up@localhost:5432/catch_up"


def _require_opt_in() -> None:
    if os.environ.get("RUN_POSTGRES_MIGRATION_TESTS", "").lower() not in {
        "1",
        "true",
        "yes",
    }:
        pytest.skip(
            "set RUN_POSTGRES_MIGRATION_TESTS=1 to run the disposable PostgreSQL smoke test"
        )


def _configured_url() -> URL:
    _require_opt_in()
    return make_url(os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL))


@pytest.fixture
def disposable_database_url() -> URL:
    """Create and clean up a unique database without touching the app DB."""

    source_url = _configured_url()
    if source_url.get_backend_name() != "postgresql":
        pytest.skip("the migration smoke test requires a PostgreSQL DATABASE_URL")

    database_name = f"catch_up_migration_test_{uuid4().hex}"
    admin_url = source_url.set(database="postgres")
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as connection:
            connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
    except DBAPIError as exc:
        admin_engine.dispose()
        pytest.fail(f"could not create disposable PostgreSQL database: {exc}")

    disposable_url = source_url.set(database=database_name)
    try:
        yield disposable_url
    finally:
        admin_engine.dispose()
        drop_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
        try:
            with drop_engine.connect() as connection:
                connection.exec_driver_sql(f'DROP DATABASE "{database_name}" WITH (FORCE)')
        finally:
            drop_engine.dispose()


def _run_migration(database_url: URL, action: str) -> None:
    previous_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url.render_as_string(hide_password=False)
    try:
        config = Config(str(ALEMBIC_CONFIG))
        getattr(command, action)(config, "head" if action == "upgrade" else "base")
    finally:
        if previous_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_url


def _user_tables(connection) -> set[str]:
    rows = connection.execute(
        text(
            """
            SELECT tablename
            FROM pg_catalog.pg_tables
            WHERE schemaname = current_schema()
            """
        )
    )
    return {row[0] for row in rows if row[0] != "alembic_version"}


def test_migration_upgrade_constraints_cascade_and_reupgrade(
    disposable_database_url: URL,
) -> None:
    _run_migration(disposable_database_url, "upgrade")

    engine = create_engine(disposable_database_url)
    repository_id = uuid4()
    first_snapshot_id = uuid4()
    second_snapshot_id = uuid4()
    blob_sha = "a" * 64
    content = b"print('shared source')\n"
    try:
        with engine.begin() as connection:
            assert connection.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")).scalar()
            assert _user_tables(connection) == {
                "repositories",
                "source_blobs",
                "repository_snapshots",
                "source_files",
            }

            connection.execute(
                text(
                    """
                    INSERT INTO repositories (id, source_url, owner, name, default_branch)
                    VALUES (:id, :source_url, :owner, :name, :default_branch)
                    """
                ),
                {
                    "id": repository_id,
                    "source_url": "https://github.com/example/project",
                    "owner": "example",
                    "name": "project",
                    "default_branch": "main",
                },
            )
            connection.execute(
                text(
                    "INSERT INTO source_blobs (sha256, content, size_bytes) "
                    "VALUES (:sha256, :content, :size_bytes)"
                ),
                {"sha256": blob_sha, "content": content, "size_bytes": len(content)},
            )
            connection.execute(
                text(
                    "INSERT INTO repository_snapshots (id, repository_id, revision) "
                    "VALUES (:id, :repository_id, :revision)"
                ),
                {
                    "id": first_snapshot_id,
                    "repository_id": repository_id,
                    "revision": "first",
                },
            )
            connection.execute(
                text(
                    "INSERT INTO repository_snapshots (id, repository_id, revision) "
                    "VALUES (:id, :repository_id, :revision)"
                ),
                {
                    "id": second_snapshot_id,
                    "repository_id": repository_id,
                    "revision": "second",
                },
            )
            file_values = {
                "snapshot_id": first_snapshot_id,
                "id": uuid4(),
                "path": "src/shared.py",
                "blob_sha256": blob_sha,
                "kind": "file",
                "size_bytes": len(content),
                "status": "discovered",
            }
            connection.execute(
                text(
                    """
                    INSERT INTO source_files
                        (id, snapshot_id, path, blob_sha256, kind, size_bytes, status)
                    VALUES
                        (:id, :snapshot_id, :path, :blob_sha256, :kind, :size_bytes, :status)
                    """
                ),
                file_values,
            )
            file_values.update(
                {"id": uuid4(), "snapshot_id": second_snapshot_id, "path": "src/shared.py"}
            )
            connection.execute(
                text(
                    """
                    INSERT INTO source_files
                        (id, snapshot_id, path, blob_sha256, kind, size_bytes, status)
                    VALUES
                        (:id, :snapshot_id, :path, :blob_sha256, :kind, :size_bytes, :status)
                    """
                ),
                file_values,
            )

            assert connection.execute(
                text("SELECT count(*) FROM source_blobs WHERE sha256 = :sha256"),
                {"sha256": blob_sha},
            ).scalar_one() == 1

            with pytest.raises(DBAPIError):
                with connection.begin_nested():
                    connection.execute(
                        text(
                            "INSERT INTO source_blobs (sha256, content, size_bytes) "
                            "VALUES (:sha256, :content, :size_bytes)"
                        ),
                        {"sha256": "A" * 64, "content": b"bad", "size_bytes": 3},
                    )
            with pytest.raises(DBAPIError):
                with connection.begin_nested():
                    connection.execute(
                        text(
                            "INSERT INTO source_blobs (sha256, content, size_bytes) "
                            "VALUES (:sha256, :content, :size_bytes)"
                        ),
                        {"sha256": "g" * 64, "content": b"bad", "size_bytes": 3},
                    )
            with pytest.raises(DBAPIError):
                with connection.begin_nested():
                    connection.execute(
                        text(
                            "INSERT INTO source_blobs (sha256, content, size_bytes) "
                            "VALUES (:sha256, :content, :size_bytes)"
                        ),
                        {"sha256": "b" * 64, "content": b"bad", "size_bytes": -1},
                    )

            connection.execute(
                text("DELETE FROM repository_snapshots WHERE id = :snapshot_id"),
                {"snapshot_id": first_snapshot_id},
            )
            assert connection.execute(
                text("SELECT count(*) FROM source_files WHERE snapshot_id = :snapshot_id"),
                {"snapshot_id": first_snapshot_id},
            ).scalar_one() == 0
            assert connection.execute(
                text("SELECT count(*) FROM source_blobs WHERE sha256 = :sha256"),
                {"sha256": blob_sha},
            ).scalar_one() == 1
    finally:
        engine.dispose()

    _run_migration(disposable_database_url, "downgrade")
    engine = create_engine(disposable_database_url)
    try:
        with engine.connect() as connection:
            assert _user_tables(connection) == set()
            assert connection.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            ).scalar()
    finally:
        engine.dispose()

    _run_migration(disposable_database_url, "upgrade")
    engine = create_engine(disposable_database_url)
    try:
        with engine.connect() as connection:
            assert _user_tables(connection) == {
                "repositories",
                "source_blobs",
                "repository_snapshots",
                "source_files",
            }
    finally:
        engine.dispose()
