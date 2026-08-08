"""Validated process settings for the backend service."""

from __future__ import annotations

import ipaddress
import os
import re
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlsplit


DEFAULT_ORIGIN = "http://localhost:3000"
VALID_ENVIRONMENTS = frozenset({"development", "test", "production"})
VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
HOST_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]*$")


class SettingsValidationError(ValueError):
    """Raised when a process setting cannot be safely used to start the service."""


@dataclass(frozen=True, slots=True)
class Settings:
    host: str
    port: int
    origins: tuple[str, ...]
    environment: str
    log_level: str
    demo_job_duration_seconds: float


def _value(environ: Mapping[str, str], name: str, default: str) -> str:
    return environ.get(name, default).strip()


def _invalid(name: str, value: str, guidance: str) -> SettingsValidationError:
    return SettingsValidationError(f"Invalid {name}={value!r}. {guidance}")


def _validate_host(value: str) -> str:
    if not value:
        raise _invalid("HOST", value, "Set HOST to an IP address, localhost, or a valid hostname.")
    try:
        ipaddress.ip_address(value)
        return value
    except ValueError:
        pass
    if value.lower() == "localhost" or HOST_PATTERN.fullmatch(value):
        return value
    raise _invalid("HOST", value, "Set HOST to an IP address, localhost, or a valid hostname.")


def _validate_origins(value: str) -> tuple[str, ...]:
    origins = tuple(origin.strip().rstrip("/") for origin in value.split(",") if origin.strip())
    if not origins:
        raise _invalid("FRONTEND_ORIGINS", value, "Set one or more comma-separated http(s) origins, for example http://localhost:3000.")
    for origin in origins:
        parsed = urlsplit(origin)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise _invalid("FRONTEND_ORIGINS", value, "Set one or more comma-separated http(s) origins, for example http://localhost:3000.")
    return origins


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Load all supported settings, failing before the server binds on invalid input."""
    source = os.environ if environ is None else environ
    host = _validate_host(_value(source, "HOST", "127.0.0.1"))
    port_raw = _value(source, "PORT", "8000")
    try:
        port = int(port_raw)
    except ValueError as error:
        raise _invalid("PORT", port_raw, "Set PORT to an integer from 1 through 65535.") from error
    if not 1 <= port <= 65535:
        raise _invalid("PORT", port_raw, "Set PORT to an integer from 1 through 65535.")

    origins_value = source.get("FRONTEND_ORIGINS") or source.get("FRONTEND_ORIGIN") or DEFAULT_ORIGIN
    origins = _validate_origins(origins_value)
    environment = _value(source, "ENVIRONMENT", "development").lower()
    if environment not in VALID_ENVIRONMENTS:
        choices = ", ".join(sorted(VALID_ENVIRONMENTS))
        raise _invalid("ENVIRONMENT", environment, f"Set ENVIRONMENT to one of: {choices}.")
    log_level = _value(source, "LOG_LEVEL", "INFO").upper()
    if log_level not in VALID_LOG_LEVELS:
        choices = ", ".join(sorted(VALID_LOG_LEVELS))
        raise _invalid("LOG_LEVEL", log_level, f"Set LOG_LEVEL to one of: {choices}.")
    duration_raw = _value(source, "DEMO_JOB_DURATION_SECONDS", "1.2")
    try:
        duration = float(duration_raw)
    except ValueError as error:
        raise _invalid("DEMO_JOB_DURATION_SECONDS", duration_raw, "Set it to a finite positive number of seconds.") from error
    if duration <= 0 or duration == float("inf") or duration != duration:
        raise _invalid("DEMO_JOB_DURATION_SECONDS", duration_raw, "Set it to a finite positive number of seconds.")
    return Settings(host, port, origins, environment, log_level, duration)
