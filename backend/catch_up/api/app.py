"""FastAPI transport adapter for the catch-up application."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, replace
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import TypeAdapter
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..application.chat import ChatCompleted, ChatDelta, ChatFailed, ChatService, ChatStarted
from ..application.errors import ApplicationError
from ..application.indexing import IndexingService
from ..application.repositories import ConversationService, RepositoryService
from ..application.workspace import FileService, WorkspaceService
from ..domain.chat import Conversation
from ..domain.jobs import IndexingJob
from ..observability import request_id_context
from ..settings import Settings
from .contracts.requests import ChatRequest, ConversationRequest, RepositoryRequest
from .contracts.responses import FileResponse, RepositoryCreateResponse, StatusResponse, WorkspaceResponse
from .contracts.sse import ChatSseEvent, MessageCompletedEvent, MessageDeltaEvent, MessageErrorEvent, MessageStartedEvent


logger = logging.getLogger(__name__)
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
chat_sse_event_adapter = TypeAdapter(ChatSseEvent)


@dataclass(frozen=True, slots=True)
class ApplicationServices:
    repositories: RepositoryService
    conversations: ConversationService
    indexing: IndexingService
    workspaces: WorkspaceService
    files: FileService
    chat: ChatService


ServiceFactory = Callable[[], ApplicationServices]


def error_response(status_code: int, code: str, message: str, *, details: Any | None = None) -> JSONResponse:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return JSONResponse(status_code=status_code, content={"error": error})


ERROR_STATUSES = {
    "invalid_repository_url": 422,
    "question_required": 422,
    "repository_not_found": 404,
    "conversation_not_found": 404,
    "job_not_found": 404,
    "file_not_found": 404,
    "repository_not_ready": 409,
    "conversation_repository_mismatch": 409,
    "invalid_job_transition": 409,
}


def add_request_identifiers(request: Request, **identifiers: UUID | str | None) -> None:
    for name, value in identifiers.items():
        if value is not None:
            request.state.identifiers[name] = str(value)


def get_services(request: Request) -> ApplicationServices:
    services = getattr(request.app.state, "services", None)
    if not isinstance(services, ApplicationServices):
        raise RuntimeError("Application services are not initialized.")
    return services


ServicesDependency = Annotated[ApplicationServices, Depends(get_services)]


def encode_sse_event(event: ChatSseEvent) -> str:
    validated = chat_sse_event_adapter.validate_python(event)
    return f"data: {validated.model_dump_json()}\n\n"


async def stream_chat_events(
    service: ChatService,
    repository_id: UUID,
    conversation_id: UUID,
    question: str,
    *,
    request_id: str,
) -> AsyncIterator[str]:
    try:
        async for event in service.stream_answer(repository_id, conversation_id, question):
            if isinstance(event, ChatStarted):
                public_event = MessageStartedEvent(
                    type="message.started",
                    repository_id=event.repository_id,
                    conversation_id=event.conversation_id,
                    message_id=event.message_id,
                    user_message_id=event.user_message_id,
                )
            elif isinstance(event, ChatDelta):
                public_event = MessageDeltaEvent(
                    type="message.delta",
                    repository_id=event.repository_id,
                    conversation_id=event.conversation_id,
                    message_id=event.message_id,
                    text=event.text,
                )
            elif isinstance(event, ChatCompleted):
                public_event = MessageCompletedEvent(
                    type="message.completed",
                    repository_id=event.repository_id,
                    conversation_id=event.conversation_id,
                    message_id=event.message_id,
                    citations=list(event.citations),
                )
                logger.info(
                    "Chat stream reached terminal state",
                    extra={
                        "request_id": request_id,
                        "repository_id": str(event.repository_id),
                        "conversation_id": str(event.conversation_id),
                        "message_id": str(event.message_id),
                        "event": "chat_stream_completed",
                    },
                )
            elif isinstance(event, ChatFailed):
                public_event = MessageErrorEvent(
                    type="message.error",
                    repository_id=event.repository_id,
                    conversation_id=event.conversation_id,
                    message_id=event.message_id,
                    code="stream_failed",
                    message="The answer stream could not be completed.",
                )
                logger.error(
                    "Chat stream failed",
                    extra={
                        "request_id": request_id,
                        "repository_id": str(event.repository_id),
                        "conversation_id": str(event.conversation_id),
                        "message_id": str(event.message_id),
                        "event": "chat_stream_failed",
                    },
                )
            else:  # pragma: no cover - exhaustiveness guard for future event types
                raise TypeError(f"Unsupported chat event: {type(event)!r}")
            yield encode_sse_event(public_event)
    except (asyncio.CancelledError, GeneratorExit):
        logger.info(
            "Chat stream reached terminal state",
            extra={
                "request_id": request_id,
                "repository_id": str(repository_id),
                "conversation_id": str(conversation_id),
                "event": "chat_stream_cancelled",
            },
        )
        raise


def create_app(
    settings: Settings,
    services: ApplicationServices,
    *,
    service_factory: ServiceFactory | None = None,
) -> FastAPI:
    app = FastAPI(title="Catch-up backend")
    app.state.services = services
    app.state.service_factory = service_factory
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.origins),
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def request_observability(request: Request, call_next: Any) -> Response:
        request_id = request.headers.get("X-Request-ID", "")
        request_id = request_id if REQUEST_ID_PATTERN.fullmatch(request_id) else str(uuid4())
        context_token = request_id_context.set(request_id)
        request.state.request_id = request_id
        request.state.identifiers = {}
        started = time.perf_counter()
        try:
            try:
                response = await call_next(request)
            except Exception:
                logger.exception(
                    "Request failed before response",
                    extra={"request_id": request_id, "method": request.method, "route": request.url.path, "event": "request_exception"},
                )
                raise
            duration_ms = round((time.perf_counter() - started) * 1000, 3)
            response.headers["X-Request-ID"] = request_id
            route = getattr(request.scope.get("route"), "path", request.url.path)
            logger.info(
                "Request completed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "route": route,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "event": "request_completed",
                    **request.state.identifiers,
                },
            )
            return response
        finally:
            request_id_context.reset(context_token)

    @app.exception_handler(ApplicationError)
    async def application_error(request: Request, exc: ApplicationError) -> JSONResponse:
        logger.info(
            "Application error handled",
            extra={
                "request_id": getattr(request.state, "request_id", None),
                "route": request.url.path,
                "error_code": exc.code,
                "event": "application_error",
            },
        )
        return error_response(ERROR_STATUSES.get(exc.code, 400), exc.code, exc.message, details=exc.details)

    @app.exception_handler(RequestValidationError)
    async def request_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        if any(error.get("type") == "json_invalid" for error in exc.errors()):
            return error_response(400, "invalid_json", "Request body must be JSON.")
        logger.info(
            "Request validation failed",
            extra={"request_id": getattr(request.state, "request_id", None), "route": request.url.path, "event": "request_validation_failed"},
        )
        return error_response(422, "validation_error", "Request validation failed.")

    @app.exception_handler(StarletteHTTPException)
    async def http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code == 404:
            return error_response(404, "not_found", "Route not found.")
        return error_response(exc.status_code, "http_error", "The request could not be completed.")

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "Unhandled request error",
            extra={"request_id": getattr(request.state, "request_id", None), "route": request.url.path, "event": "unhandled_exception"},
        )
        return error_response(500, "internal_error", "The server could not complete the request.")

    @app.get("/health", response_model=StatusResponse)
    async def health() -> StatusResponse:
        return StatusResponse(status="ok", service="catch-up-backend")

    @app.get("/ready", response_model=StatusResponse)
    async def ready(request: Request) -> StatusResponse | JSONResponse:
        """Report whether this process can serve requests without assuming a delivery phase."""
        if not isinstance(getattr(request.app.state, "services", None), ApplicationServices):
            return error_response(503, "not_ready", "The backend is still initializing.")
        return StatusResponse(status="ready", service="catch-up-backend")

    @app.post("/__test/reset", include_in_schema=False, response_model=None, status_code=204)
    async def reset_test_services(request: Request) -> Response:
        if settings.environment != "test" or request.app.state.service_factory is None:
            return error_response(404, "not_found", "Route not found.")
        request.app.state.services = request.app.state.service_factory()
        return Response(status_code=204)

    @app.post("/api/repositories", status_code=202, response_model=RepositoryCreateResponse)
    async def create_repository(request: Request, payload: RepositoryRequest, services: ServicesDependency) -> RepositoryCreateResponse:
        registration = services.repositories.register(payload.url)
        services.indexing.track(registration.job)
        add_request_identifiers(
            request,
            repository_id=registration.repository.id,
            conversation_id=registration.conversation.id,
            job_id=registration.job.id,
        )
        return RepositoryCreateResponse(
            repository=registration.repository,
            conversation=registration.conversation,
            job=registration.job,
        )

    @app.post("/api/conversations", status_code=201, response_model=Conversation)
    async def create_conversation(request: Request, payload: ConversationRequest, services: ServicesDependency) -> Conversation:
        conversation = services.conversations.create(payload.repository_id)
        add_request_identifiers(request, repository_id=payload.repository_id, conversation_id=conversation.id)
        return conversation

    @app.post("/api/repositories/{repository_id}/indexing-jobs", status_code=202, response_model=IndexingJob)
    async def create_indexing_job(request: Request, repository_id: UUID, services: ServicesDependency) -> IndexingJob:
        job = services.indexing.start(repository_id)
        add_request_identifiers(request, repository_id=repository_id, job_id=job.id)
        return job

    @app.get("/api/repositories/{owner}/{repo}/workspace", response_model=WorkspaceResponse)
    async def get_workspace(request: Request, owner: str, repo: str, services: ServicesDependency) -> WorkspaceResponse:
        workspace = services.workspaces.get(owner, repo)
        job = services.indexing.get(workspace.job.id)
        workspace = replace(workspace, job=job)
        add_request_identifiers(request, repository_id=workspace.repository.id)
        return WorkspaceResponse(
            repository=workspace.repository,
            conversation=workspace.conversation,
            tree=workspace.tree,
            selected_file=workspace.selected_file,
            starter_questions=list(workspace.starter_questions),
            messages=workspace.messages,
            job=workspace.job,
        )

    @app.get("/api/repositories/{owner}/{repo}/files", response_model=FileResponse)
    async def get_file(request: Request, owner: str, repo: str, services: ServicesDependency, path: str = Query(...)) -> FileResponse:
        source = services.files.get(owner, repo, path)
        add_request_identifiers(request, repository_id=source.repository_id)
        return FileResponse(path=source.path, content=source.content)

    @app.get("/api/jobs/{job_id}", response_model=IndexingJob)
    async def get_job(request: Request, job_id: UUID, services: ServicesDependency) -> IndexingJob:
        add_request_identifiers(request, job_id=job_id)
        return services.indexing.get(job_id)

    @app.post("/api/jobs/{job_id}/cancel", response_model=IndexingJob)
    async def cancel_job(request: Request, job_id: UUID, services: ServicesDependency) -> IndexingJob:
        add_request_identifiers(request, job_id=job_id)
        return services.indexing.cancel(job_id)

    @app.post("/api/chat/stream")
    async def chat_stream(request: Request, payload: ChatRequest, services: ServicesDependency) -> Response:
        services.chat.validate_request(payload.repository_id, payload.conversation_id, payload.question)
        add_request_identifiers(request, repository_id=payload.repository_id, conversation_id=payload.conversation_id)
        return StreamingResponse(
            stream_chat_events(
                services.chat,
                payload.repository_id,
                payload.conversation_id,
                payload.question,
                request_id=request.state.request_id,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )

    return app


__all__ = ["ApplicationServices", "create_app", "encode_sse_event", "stream_chat_events"]
