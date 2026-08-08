"""FastAPI boundary for the catch-up demo application."""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated, Any, Literal
from urllib.parse import unquote, urlsplit
from uuid import UUID, uuid4

import uvicorn
from fastapi import FastAPI, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

try:
    from .fixtures import DEMO_REPOSITORY_ID, DEMO_REVISION, FILE_CONTENT, STARTER_QUESTIONS, conversation_fixture, messages_fixture, passages_fixture, tree_fixture
    from .models import Citation, Conversation, IndexingError, IndexingJob, Message, Repository, SourcePassage, utc_now
except ImportError:  # Allows ``uv run main.py`` from the backend directory.
    from fixtures import DEMO_REPOSITORY_ID, DEMO_REVISION, FILE_CONTENT, STARTER_QUESTIONS, conversation_fixture, messages_fixture, passages_fixture, tree_fixture
    from models import Citation, Conversation, IndexingError, IndexingJob, Message, Repository, SourcePassage, utc_now


TreeNodeType = Literal["file", "folder"]


class TreeNode(BaseModel):
    name: str
    type: TreeNodeType
    children: list["TreeNode"] | None = None


class RepositoryCreateResponse(BaseModel):
    repository: Repository
    job: IndexingJob


class WorkspaceResponse(BaseModel):
    repository: Repository
    conversation: Conversation
    tree: list[TreeNode]
    selected_file: str
    starter_questions: list[str]
    messages: list[Message]
    passages: list[SourcePassage]
    job: IndexingJob


class FileResponse(BaseModel):
    path: str
    content: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Any | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class MessageStartedEvent(BaseModel):
    type: Literal["message.started"]
    message_id: UUID


class MessageDeltaEvent(BaseModel):
    type: Literal["message.delta"]
    text: str


class MessageCompletedEvent(BaseModel):
    type: Literal["message.completed"]
    citations: list[Citation]


class MessageErrorEvent(BaseModel):
    type: Literal["message.error"]
    code: str | None = None
    message: str | None = None


ChatSseEvent = Annotated[
    MessageStartedEvent | MessageDeltaEvent | MessageCompletedEvent | MessageErrorEvent,
    Field(discriminator="type"),
]


TreeNode.model_rebuild()


class RepositoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = ""


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository_id: str = ""
    question: str = ""


@dataclass
class JobState:
    job: IndexingJob
    created_at_monotonic: float


app = FastAPI(title="Catch-up backend")

configured_origins = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGINS", os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


JOBS: dict[str, JobState] = {}
REPOSITORIES: dict[tuple[str, str], Repository] = {}
JOB_DURATION_SECONDS = 1.2
SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
OWNER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*$")


def error_response(status_code: int, code: str, message: str, *, details: Any | None = None) -> JSONResponse:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return JSONResponse(status_code=status_code, content={"error": error})


@app.exception_handler(RequestValidationError)
async def request_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    if any(error.get("type") == "json_invalid" for error in exc.errors()):
        return error_response(400, "invalid_json", "Request body must be JSON.")
    details = jsonable_encoder(exc.errors())
    return error_response(422, "validation_error", "Request validation failed.", details=details)


@app.exception_handler(StarletteHTTPException)
async def http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if exc.status_code == 404:
        return error_response(404, "not_found", "Route not found.")
    return error_response(exc.status_code, "http_error", str(exc.detail))


def repository_identity(owner: str, name: str, *, url: str | None = None) -> Repository:
    key = (owner, name)
    if key not in REPOSITORIES:
        repository_id = DEMO_REPOSITORY_ID if key == ("acme", "checkout-service") else uuid4()
        REPOSITORIES[key] = Repository(
            id=repository_id,
            source_url=url or f"https://github.com/{owner}/{name}",
            owner=owner,
            name=name,
            default_branch="main",
            indexed_revision=DEMO_REVISION,
        )
    return REPOSITORIES[key]


def validate_segment(value: str, *, owner: bool = False) -> str | None:
    decoded = unquote(value).strip()
    pattern = OWNER_PATTERN if owner else SEGMENT_PATTERN
    if not decoded or decoded in {".", ".."} or "/" in decoded or "\\" in decoded or not pattern.fullmatch(decoded):
        return None
    return decoded


def parse_repository_url(value: str) -> tuple[str, str] | None:
    try:
        parsed = urlsplit(value.strip())
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or hostname not in {"github.com", "www.github.com"}:
        return None
    if parsed.username or parsed.password or port or parsed.query or parsed.fragment:
        return None
    raw_segments = parsed.path.split("/")
    if not raw_segments or raw_segments[0] != "":
        return None
    raw_segments = raw_segments[1:]
    if raw_segments and raw_segments[-1] == "":
        raw_segments.pop()
    if any(not segment for segment in raw_segments):
        return None
    segments = [unquote(segment) for segment in raw_segments]
    if len(segments) != 2:
        return None
    owner = validate_segment(segments[0], owner=True)
    name = validate_segment(segments[1][:-4] if segments[1].endswith(".git") else segments[1])
    if not owner or not name:
        return None
    return owner, name


def repository_from_route(owner_segment: str, repo_segment: str) -> tuple[str, str] | None:
    owner = validate_segment(owner_segment, owner=True)
    repo_without_suffix = repo_segment[:-4] if repo_segment.endswith(".git") else repo_segment
    name = validate_segment(repo_without_suffix)
    if not owner or not name:
        return None
    return owner, name


def ensure_job(repository: Repository, *, reset: bool = False) -> JobState:
    existing = next((state for state in JOBS.values() if state.job.repository_id == repository.id), None)
    if reset or existing is None:
        job = IndexingJob(repository_id=repository.id, status="queued", stage="queued", progress=0)
        state = JobState(job=job, created_at_monotonic=time.monotonic())
        JOBS[str(job.id)] = state
        return state
    return existing


def job_payload(state: JobState) -> IndexingJob:
    elapsed = max(0.0, time.monotonic() - state.created_at_monotonic)
    progress = min(100, int((elapsed / JOB_DURATION_SECONDS) * 100))
    if progress >= 100:
        status = "completed"
        stage = "completed"
        progress = 100
    elif progress == 0:
        status = "queued"
        stage = "queued"
    else:
        status = "indexing"
        stage = "indexing"
    now = utc_now()
    return state.job.model_copy(
        update={
            "status": status,
            "stage": stage,
            "progress": progress,
            "updated_at": now,
            "started_at": state.job.created_at if progress else None,
            "completed_at": now if status == "completed" else None,
        }
    )


def file_path_from_query(path: str) -> str | None:
    decoded = unquote(path)
    if not decoded or decoded.startswith(("/", "\\")) or "\\" in decoded:
        return None
    parts = decoded.split("/")
    if any(not part or part in {".", ".."} for part in parts):
        return None
    candidate = "/".join(parts)
    return candidate if candidate in FILE_CONTENT else None


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "service": "catch-up-backend", "phase": 2}


@app.post("/api/repositories", status_code=202, response_model=RepositoryCreateResponse)
async def create_repository(payload: RepositoryRequest | None = None) -> RepositoryCreateResponse | JSONResponse:
    payload = payload or RepositoryRequest()
    parsed = parse_repository_url(payload.url)
    if not parsed:
        return error_response(
            422,
            "invalid_repository_url",
            "Use a public GitHub repository URL in the form https://github.com/owner/repository.",
        )
    owner, name = parsed
    repository = repository_identity(owner, name, url=payload.url.strip().rstrip("/"))
    job = ensure_job(repository, reset=True)
    return RepositoryCreateResponse(
        repository=repository,
        job=job_payload(job),
    )


@app.get("/api/repositories/{owner}/{repo}/workspace", response_model=WorkspaceResponse)
async def get_workspace(owner: str, repo: str) -> WorkspaceResponse | JSONResponse:
    parsed = repository_from_route(owner, repo)
    if not parsed:
        return error_response(404, "repository_not_found", "Repository route is invalid.")
    owner_name, repo_name = parsed
    repository = repository_identity(owner_name, repo_name)
    job = ensure_job(repository)
    return WorkspaceResponse(
        repository=repository,
        conversation=conversation_fixture(repository.id),
        tree=tree_fixture(),
        selected_file="src/api/checkout.ts",
        starter_questions=list(STARTER_QUESTIONS),
        messages=messages_fixture(repository.id),
        passages=passages_fixture(repository.id),
        job=job_payload(job),
    )


@app.get("/api/repositories/{owner}/{repo}/files", response_model=FileResponse)
async def get_file(owner: str, repo: str, path: str = Query(...)) -> FileResponse | JSONResponse:
    if not repository_from_route(owner, repo):
        return error_response(404, "repository_not_found", "Repository route is invalid.")
    safe_path = file_path_from_query(path)
    if not safe_path:
        return error_response(404, "file_not_found", "The requested source file was not found.")
    return FileResponse(path=safe_path, content=FILE_CONTENT[safe_path])


@app.get("/api/jobs/{job_id}", response_model=IndexingJob)
async def get_job(job_id: str) -> IndexingJob | JSONResponse:
    job = JOBS.get(job_id)
    if not job:
        return error_response(404, "job_not_found", "Indexing job was not found.")
    return job_payload(job)


async def stream_demo_answer(repository_id: str, question: str) -> AsyncIterator[str]:
    """Yield ordered SSE events; ``__stream_error__`` is a deterministic test hook."""
    message_id = uuid4()
    try:
        yield f"data: {json.dumps({'type': 'message.started', 'message_id': str(message_id)})}\n\n"
        await asyncio.sleep(0.04)
        if "__stream_error__" in question:
            raise RuntimeError("The demo stream failed before completion.")
        for text in (
            "The checkout flow starts in the API layer, validates the cart, and coordinates payment with inventory. ",
            "The controller creates the order only after both side effects succeed; a failed inventory reservation refunds the payment.",
        ):
            yield f"data: {json.dumps({'type': 'message.delta', 'text': text})}\n\n"
            await asyncio.sleep(0.04)
        try:
            message_repository_id = UUID(repository_id)
        except ValueError:
            message_repository_id = DEMO_REPOSITORY_ID
        citations = [citation.model_dump(mode="json") for citation in messages_fixture(message_repository_id)[-1].citations]
        yield f"data: {json.dumps({'type': 'message.completed', 'citations': citations})}\n\n"
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        yield f"data: {json.dumps({'type': 'message.error', 'code': 'stream_failed', 'message': str(exc)})}\n\n"


@app.post("/api/chat/stream")
async def chat_stream(payload: ChatRequest | None = None) -> Response:
    payload = payload or ChatRequest()
    if not payload.repository_id.strip():
        return error_response(422, "repository_required", "A repository id is required.")
    if not payload.question.strip():
        return error_response(422, "question_required", "A question is required.")
    return StreamingResponse(
        stream_demo_answer(payload.repository_id, payload.question.strip()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


def main() -> None:
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    print(f"catch-up backend listening on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
