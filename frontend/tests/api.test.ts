import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, createRepository, getJob, getWorkspace, streamChat } from "../app/_lib/api";

const repositoryId = "11111111-1111-4111-8111-111111111111";
const conversationId = "22222222-2222-4222-8222-222222222222";
const assistantId = "33333333-3333-4333-8333-333333333333";
const userId = "44444444-4444-4444-8444-444444444444";
const citation = { id: "55555555-5555-4555-8555-555555555555", passage_id: "66666666-6666-4666-8666-666666666666", revision: "abc", path: "src/a.ts", start_line: 1, end_line: 2 };

function jsonResponse(payload: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(payload), {
    ...init,
    headers: { "Content-Type": "application/json", ...init.headers },
  });
}

async function consumeStream(body: string, contentType = "text/event-stream"): Promise<void> {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(body, { headers: { "Content-Type": contentType } })));
  for await (const event of streamChat(repositoryId, conversationId, "Question")) void event;
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
            `data: {"type":"message.started","repository_id":"${repositoryId}","conversation_id":"${conversationId}","message_id":"${assistantId}","user_message_id":"${userId}"}\n\n`,
            `data: {"type":"message.delta","repository_id":"${repositoryId}","conversation_id":"${conversationId}","message_id":"${assistantId}","text":"Hello"}\n\n`,
            `data: {"type":"message.completed","repository_id":"${repositoryId}","conversation_id":"${conversationId}","message_id":"${assistantId}","citations":[${JSON.stringify(citation)}]}\n\n`,
          ].join(""),
          { headers: { "Content-Type": "text/event-stream" } },
        ),
      ),
    );

    const events = [];
    for await (const event of streamChat(repositoryId, conversationId, "How does checkout work?")) events.push(event);

    expect(events).toEqual([
      { type: "message.started", repository_id: repositoryId, conversation_id: conversationId, message_id: assistantId, user_message_id: userId },
      { type: "message.delta", repository_id: repositoryId, conversation_id: conversationId, message_id: assistantId, text: "Hello" },
      { type: "message.completed", repository_id: repositoryId, conversation_id: conversationId, message_id: assistantId, citations: [citation] },
    ]);
  });

  it.each([
    ["malformed JSON", 'data: {"type":\n\n'],
    ["unknown event", `data: {"type":"message.unknown","repository_id":"${repositoryId}"}\n\n`],
    ["missing required correlation", `data: {"type":"message.started","repository_id":"${repositoryId}","conversation_id":"${conversationId}","message_id":"${assistantId}"}\n\n`],
    ["invalid citation", `data: {"type":"message.started","repository_id":"${repositoryId}","conversation_id":"${conversationId}","message_id":"${assistantId}","user_message_id":"${userId}"}\n\ndata: {"type":"message.completed","repository_id":"${repositoryId}","conversation_id":"${conversationId}","message_id":"${assistantId}","citations":[${JSON.stringify({ ...citation, start_line: 3, end_line: 2 })}]}\n\n`],
  ])("rejects %s stream data", async (_, body) => {
    await expect(consumeStream(body)).rejects.toMatchObject<ApiError>({ code: "invalid_stream", status: 502 });
  });

  it("rejects a non-SSE content type", async () => {
    await expect(consumeStream("{}", "application/json")).rejects.toMatchObject<ApiError>({ code: "invalid_stream", status: 502 });
  });

  it("normalizes a premature EOF after a valid started event", async () => {
    const body = `data: {"type":"message.started","repository_id":"${repositoryId}","conversation_id":"${conversationId}","message_id":"${assistantId}","user_message_id":"${userId}"}\n\n`;
    await expect(consumeStream(body)).rejects.toMatchObject<ApiError>({ code: "stream_incomplete", status: 502 });
  });
});
