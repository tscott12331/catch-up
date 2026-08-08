from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid1

import pytest
from pydantic import ValidationError

from fixtures import DEMO_REPOSITORY_ID, DEMO_REVISION, messages_fixture, passages_fixture
from models import Citation, IndexingJob, Repository, SourcePassage


def test_domain_models_serialize_uuid4_and_utc_timestamps() -> None:
    repository = Repository(
        id=DEMO_REPOSITORY_ID,
        source_url="https://github.com/acme/checkout-service",
        owner="acme",
        name="checkout-service",
        default_branch="main",
        indexed_revision=DEMO_REVISION,
    )
    job = IndexingJob(repository_id=repository.id, status="cancelled", stage="cancelled", progress=42)

    payload = job.model_dump(mode="json")
    assert UUID(payload["id"]).version == 4
    assert payload["repository_id"] == str(repository.id)
    assert payload["created_at"].endswith("Z")
    assert payload["updated_at"].endswith("Z")


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (IndexingJob, {"id": uuid1(), "repository_id": DEMO_REPOSITORY_ID, "status": "queued", "stage": "queued", "progress": 0}),
        (IndexingJob, {"repository_id": DEMO_REPOSITORY_ID, "status": "queued", "stage": "queued", "progress": 101}),
        (SourcePassage, {"repository_id": DEMO_REPOSITORY_ID, "revision": DEMO_REVISION, "path": "src/a.py", "start_line": 3, "end_line": 2, "content": "x"}),
        (Citation, {"passage_id": UUID("33333333-3333-4333-8333-333333333333"), "revision": DEMO_REVISION, "path": "src/a.py", "start_line": 0, "end_line": 1}),
    ],
)
def test_domain_models_reject_invalid_identifiers_progress_and_ranges(model: type[object], payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        model(**payload)  # type: ignore[operator]


def test_domain_models_reject_non_utc_timestamps() -> None:
    with pytest.raises(ValidationError, match="UTC timestamp"):
        IndexingJob(
            repository_id=DEMO_REPOSITORY_ID,
            status="queued",
            stage="queued",
            progress=0,
            created_at=datetime.now(timezone(timedelta(hours=-7))),
        )


def test_fixture_citations_resolve_to_their_passages_and_revision() -> None:
    passages = {passage.id: passage for passage in passages_fixture(DEMO_REPOSITORY_ID)}

    citations = [citation for message in messages_fixture(DEMO_REPOSITORY_ID) for citation in message.citations]

    assert citations
    for citation in citations:
        passage = passages[citation.passage_id]
        assert passage.revision == citation.revision == DEMO_REVISION
        assert passage.path == citation.path
        assert passage.start_line <= citation.start_line <= citation.end_line <= passage.end_line
