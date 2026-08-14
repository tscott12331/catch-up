from __future__ import annotations

from uuid import uuid4

import pytest

from catch_up.domain.repository import Repository
from catch_up.infrastructure.memory import InMemoryDatabase, InMemoryUnitOfWorkFactory


def repository(name: str = "service") -> Repository:
    return Repository(
        source_url=f"https://github.com/acme/{name}",
        owner="acme",
        name=name,
        default_branch="main",
        indexed_revision="abc123",
    )


def test_unit_of_work_only_publishes_committed_changes() -> None:
    database = InMemoryDatabase()
    factory = InMemoryUnitOfWorkFactory(database)
    committed = repository("committed")
    rolled_back = repository("rolled-back")

    with factory() as uow:
        uow.repositories.add(committed)
        uow.commit()
    with factory() as uow:
        uow.repositories.add(rolled_back)

    with factory() as uow:
        assert uow.repositories.get(committed.id) == committed
        assert uow.repositories.get(rolled_back.id) is None


def test_exception_after_commit_rolls_back_the_operation() -> None:
    database = InMemoryDatabase()
    factory = database.uow_factory()
    discarded = repository("discarded")

    with pytest.raises(RuntimeError, match="abort"):
        with factory() as uow:
            uow.repositories.add(discarded)
            uow.commit()
            raise RuntimeError("abort")

    with factory() as uow:
        assert uow.repositories.get(discarded.id) is None


def test_commit_captures_changes_at_the_commit_boundary() -> None:
    database = InMemoryDatabase()
    factory = database.uow_factory()
    committed = repository("committed-at-boundary")
    late = repository("changed-after-commit")

    with factory() as uow:
        uow.repositories.add(committed)
        uow.commit()
        uow.repositories.add(late)

    with factory() as uow:
        assert uow.repositories.get(committed.id) == committed
        assert uow.repositories.get(late.id) is None


def test_repository_results_are_copies_and_route_uniqueness_is_enforced() -> None:
    database = InMemoryDatabase()
    factory = database.uow_factory()
    stored = repository()
    with factory() as uow:
        uow.repositories.add(stored)
        uow.commit()

    with factory() as uow:
        loaded = uow.repositories.get(stored.id)
        assert loaded is not None
        loaded.name = "mutated-outside-store"
        assert uow.repositories.get(stored.id) == stored
        with pytest.raises(ValueError, match="route"):
            uow.repositories.add(stored.model_copy(update={"id": uuid4()}))
