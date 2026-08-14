"""Validate settings before importing and starting the ASGI application."""

from __future__ import annotations

import logging

from catch_up.observability import configure_json_logging
from catch_up.settings import SettingsValidationError, load_settings


def run() -> int:
    try:
        settings = load_settings()
    except SettingsValidationError as error:
        configure_json_logging("ERROR")
        logging.getLogger(__name__).error("Backend configuration invalid: %s", error, extra={"event": "configuration_invalid"})
        return 2
    from catch_up.bootstrap import main

    main(settings)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
