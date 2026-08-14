"""Errors raised by application use cases.

These errors intentionally carry no HTTP status. Transport adapters own the
mapping from a stable application error code to a public protocol response.
"""

from __future__ import annotations

from typing import Any


class ApplicationError(Exception):
    """A known, safe-to-map application failure."""

    code = "application_error"
    default_message = "The operation could not be completed."

    def __init__(self, message: str | None = None, *, details: Any | None = None) -> None:
        self.message = message or self.default_message
        self.details = details
        super().__init__(self.message)


class InvalidRepositoryUrl(ApplicationError):
    code = "invalid_repository_url"
    default_message = "Use a public GitHub repository URL in the form https://github.com/owner/repository."


class RepositoryNotFound(ApplicationError):
    code = "repository_not_found"
    default_message = "Repository was not found."


class ConversationNotFound(ApplicationError):
    code = "conversation_not_found"
    default_message = "Conversation was not found."


class JobNotFound(ApplicationError):
    code = "job_not_found"
    default_message = "Indexing job was not found."


class FileNotFound(ApplicationError):
    code = "file_not_found"
    default_message = "The requested source file was not found."


class RepositoryNotReady(ApplicationError):
    code = "repository_not_ready"
    default_message = "Repository lifecycle records are incomplete."


class ConversationRepositoryMismatch(ApplicationError):
    code = "conversation_repository_mismatch"
    default_message = "Conversation does not belong to this repository."


class InvalidJobTransition(ApplicationError):
    code = "invalid_job_transition"
    default_message = "This indexing job can no longer be cancelled."


class QuestionRequired(ApplicationError):
    code = "question_required"
    default_message = "A question is required."

