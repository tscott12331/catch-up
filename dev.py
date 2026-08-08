"""Start the local backend and frontend together, stopping both on any failure."""

from __future__ import annotations

import logging
import signal
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
logger = logging.getLogger("catch_up.dev")


def stop(process: subprocess.Popen[object]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    processes: list[tuple[str, subprocess.Popen[object]]] = []

    def shutdown(_: int, __: object) -> None:
        logger.info("Stopping local development processes")
        for _, process in reversed(processes):
            stop(process)
        raise SystemExit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    commands = (
        ("backend", ["uv", "run", "--project", "backend", "python", "backend/run.py"]),
        ("frontend", ["bun", "run", "--cwd", "frontend", "dev"]),
    )
    try:
        for name, command in commands:
            logger.info("Starting %s", name)
            processes.append((name, subprocess.Popen(command, cwd=ROOT)))
    except OSError as error:
        logger.error("Could not start local development: %s", error)
        for _, process in reversed(processes):
            stop(process)
        return 2

    while True:
        for name, process in processes:
            exit_code = process.poll()
            if exit_code is not None:
                logger.error("%s exited with code %s; stopping the remaining process", name, exit_code)
                for other_name, other_process in reversed(processes):
                    if other_name != name:
                        stop(other_process)
                return exit_code or 1
        time.sleep(0.1)


if __name__ == "__main__":
    raise SystemExit(main())
