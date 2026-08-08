# Catch-up frontend

This Next.js app is the presentation layer for the FastAPI demo backend.
Run both processes together from the repository root:

```bash
python dev.py
```

Or run the two processes in separate terminals:

```bash
# terminal 1
cd ..
uv run --project backend python backend/run.py

# terminal 2
cd frontend
bun install
bun run dev
```

The browser API client reads `NEXT_PUBLIC_API_BASE_URL` and defaults to
`http://localhost:8000`. For example, create `frontend/.env.local` with:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

FastAPI must allow the browser origin through `FRONTEND_ORIGIN` (or the
comma-separated `FRONTEND_ORIGINS` setting), normally:

```env
FRONTEND_ORIGIN=http://localhost:3000
```

The app keeps interface copy and the demo CTA URL locally, while repository
metadata, indexing progress, file trees, source content, conversation history,
starter questions, citations, and streamed answers arrive through API requests.

Useful checks:

```bash
bun run lint
bun run build
bun run test
bun run contract:check
```

After a backend API contract update, regenerate the tracked frontend OpenAPI
types with `bun run contract:generate`.
