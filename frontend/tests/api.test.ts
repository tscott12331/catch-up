import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, createApiClient, createRepository, getJob, getWorkspace } from "../app/_lib/api";

const repositoryId = "11111111-1111-4111-8111-111111111111";
const conversationId = "22222222-2222-4222-8222-222222222222";
const assistantId = "33333333-3333-4333-8333-333333333333";
const userId = "44444444-4444-4444-8444-444444444444";
const citation = { id: "55555555-5555-4555-8555-555555555555", passage_id: "66666666-6666-4666-8666-666666666666", revision: "abc", path: "src/a.ts", start_line: 1, end_line: 2 };

const started = { type: "message.started", repository_id: repositoryId, conversation_id: conversationId, message_id: assistantId, user_message_id: userId } as const;
const delta = { type: "message.delta", repository_id: repositoryId, conversation_id: conversationId, message_id: assistantId, text: "Hello" } as const;
const completed = { type: "message.completed", repository_id: repositoryId, conversation_id: conversationId, message_id: assistantId, citations: [citation] } as const;

function jsonResponse(payload: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(payload), {
    ...init,
    headers: { "Content-Type": "application/json", ...init.headers },
  });
}

function sseFrame(event: unknown, newline = "\n"): string {
  return `data: ${JSON.stringify(event)}${newline}${newline}`;
}

function chunkedSseResponse(chunks: string[], contentType = "text/event-stream; charset=utf-8"): Response {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
  return new Response(body, { headers: { "Content-Type": contentType } });
}

function clientReturning(response: Response) {
  const fetchMock = vi.fn().mockResolvedValue(response);
  return { client: createApiClient({ fetch: fetchMock as typeof fetch }), fetchMock };
}

async function consumeStream(body: string, contentType = "text/event-stream"): Promise<void> {
  const { client } = clientReturning(new Response(body, { headers: { "Content-Type": contentType } }));
  for await (const event of client.streamChat(repositoryId, conversationId, "Question")) void event;
}

afterEach(() => vi.unstubAllGlobals());

describe("API client", () => {
  it("supports an injected base URL and fetch implementation", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ repository: { id: repositoryId }, tree: [], selected_file: "README.md", starter_questions: [], messages: [], job: { id: assistantId, status: "indexing", progress: 40 } }))
      .mockResolvedValueOnce(jsonResponse({ id: assistantId, status: "completed", progress: 100 }));
    const client = createApiClient({ baseUrl: "https://api.example.test/", fetch: fetchMock as typeof fetch });

    const workspace = await client.getWorkspace("owner/name", "repo name");
    const job = await client.getJob("job/id");

    expect(workspace.job.progress).toBe(40);
    expect(job.progress).toBe(100);
    expect(fetchMock).toHaveBeenNthCalledWith(1, "https://api.example.test/api/repositories/owner%2Fname/repo%20name/workspace", expect.any(Object));
    expect(fetchMock).toHaveBeenNthCalledWith(2, "https://api.example.test/api/jobs/job%2Fid", expect.any(Object));
    const firstInit = fetchMock.mock.calls[0][1] as RequestInit;
    expect(new Headers(firstInit.headers).get("Accept")).toBe("application/json");
  });

  it("preserves named exports backed by the default client", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ repository: { id: repositoryId }, tree: [], selected_file: "README.md", starter_questions: [], messages: [], job: { id: assistantId, status: "indexing", progress: 40 } }))
      .mockResolvedValueOnce(jsonResponse({ id: assistantId, status: "completed", progress: 100 }));
    vi.stubGlobal("fetch", fetchMock);

    expect((await getWorkspace("acme", "checkout-service")).job.progress).toBe(40);
    expect((await getJob(assistantId)).progress).toBe(100);
  });

  it("maps public error envelopes to ApiError", async () => {
    const { client } = clientReturning(jsonResponse({ error: { code: "invalid_repository_url", message: "Use a public GitHub repository URL.", details: { host: "example.com" } } }, { status: 422 }));

    await expect(client.createRepository("not a repository")).rejects.toMatchObject<ApiError>({
      status: 422,
      code: "invalid_repository_url",
      message: "Use a public GitHub repository URL.",
      details: { host: "example.com" },
    });
  });

  it("keeps the default named repository mutation compatible", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ error: { code: "invalid_repository_url", message: "Use a public GitHub repository URL." } }, { status: 422 })));
    await expect(createRepository("not a repository")).rejects.toMatchObject<ApiError>({ status: 422, code: "invalid_repository_url" });
  });

  it("normalizes network failures but preserves abort errors", async () => {
    const networkClient = createApiClient({ fetch: vi.fn().mockRejectedValue(new TypeError("offline")) as typeof fetch });
    await expect(networkClient.getJob(assistantId)).rejects.toMatchObject<ApiError>({ status: 0, code: "network_error" });

    const abort = new DOMException("Aborted", "AbortError");
    const abortClient = createApiClient({ fetch: vi.fn().mockRejectedValue(abort) as typeof fetch });
    await expect(abortClient.getJob(assistantId)).rejects.toBe(abort);
  });
});

describe("chat SSE client", () => {
  it("parses every generated event shape across chunk and CRLF boundaries", async () => {
    const stream = [sseFrame(started, "\r\n"), sseFrame(delta, "\r\n"), sseFrame(completed, "\r\n")].join("");
    const { client, fetchMock } = clientReturning(chunkedSseResponse([stream.slice(0, 7), stream.slice(7, 89), stream.slice(89)]));

    const events = [];
    for await (const event of client.streamChat(repositoryId, conversationId, "How does checkout work?")) events.push(event);

    expect(events).toEqual([started, delta, completed]);
    const request = fetchMock.mock.calls[0];
    expect(request[0]).toBe("http://localhost:8000/api/chat/stream");
    expect(new Headers((request[1] as RequestInit).headers).get("Accept")).toBe("text/event-stream");
  });

  it("accepts a documented message.error as the terminal event", async () => {
    const terminalError = { type: "message.error", repository_id: repositoryId, conversation_id: conversationId, message_id: assistantId, code: "generation_failed", message: "Could not answer." };
    const { client } = clientReturning(chunkedSseResponse([sseFrame(started), sseFrame(terminalError)]));
    const events = [];
    for await (const event of client.streamChat(repositoryId, conversationId, "Question")) events.push(event);
    expect(events).toEqual([started, terminalError]);
  });

  it.each([
    ["malformed JSON", 'data: {"type":\n\n'],
    ["unknown event", sseFrame({ type: "message.unknown", repository_id: repositoryId })],
    ["an extra property", sseFrame({ ...started, unexpected: true })],
    ["a malformed UUID", sseFrame({ ...started, message_id: "not-a-uuid" })],
    ["missing required correlation", sseFrame({ ...started, user_message_id: undefined })],
    ["invalid citation ranges", sseFrame(started) + sseFrame({ ...completed, citations: [{ ...citation, start_line: 3, end_line: 2 }] })],
    ["an event before message.started", sseFrame(delta)],
    ["a duplicate message.started", sseFrame(started) + sseFrame(started)],
    ["a mismatched repository", sseFrame({ ...started, repository_id: userId })],
    ["a mismatched message", sseFrame(started) + sseFrame({ ...delta, message_id: userId })],
    ["an event after the terminal event", sseFrame(started) + sseFrame(completed) + sseFrame(delta)],
  ])("rejects %s", async (_, body) => {
    await expect(consumeStream(body)).rejects.toMatchObject<ApiError>({ code: "invalid_stream", status: 502 });
  });

  it("rejects a non-SSE content type or missing response body", async () => {
    await expect(consumeStream("{}", "application/json")).rejects.toMatchObject<ApiError>({ code: "invalid_stream", status: 502 });
    const { client } = clientReturning(new Response(null, { headers: { "Content-Type": "text/event-stream" } }));
    await expect(async () => {
      for await (const event of client.streamChat(repositoryId, conversationId, "Question")) void event;
    }).rejects.toMatchObject<ApiError>({ code: "invalid_stream", status: 502 });
  });

  it("normalizes an error response before attempting stream parsing", async () => {
    const { client } = clientReturning(jsonResponse({ error: { code: "conversation_not_found", message: "Conversation was not found." } }, { status: 404 }));
    await expect(async () => {
      for await (const event of client.streamChat(repositoryId, conversationId, "Question")) void event;
    }).rejects.toMatchObject<ApiError>({ status: 404, code: "conversation_not_found" });
  });

  it("normalizes premature EOF before a terminal event", async () => {
    await expect(consumeStream(sseFrame(started))).rejects.toMatchObject<ApiError>({ code: "stream_incomplete", status: 502 });
  });
});
