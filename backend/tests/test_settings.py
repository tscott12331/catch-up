from __future__ import annotations

import pytest

from catch_up.settings import SettingsValidationError, load_settings


def test_settings_use_safe_defaults_and_normalize_origins() -> None:
    settings = load_settings({"FRONTEND_ORIGINS": "http://localhost:3000/, https://example.test/"})
    assert settings.host == "127.0.0.1"
    assert settings.port == 8000
    assert settings.origins == ("http://localhost:3000", "https://example.test")
    assert settings.environment == "development"
    assert settings.log_level == "INFO"
    assert settings.demo_job_duration_seconds == 1.2


@pytest.mark.parametrize(
    ("environment", "name"),
    [
        ({"PORT": "not-a-port"}, "PORT"),
        ({"FRONTEND_ORIGINS": "ftp://localhost:3000"}, "FRONTEND_ORIGINS"),
        ({"ENVIRONMENT": "staging"}, "ENVIRONMENT"),
        ({"LOG_LEVEL": "verbose"}, "LOG_LEVEL"),
        ({"DEMO_JOB_DURATION_SECONDS": "0"}, "DEMO_JOB_DURATION_SECONDS"),
    ],
)
def test_invalid_settings_fail_before_startup_with_actionable_variable_name(environment: dict[str, str], name: str) -> None:
    with pytest.raises(SettingsValidationError, match=rf"Invalid {name}"):
        load_settings(environment)
