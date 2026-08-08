# Catch-up backend

The demo backend uses FastAPI and serves repository metadata, the fixture
workspace, source previews, deterministic indexing progress, and streamed
answers. Start it from this directory with:

```bash
uv run main.py
```

The Next.js app runs separately in `frontend/`:

```bash
cd ../frontend
bun install
bun run dev
```

Configuration:

- `HOST` and `PORT` configure the FastAPI bind address (`127.0.0.1:8000` by default).
- `FRONTEND_ORIGIN` configures one allowed browser origin; use
  `FRONTEND_ORIGINS` with comma-separated origins for more than one.
- `NEXT_PUBLIC_API_BASE_URL` belongs to the frontend and points at this API,
  defaulting to `http://localhost:8000`.

## Endpoints

- `GET /health`
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
- `POST /api/chat/stream` accepts `{ "repository_id": "...", "question": "..." }`
  and emits `message.started`, `message.delta`, `message.completed`, or
  `message.error` SSE events.

Errors use `{ "error": { "code": "...", "message": "..." } }`. The demo
uses process-local in-memory stores. They reset whenever the backend process
restarts; tests can call `reset_in_memory_stores()` to reset them explicitly.
Only registered repositories are available on workspace and file routes. The
checkout fixture is seeded on each reset so the demo flow remains available.

## Contract artifacts and tests

The tracked artifacts in `../contracts/` are generated from the backend:

```bash
uv run --project backend python backend/export_contracts.py
uv run --project backend python backend/export_contracts.py --check
uv run --project backend pytest
```
