from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import AnyHttpUrl

from catch_up.application.errors import FileNotFound, InvalidRepositoryUrl, RepositoryNotFound, RepositoryNotReady
from catch_up.application.repositories import ConversationService, RepositoryService, parse_repository_url
from catch_up.application.workspace import FileService, WorkspaceService
from catch_up.infrastructure.demo.content import DemoRepositoryContentSource
from catch_up.infrastructure.demo.fixtures import CHECKOUT_PASSAGE_ID, DEMO_CONVERSATION_ID, DEMO_REPOSITORY_ID, PAYMENT_PASSAGE_ID
from catch_up.infrastructure.demo.seeding import seed_demo_repository
from catch_up.infrastructure.memory import InMemoryDatabase
from catch_up.domain.repository import Repository


def uow_factory():
    return InMemoryDatabase().uow_factory()


def test_repository_url_policy_matches_the_phase_one_boundary() -> None:
    assert parse_repository_url("https://github.com/acme/checkout.git/") == ("acme", "checkout")
    assert parse_repository_url("https://www.github.com/acme/checkout") == ("acme", "checkout")
    for invalid in (
        "https://example.com/acme/checkout",
        "https://github.com/acme/checkout/tree/main",
        "https://user@github.com/acme/checkout",
        "https://github.com:443/acme/checkout",
        "https://github.com/acme/%2e%2e",
    ):
        assert parse_repository_url(invalid) is None


def test_registration_seeds_coherent_repository_scoped_content() -> None:
    factory = uow_factory()
    content = DemoRepositoryContentSource()
    service = RepositoryService(factory, content)

    first = service.register("https://github.com/acme/first")
    second = service.register("https://github.com/acme/second")

    with factory() as uow:
        first_passages = uow.passages.list_for_repository(first.repository.id)
        second_passages = uow.passages.list_for_repository(second.repository.id)
    assert {passage.id for passage in first_passages}.isdisjoint(passage.id for passage in second_passages)
    for registration, passages in ((first, first_passages), (second, second_passages)):
        by_id = {passage.id: passage for passage in passages}
        with factory() as uow:
            messages = uow.messages.list_for_conversation(registration.conversation.id)
        for citation in (citation for message in messages for citation in message.citations):
            passage = by_id[citation.passage_id]
            assert passage.repository_id == registration.repository.id
            assert passage.revision == citation.revision
            assert passage.path == citation.path


def test_reregistering_reuses_repository_and_conversation_but_creates_a_new_job() -> None:
    factory = uow_factory()
    service = RepositoryService(factory, DemoRepositoryContentSource())
    original = service.register("https://github.com/acme/service")
    repeated = service.register("https://github.com/acme/service/")

    assert repeated.repository.id == original.repository.id
    assert repeated.conversation.id == original.conversation.id
    assert repeated.job.id != original.job.id
    with factory() as uow:
        assert len(uow.messages.list_for_conversation(original.conversation.id)) == 3


def test_registration_rolls_back_partial_records_when_seeding_fails() -> None:
    class FailingContent(DemoRepositoryContentSource):
        def seed_content(self, repository_id: UUID, conversation_id: UUID, *, canonical: bool = False):
            del repository_id, conversation_id, canonical
            raise RuntimeError("seed failed")

    factory = uow_factory()
    with pytest.raises(RuntimeError, match="seed failed"):
        RepositoryService(factory, FailingContent()).register("https://github.com/acme/broken")

    with factory() as uow:
        assert uow.repositories.get_by_route("acme", "broken") is None


def test_registration_reports_invalid_url_and_incomplete_existing_lifecycle() -> None:
    factory = uow_factory()
    content = DemoRepositoryContentSource()
    service = RepositoryService(factory, content)
    with pytest.raises(InvalidRepositoryUrl):
        service.register("https://example.com/acme/service")

    with factory() as uow:
        uow.repositories.add(
            Repository(
                source_url=AnyHttpUrl("https://github.com/acme/service"),
                owner="acme",
                name="service",
                default_branch="main",
                indexed_revision=content.revision,
            )
        )
        uow.commit()
    with pytest.raises(RepositoryNotReady):
        service.register("https://github.com/acme/service")


def test_conversation_workspace_and_file_services_share_only_ports() -> None:
    factory = uow_factory()
    content = DemoRepositoryContentSource()
    registered = RepositoryService(factory, content).register("https://github.com/acme/service")

    conversation = ConversationService(factory).create(registered.repository.id)
    workspace = WorkspaceService(factory, content).get("acme", "service.git")
    source = FileService(factory, content).get("acme", "service", "src/api/checkout.ts")

    assert workspace.conversation.id == conversation.id
    assert workspace.messages == []
    assert workspace.job.id == registered.job.id
    assert workspace.selected_file == "src/api/checkout.ts"
    assert source.path == "src/api/checkout.ts"
    assert "export async function checkout" in source.content

    with pytest.raises(FileNotFound):
        FileService(factory, content).get("acme", "service", "%2e%2e/secrets")
    with pytest.raises(RepositoryNotFound):
        WorkspaceService(factory, content).get("missing", "service")
    with pytest.raises(RepositoryNotFound):
        ConversationService(factory).create(UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"))


def test_canonical_demo_seed_retains_the_phase_one_identifiers() -> None:
    factory = uow_factory()
    seeded = seed_demo_repository(factory, DemoRepositoryContentSource())

    assert seeded.repository.id == DEMO_REPOSITORY_ID
    assert seeded.conversation.id == DEMO_CONVERSATION_ID
    with factory() as uow:
        passages = uow.passages.list_for_repository(seeded.repository.id)
        messages = uow.messages.list_for_conversation(seeded.conversation.id)
    assert {passage.id for passage in passages} == {CHECKOUT_PASSAGE_ID, PAYMENT_PASSAGE_ID}
    citations = [
        citation
        for message in messages
        for citation in message.citations
    ]
    assert {citation.passage_id for citation in citations} <= {passage.id for passage in passages}
