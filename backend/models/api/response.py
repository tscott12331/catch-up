from typing import Any
from pydantic import BaseModel

from models.api.chat_sse import Message
from models.chat import Conversation
from models.jobs import IndexingJob
from models.repository import Repository, SourcePassage, TreeNode


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


class StatusResponse(BaseModel):
    status: str
    service: str
