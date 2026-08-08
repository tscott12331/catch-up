import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, createRepository, getJob, getWorkspace, streamChat } from "../app/_lib/api";

function jsonResponse(payload: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(payload), {
    ...init,
    headers: { "Content-Type": "application/json", ...init.headers },
  });
}

afterEach(() => vi.unstubAllGlobals());

describe("API client", () => {
  it("loads workspace and job progress from the public endpoints", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ repository: { id: "repo_acme_checkout-service" }, tree: [], selected_file: "README.md", starter_questions: [], messages: [], job: { id: "job_acme_checkout-service", status: "indexing", progress: 40 } }))
      .mockResolvedValueOnce(jsonResponse({ id: "job_acme_checkout-service", status: "completed", progress: 100 }));
    vi.stubGlobal("fetch", fetchMock);

    const workspace = await getWorkspace("acme", "checkout-service");
    const job = await getJob("job_acme_checkout-service");

    expect(workspace.job.progress).toBe(40);
    expect(job).toEqual({ id: "job_acme_checkout-service", status: "completed", progress: 100 });
    expect(fetchMock).toHaveBeenNthCalledWith(1, "http://localhost:8000/api/repositories/acme/checkout-service/workspace", expect.any(Object));
    expect(fetchMock).toHaveBeenNthCalledWith(2, "http://localhost:8000/api/jobs/job_acme_checkout-service", expect.any(Object));
  });

  it("maps error envelopes to ApiError", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ error: { code: "invalid_repository_url", message: "Use a public GitHub repository URL." } }, { status: 422 })));

    await expect(createRepository("not a repository")).rejects.toMatchObject<ApiError>({ status: 422, code: "invalid_repository_url", message: "Use a public GitHub repository URL." });
  });

  it("parses every documented SSE event shape", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          [
            'data: {"type":"message.started","message_id":"message_1"}\n\n',
            'data: {"type":"message.delta","text":"Hello"}\n\n',
            'data: {"type":"message.completed","citations":[]}\n\n',
            'data: {"type":"message.error","code":"stream_failed","message":"Failed"}\n\n',
          ].join(""),
          { headers: { "Content-Type": "text/event-stream" } },
        ),
      ),
    );

    const events = [];
    for await (const event of streamChat("repo_acme_checkout-service", "How does checkout work?")) events.push(event);

    expect(events).toEqual([
      { type: "message.started", message_id: "message_1" },
      { type: "message.delta", text: "Hello" },
      { type: "message.completed", citations: [] },
      { type: "message.error", code: "stream_failed", message: "Failed" },
    ]);
  });
});
