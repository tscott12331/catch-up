from uuid import UUID
from pydantic import BaseModel, ConfigDict


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
