"""Minimal, dependency-free structured logging helpers."""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any


SAFE_LOG_FIELDS = frozenset(
    {
        "request_id",
        "method",
        "route",
        "status_code",
        "duration_ms",
        "repository_id",
        "conversation_id",
        "job_id",
        "message_id",
        "event",
        "error_code",
        "environment",
    }
)
request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    """Emit a small allowlisted JSON object and never serialize exception details."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in SAFE_LOG_FIELDS:
            value = getattr(record, field, None)
            if field == "request_id" and value is None:
                value = request_id_context.get()
            if value is not None:
                payload[field] = value
        return json.dumps(payload, separators=(",", ":"), default=str)


def configure_json_logging(level: str) -> None:
    """Configure process logging once for machine-readable local operation."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

