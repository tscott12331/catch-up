# Catch-up

Catch-up is a local-first codebase onboarding demo: a Next.js frontend talks to
a modular FastAPI backend that serves deterministic repository content,
indexing progress, and streamed answers through replaceable demo adapters.

## Setup and daily workflow

Install [uv](https://docs.astral.sh/uv/) and [Bun](https://bun.sh/), then install
the frontend dependencies once:

```bash
cd frontend
bun install
cd ..
python dev.py
```

`dev.py` starts both processes, forwards normal termination, and stops the
other process if either one exits. Open `http://localhost:3000`. To work in
separate terminals, run `uv run --project backend python backend/run.py` and
`bun --cwd frontend run dev` from the repository root.

## Health and readiness

The backend listens on `http://127.0.0.1:8000` by default. Use these endpoints
for local checks and process supervision:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/ready
```

`/health` confirms the service is alive. `/ready` confirms the application
service container has been constructed. Both are phase-independent and return
JSON.

## Architecture

The backend lives in `backend/catch_up` and has four dependency boundaries:

- `domain` owns the repository, indexing, conversation, message, citation, and
  passage models.
- `application` owns use cases, typed errors, and persistence/content/time
  ports. It has no FastAPI or demo-fixture dependencies.
- `infrastructure` implements the transactional in-memory unit of work and the
  deterministic content, indexing, and answer adapters.
- `api` owns HTTP/SSE contracts, error mapping, request observability, and the
  side-effect-free `create_app(settings, services)` factory.

`backend/catch_up/bootstrap.py` is the composition root. It loads no state at
module import time; the documented `backend/run.py` launcher validates settings,
builds the service container, seeds the canonical demo, and starts Uvicorn.

The frontend keeps generated OpenAPI and SSE types under
`frontend/app/_lib/generated`. Its API modules isolate HTTP transport, error
normalization, SSE framing, and runtime event validation from UI components.

## Configuration

Copy the sanitized examples as a starting point (or export the same variables
in your shell): `backend/.env.example` and `frontend/.env.example`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `HOST` | `127.0.0.1` | Backend bind host. |
| `PORT` | `8000` | Backend bind port (1–65535). |
| `FRONTEND_ORIGINS` | `http://localhost:3000` | Comma-separated allowed browser origins. |
| `ENVIRONMENT` | `development` | `development`, `test`, or `production`. |
| `LOG_LEVEL` | `INFO` | Standard Python log severity. |
| `DEMO_JOB_DURATION_SECONDS` | `1.2` | Positive duration for deterministic demo jobs. |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | Frontend API base URL. |

The backend validates its settings before binding. Invalid values terminate the
launcher with a JSON log entry that explains the setting and valid range.
Every response includes `X-Request-ID`; a valid inbound value is preserved,
otherwise the backend creates one. Application logs are JSON and include that
ID plus safe request/job/message identifiers, never question or source text.

## Checks and troubleshooting

```bash
uv run --project backend python verify.py
```

This is the Phase 1 verification gate: it runs backend tests, verifies checked-in
contracts, runs frontend contract, lint, unit, and build checks, then exercises
the browser workflows. The gate reports each check, refuses to start browser
servers on occupied test ports, and confirms those servers have terminated
before returning. Install Playwright Chromium once before its first run:

```bash
bun x --cwd frontend playwright install chromium
```

If the browser cannot reach the API, first check `/health`, then ensure
`NEXT_PUBLIC_API_BASE_URL` points to the backend and `FRONTEND_ORIGINS` includes
the exact frontend origin. If startup rejects a setting, use the JSON error's
variable name and copy the accepted format from `backend/.env.example`. If a
port is already in use, change `PORT` and the frontend API URL together.
