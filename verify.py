"""Run the complete Phase 1 verification gate from the repository root."""

from __future__ import annotations

import socket
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
)
E2E_CHECK = ("browser tests", ("bun", "run", "--cwd", "frontend", "test:e2e"))
E2E_PORTS = (8010, 3100)
PORT_CLOSE_TIMEOUT_SECONDS = 5.0


def listening_ports(ports: tuple[int, ...]) -> list[int]:
    occupied: list[int] = []
    for port in ports:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                occupied.append(port)
        except OSError:
            pass
    return occupied


def wait_for_ports_to_close(ports: tuple[int, ...]) -> list[int]:
    deadline = time.monotonic() + PORT_CLOSE_TIMEOUT_SECONDS
    while occupied := listening_ports(ports):
        if time.monotonic() >= deadline:
            return occupied
        time.sleep(0.1)
    return []


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

    occupied = listening_ports(E2E_PORTS)
    if occupied:
        joined = ", ".join(str(port) for port in occupied)
        print(
            f"[verify] browser tests cannot start because localhost port(s) {joined} are already in use.",
            file=sys.stderr,
        )
        return 2

    name, command = E2E_CHECK
    exit_code = 2
    try:
        exit_code = run_check(name, command)
    finally:
        occupied = wait_for_ports_to_close(E2E_PORTS)
        if occupied:
            joined = ", ".join(str(port) for port in occupied)
            print(
                f"[verify] browser test server cleanup failed; localhost port(s) {joined} still accept connections.",
                file=sys.stderr,
            )
            exit_code = exit_code or 2
        else:
            print("[verify] browser test server cleanup confirmed", flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
