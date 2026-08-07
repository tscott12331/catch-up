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
- `POST /api/repositories` accepts a public GitHub URL and returns repository
  identity plus an indexing job.
- `GET /api/repositories/{owner}/{repo}/workspace` returns the fixture tree,
  selected file, starter questions, initial messages, and current job.
- `GET /api/repositories/{owner}/{repo}/files?path=...` returns source content
  for a file in the fixture tree.
- `GET /api/jobs/{job_id}` returns server-calculated indexing progress.
- `POST /api/chat/stream` accepts `{ "repository_id": "...", "question": "..." }`
  and emits `message.started`, `message.delta`, `message.completed`, or
  `message.error` SSE events.

Errors use `{ "error": { "code": "...", "message": "..." } }`. The demo
does not persist repositories or conversations; any valid repository route is
constructed from its owner and name and receives the same fixture content.
