from typing import Any

from pydantic import BaseModel

from ...domain.chat import Conversation
from ...domain.jobs import IndexingJob
from ...domain.messages import Message
from ...domain.repository import Repository, TreeNode


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


class StatusResponse(BaseModel):
    status: str
    service: str
