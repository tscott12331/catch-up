# Catch-up backend

The backend uses FastAPI with framework-independent application services and
replaceable adapters. The current adapters provide deterministic repository
content, indexing progress, and streamed answers. From the repository root,
start it with:

```bash
uv run --project backend python backend/run.py
```

The Next.js app runs separately in `frontend/`:

```bash
cd ../frontend
bun install
bun run dev
```

Configuration:

- `HOST` and `PORT` configure the FastAPI bind address (`127.0.0.1:8000` by default).
- `FRONTEND_ORIGINS` configures allowed browser origins (the legacy singular
  `FRONTEND_ORIGIN` remains supported).
- `ENVIRONMENT`, `LOG_LEVEL`, and `DEMO_JOB_DURATION_SECONDS` are validated at
  startup; see `backend/.env.example` and the root README.
- `NEXT_PUBLIC_API_BASE_URL` belongs to the frontend and points at this API,
  defaulting to `http://localhost:8000`.

## Endpoints

- `GET /health`
- `GET /ready`
- `POST /api/repositories` accepts a public GitHub URL and registers its
  repository, initial active conversation, and indexing job.
- `POST /api/conversations` makes a new active conversation for a registered repository.
- `POST /api/repositories/{repository_id}/indexing-jobs` starts a new indexing job.
- `POST /api/jobs/{job_id}/cancel` cancels a queued or indexing job.
- `GET /api/repositories/{owner}/{repo}/workspace` returns the fixture tree,
  selected file, starter questions, initial messages, and current job.
- `GET /api/repositories/{owner}/{repo}/files?path=...` returns source content
  for a file in the fixture tree.
- `GET /api/jobs/{job_id}` returns server-calculated indexing progress.
- `POST /api/chat/stream` accepts `{ "repository_id": "...", "conversation_id":
  "...", "question": "..." }` and emits `message.started`, `message.delta`,
  `message.completed`, or `message.error` SSE events.

Errors use `{ "error": { "code": "...", "message": "..." } }`. The demo
uses a transactional process-local in-memory unit of work. State resets whenever
the backend process restarts. In `ENVIRONMENT=test`, browser tests can use the
schema-hidden `POST /__test/reset` endpoint to construct a fresh service
container and canonical demo; the endpoint returns 404 elsewhere. Only
registered repositories are available on workspace and file routes.

## Package structure

- `catch_up/domain`: Pydantic domain values and invariants.
- `catch_up/application`: use cases, ports, and transport-independent errors.
- `catch_up/infrastructure`: in-memory persistence and deterministic demo
  adapters/fixtures.
- `catch_up/api`: request/response/SSE contracts and the FastAPI app factory.
- `catch_up/bootstrap.py`: production composition and Uvicorn startup.

Routes resolve an injected `ApplicationServices` container. Tests construct a
fresh app with fake clocks/sleepers, so importing contracts or rendering OpenAPI
does not load environment settings or seed runtime state.

## Contract artifacts and tests

The tracked artifacts in `../contracts/` are generated from the backend:

```bash
uv run --project backend python backend/export_contracts.py
uv run --project backend python backend/export_contracts.py --check
uv run --project backend pytest
```

`export_contracts.py` builds a deterministic, unseeded schema app. It owns
OpenAPI, standalone domain schemas, and the serialized SSE JSON Schema. After a
contract change, run the generator and then regenerate frontend types with
`bun run --cwd frontend contract:generate` from the repository root.
