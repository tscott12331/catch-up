"""Run the complete Phase 1 verification gate from the repository root."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CHECKS = (
    ("backend tests", ("uv", "run", "--project", "backend", "pytest")),
    (
        "backend contract check",
        ("uv", "run", "--project", "backend", "python", "backend/export_contracts.py", "--check"),
    ),
    ("frontend contract check", ("bun", "run", "--cwd", "frontend", "contract:check")),
    ("frontend lint", ("bun", "run", "--cwd", "frontend", "lint")),
    ("frontend tests", ("bun", "run", "--cwd", "frontend", "test")),
    ("frontend build", ("bun", "run", "--cwd", "frontend", "build")),
    ("browser tests", ("bun", "run", "--cwd", "frontend", "test:e2e")),
)


def run_check(name: str, command: tuple[str, ...]) -> int:
    print(f"[verify] starting {name}: {subprocess.list2cmdline(command)}", flush=True)
    started_at = time.monotonic()
    try:
        result = subprocess.run(command, cwd=ROOT, check=False)
    except OSError as error:
        print(f"[verify] {name} could not start: {error}", file=sys.stderr, flush=True)
        return 2
    finally:
        elapsed = time.monotonic() - started_at
        print(f"[verify] finished {name} in {elapsed:.1f}s", flush=True)
    return result.returncode


def main() -> int:
    for name, command in CHECKS:
        if exit_code := run_check(name, command):
            return exit_code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
