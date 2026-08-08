"""Run the complete Phase 1 verification gate from the repository root."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
COMMANDS = (
    ("uv", "run", "--project", "backend", "pytest"),
    ("uv", "run", "--project", "backend", "python", "backend/export_contracts.py", "--check"),
    ("bun", "run", "--cwd", "frontend", "contract:check"),
    ("bun", "run", "--cwd", "frontend", "lint"),
    ("bun", "run", "--cwd", "frontend", "test"),
    ("bun", "run", "--cwd", "frontend", "build"),
    ("bun", "run", "--cwd", "frontend", "test:e2e"),
)


def main() -> int:
    for command in COMMANDS:
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
