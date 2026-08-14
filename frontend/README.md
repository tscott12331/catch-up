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

## API and generated contracts

`app/_lib/api/transport.ts` owns HTTP transport and error normalization;
`app/_lib/api/client.ts` owns endpoint calls; and the SSE modules own framing,
sequence handling, and runtime validation. Chat state transitions are isolated
in `app/_lib/chat-reducer.ts`.

Do not hand-edit files under `app/_lib/generated`. `openapi.ts` is generated
from `../contracts/openapi.json`; `sse-events.json` is copied from the backend's
serialized event schema; and `sse-events.ts` is generated from that JSON Schema.
The runtime SSE validator consumes the same checked-in schema as the generated
TypeScript type.

## Browser verification

The deterministic Playwright suite starts its own backend in `ENVIRONMENT=test`
on port 8010 and a frontend on port 3100. It resets the in-memory fixture state
through a test-only endpoint before every scenario; that endpoint returns 404 in
development and production. Run it after installing the Chromium browser once:

```bash
bun x playwright install chromium
bun run test:e2e
```

`test:e2e` always starts isolated servers and does not reuse a locally running
development backend.

After a backend API or SSE contract update, regenerate all tracked frontend
contract artifacts with `bun run contract:generate`, then run
`bun run contract:check`.
