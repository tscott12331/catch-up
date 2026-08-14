from __future__ import annotations

from datetime import datetime

from catch_up.api.contracts.responses import WorkspaceResponse
from catch_up.application.errors import ApplicationError, RepositoryNotFound
from catch_up.application.ports import Clock, JobRepository, Sleeper, UnitOfWork


def test_workspace_passages_are_not_part_of_the_public_contract() -> None:
    assert "passages" not in WorkspaceResponse.model_fields


def test_application_errors_are_transport_independent() -> None:
    error = RepositoryNotFound(details={"repository_id": "missing"})
    assert isinstance(error, ApplicationError)
    assert error.code == "repository_not_found"
    assert str(error) == "Repository was not found."
    assert error.details == {"repository_id": "missing"}
    assert not hasattr(error, "status_code")


def test_application_ports_can_be_imported_without_runtime_construction() -> None:
    assert UnitOfWork.__module__ == "catch_up.application.ports"
    assert JobRepository.__module__ == "catch_up.application.ports"
    assert Clock.utc_now.__annotations__["return"] in {datetime, "datetime"}
    assert Sleeper.sleep.__name__ == "sleep"
