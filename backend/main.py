"""FastAPI boundary for the catch-up demo application."""

from __future__ import annotations

import asyncio
import logging
import os
import re
from collections.abc import AsyncIterator
from typing import Annotated, Any, Literal
from urllib.parse import unquote, urlsplit
from uuid import UUID, uuid4

import uvicorn
from fastapi import Depends, FastAPI, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, TypeAdapter
from starlette.exceptions import HTTPException as StarletteHTTPException

try:
    from .fixtures import DEMO_CONVERSATION_ID, DEMO_REPOSITORY_ID, DEMO_REVISION, FILE_CONTENT, STARTER_QUESTIONS, messages_fixture, passages_fixture, tree_fixture
    from .models import ChatSseEvent, Citation, Conversation, IndexingError, IndexingJob, Message, MessageCompletedEvent, MessageDeltaEvent, MessageErrorEvent, MessageStartedEvent, Repository, SourcePassage, utc_now
    from .stores import InMemoryStores, InvalidJobTransition
except ImportError:  # Allows ``uv run main.py`` from the backend directory.
    from fixtures import DEMO_CONVERSATION_ID, DEMO_REPOSITORY_ID, DEMO_REVISION, FILE_CONTENT, STARTER_QUESTIONS, messages_fixture, passages_fixture, tree_fixture
    from models import ChatSseEvent, Citation, Conversation, IndexingError, IndexingJob, Message, MessageCompletedEvent, MessageDeltaEvent, MessageErrorEvent, MessageStartedEvent, Repository, SourcePassage, utc_now
    from stores import InMemoryStores, InvalidJobTransition


TreeNodeType = Literal["file", "folder"]
logger = logging.getLogger(__name__)


class TreeNode(BaseModel):
    name: str
    type: TreeNodeType
    children: list["TreeNode"] | None = None


class RepositoryCreateResponse(BaseModel):
    repository: Repository
    conversation: Conversation
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


TreeNode.model_rebuild()
chat_sse_event_adapter = TypeAdapter(ChatSseEvent)


class RepositoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = ""


class ConversationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repository_id: UUID


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repository_id: UUID
    conversation_id: UUID
    question: str = ""


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

SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
OWNER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*$")


def reset_in_memory_stores(target_app: FastAPI = app) -> None:
    """Reset the process-local stores and seed the checkout fixture for demos/tests."""
    stores = InMemoryStores()
    repository = Repository(
        id=DEMO_REPOSITORY_ID,
        source_url="https://github.com/acme/checkout-service",
        owner="acme",
        name="checkout-service",
        default_branch="main",
        indexed_revision=DEMO_REVISION,
    )
    conversation = Conversation(id=DEMO_CONVERSATION_ID, repository_id=repository.id)
    stores.repositories.add(repository)
    stores.conversations.add(conversation)
    stores.passages.add_many(passages_fixture(repository.id))
    for message in messages_fixture(repository.id, conversation.id):
        stores.messages.add(message)
    stores.jobs.add(IndexingJob(repository_id=repository.id, status="queued", stage="queued", progress=0))
    target_app.state.stores = stores


reset_in_memory_stores()


def get_stores(request: Request) -> InMemoryStores:
    return request.app.state.stores


StoresDependency = Annotated[InMemoryStores, Depends(get_stores)]


def error_response(status_code: int, code: str, message: str, *, details: Any | None = None) -> JSONResponse:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return JSONResponse(status_code=status_code, content={"error": error})


@app.exception_handler(RequestValidationError)
async def request_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    if any(error.get("type") == "json_invalid" for error in exc.errors()):
        return error_response(400, "invalid_json", "Request body must be JSON.")
    logger.info("Request validation failed for %s: %s", request.url.path, jsonable_encoder(exc.errors()))
    return error_response(422, "validation_error", "Request validation failed.")


@app.exception_handler(StarletteHTTPException)
async def http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if exc.status_code == 404:
        return error_response(404, "not_found", "Route not found.")
    logger.info("HTTP exception for %s: status=%s detail=%r", request.url.path, exc.status_code, exc.detail)
    return error_response(exc.status_code, "http_error", "The request could not be completed.")


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Keep public failures deterministic while retaining diagnostic context in logs."""
    logger.exception("Unhandled request error for %s", request.url.path)
    return error_response(500, "internal_error", "The server could not complete the request.")


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
    raw_segments = parsed.path.split("/")[1:]
    if raw_segments and raw_segments[-1] == "":
        raw_segments.pop()
    if len(raw_segments) != 2 or any(not segment for segment in raw_segments):
        return None
    segments = [unquote(segment) for segment in raw_segments]
    owner = validate_segment(segments[0], owner=True)
    name = validate_segment(segments[1][:-4] if segments[1].endswith(".git") else segments[1])
    return (owner, name) if owner and name else None


def repository_from_route(owner_segment: str, repo_segment: str) -> tuple[str, str] | None:
    owner = validate_segment(owner_segment, owner=True)
    name = validate_segment(repo_segment[:-4] if repo_segment.endswith(".git") else repo_segment)
    return (owner, name) if owner and name else None


def register_repository(stores: InMemoryStores, *, owner: str, name: str, url: str) -> tuple[Repository, Conversation, IndexingJob]:
    repository = stores.repositories.get_by_route(owner, name)
    if repository is None:
        repository = stores.repositories.add(
            Repository(source_url=url, owner=owner, name=name, default_branch="main", indexed_revision=DEMO_REVISION)
        )
        conversation = stores.conversations.add(Conversation(repository_id=repository.id))
        stores.passages.add_many(passages_fixture(repository.id))
        for message in messages_fixture(repository.id, conversation.id):
            stores.messages.add(message.model_copy(update={"id": uuid4()}))
    else:
        conversation = stores.conversations.get_active(repository.id)
        assert conversation is not None
    job = stores.jobs.add(IndexingJob(repository_id=repository.id, status="queued", stage="queued", progress=0))
    return repository, conversation, job


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
    return {"status": "ok", "service": "catch-up-backend", "phase": 4}


@app.post("/api/repositories", status_code=202, response_model=RepositoryCreateResponse)
async def create_repository(payload: RepositoryRequest | None = None, stores: StoresDependency = None) -> RepositoryCreateResponse | JSONResponse:
    payload = payload or RepositoryRequest()
    parsed = parse_repository_url(payload.url)
    if not parsed:
        return error_response(422, "invalid_repository_url", "Use a public GitHub repository URL in the form https://github.com/owner/repository.")
    owner, name = parsed
    repository, conversation, job = register_repository(stores, owner=owner, name=name, url=payload.url.strip().rstrip("/"))
    return RepositoryCreateResponse(repository=repository, conversation=conversation, job=stores.jobs.advance(job.id))


@app.post("/api/conversations", status_code=201, response_model=Conversation)
async def create_conversation(payload: ConversationRequest, stores: StoresDependency = None) -> Conversation | JSONResponse:
    if stores.repositories.get(payload.repository_id) is None:
        return error_response(404, "repository_not_found", "Repository was not found.")
    return stores.conversations.add(Conversation(repository_id=payload.repository_id))


@app.post("/api/repositories/{repository_id}/indexing-jobs", status_code=202, response_model=IndexingJob)
async def create_indexing_job(repository_id: UUID, stores: StoresDependency = None) -> IndexingJob | JSONResponse:
    if stores.repositories.get(repository_id) is None:
        return error_response(404, "repository_not_found", "Repository was not found.")
    job = stores.jobs.add(IndexingJob(repository_id=repository_id, status="queued", stage="queued", progress=0))
    return stores.jobs.advance(job.id)


@app.get("/api/repositories/{owner}/{repo}/workspace", response_model=WorkspaceResponse)
async def get_workspace(owner: str, repo: str, stores: StoresDependency = None) -> WorkspaceResponse | JSONResponse:
    parsed = repository_from_route(owner, repo)
    repository = stores.repositories.get_by_route(*parsed) if parsed else None
    if repository is None:
        return error_response(404, "repository_not_found", "Repository was not found.")
    conversation = stores.conversations.get_active(repository.id)
    job = stores.jobs.current_for_repository(repository.id)
    if conversation is None or job is None:
        return error_response(409, "repository_not_ready", "Repository lifecycle records are incomplete.")
    return WorkspaceResponse(
        repository=repository,
        conversation=conversation,
        tree=tree_fixture(),
        selected_file="src/api/checkout.ts",
        starter_questions=list(STARTER_QUESTIONS),
        messages=stores.messages.list_for_conversation(conversation.id),
        passages=stores.passages.list_for_repository(repository.id),
        job=stores.jobs.advance(job.id),
    )


@app.get("/api/repositories/{owner}/{repo}/files", response_model=FileResponse)
async def get_file(owner: str, repo: str, path: str = Query(...), stores: StoresDependency = None) -> FileResponse | JSONResponse:
    parsed = repository_from_route(owner, repo)
    if parsed is None or stores.repositories.get_by_route(*parsed) is None:
        return error_response(404, "repository_not_found", "Repository was not found.")
    safe_path = file_path_from_query(path)
    if not safe_path:
        return error_response(404, "file_not_found", "The requested source file was not found.")
    return FileResponse(path=safe_path, content=FILE_CONTENT[safe_path])


@app.get("/api/jobs/{job_id}", response_model=IndexingJob)
async def get_job(job_id: UUID, stores: StoresDependency = None) -> IndexingJob | JSONResponse:
    job = stores.jobs.advance(job_id)
    if job is None:
        return error_response(404, "job_not_found", "Indexing job was not found.")
    return job


@app.post("/api/jobs/{job_id}/cancel", response_model=IndexingJob)
async def cancel_job(job_id: UUID, stores: StoresDependency = None) -> IndexingJob | JSONResponse:
    try:
        job = stores.jobs.cancel(job_id)
    except InvalidJobTransition:
        return error_response(409, "invalid_job_transition", "This indexing job can no longer be cancelled.")
    if job is None:
        return error_response(404, "job_not_found", "Indexing job was not found.")
    return job


def encode_sse_event(event: ChatSseEvent) -> str:
    """Serialize only an event that re-validates against the public discriminated union."""
    validated = chat_sse_event_adapter.validate_python(event)
    return f"data: {validated.model_dump_json()}\n\n"


def replace_message_state(stores: InMemoryStores, message: Message, state: Literal["completed", "failed", "cancelled"], *, content: str | None = None, citations: list[Citation] | None = None) -> Message:
    return stores.messages.replace(
        message.model_copy(
            update={
                "completion_state": state,
                "content": message.content if content is None else content,
                "citations": message.citations if citations is None else citations,
                "completed_at": utc_now(),
            }
        )
    )


async def stream_demo_answer(stores: InMemoryStores, repository: Repository, conversation: Conversation, question: str) -> AsyncIterator[str]:
    """Yield validated, ordered SSE events and persist every terminal message state."""
    message_id = uuid4()
    user_message = stores.messages.add(
        Message(conversation_id=conversation.id, role="user", content=question, completion_state="completed", completed_at=utc_now())
    )
    assistant_message = stores.messages.add(
        Message(id=message_id, conversation_id=conversation.id, role="assistant", content="", completion_state="streaming")
    )
    answer = ""
    try:
        yield encode_sse_event(
            MessageStartedEvent(
                type="message.started",
                repository_id=repository.id,
                conversation_id=conversation.id,
                message_id=assistant_message.id,
                user_message_id=user_message.id,
            )
        )
        await asyncio.sleep(0.04)
        if "__stream_error__" in question:
            raise RuntimeError("The demo stream failed before completion.")
        for text in (
            "The checkout flow starts in the API layer, validates the cart, and coordinates payment with inventory. ",
            "The controller creates the order only after both side effects succeed; a failed inventory reservation refunds the payment.",
        ):
            answer += text
            yield encode_sse_event(
                MessageDeltaEvent(
                    type="message.delta",
                    repository_id=repository.id,
                    conversation_id=conversation.id,
                    message_id=assistant_message.id,
                    text=text,
                )
            )
            await asyncio.sleep(0.04)
        citations = messages_fixture(repository.id, conversation.id)[-1].citations
        replace_message_state(stores, assistant_message, "completed", content=answer, citations=citations)
        yield encode_sse_event(
            MessageCompletedEvent(
                type="message.completed",
                repository_id=repository.id,
                conversation_id=conversation.id,
                message_id=assistant_message.id,
                citations=citations,
            )
        )
    except asyncio.CancelledError:
        replace_message_state(stores, assistant_message, "cancelled", content=answer)
        raise
    except Exception:
        logger.exception("Chat stream failed for repository=%s conversation=%s message=%s", repository.id, conversation.id, assistant_message.id)
        replace_message_state(stores, assistant_message, "failed", content=answer)
        yield encode_sse_event(
            MessageErrorEvent(
                type="message.error",
                repository_id=repository.id,
                conversation_id=conversation.id,
                message_id=assistant_message.id,
                code="stream_failed",
                message="The answer stream could not be completed.",
            )
        )


@app.post("/api/chat/stream")
async def chat_stream(payload: ChatRequest, stores: StoresDependency = None) -> Response:
    if not payload.question.strip():
        return error_response(422, "question_required", "A question is required.")
    repository = stores.repositories.get(payload.repository_id)
    if repository is None:
        return error_response(404, "repository_not_found", "Repository was not found.")
    conversation = stores.conversations.get(payload.conversation_id)
    if conversation is None:
        return error_response(404, "conversation_not_found", "Conversation was not found.")
    if conversation.repository_id != repository.id:
        return error_response(409, "conversation_repository_mismatch", "Conversation does not belong to this repository.")
    return StreamingResponse(
        stream_demo_answer(stores, repository, conversation, payload.question.strip()),
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
