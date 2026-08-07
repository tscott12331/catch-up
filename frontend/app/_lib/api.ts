import type { Citation, IndexingJob, RepositoryIdentity, WorkspacePayload } from "./types";

const DEFAULT_API_BASE_URL = "http://localhost:8000";
const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || DEFAULT_API_BASE_URL).replace(/\/$/, "");

export type ApiErrorPayload = {
  code: string;
  message: string;
  details?: unknown;
};

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details?: unknown;

  constructor(status: number, payload: ApiErrorPayload) {
    super(payload.message);
    this.name = "ApiError";
    this.status = status;
    this.code = payload.code;
    this.details = payload.details;
  }
}

type ErrorBody = {
  error?: Partial<ApiErrorPayload>;
  detail?: unknown;
};

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function normalizeError(status: number, body: unknown): ApiError {
  const errorBody = body as ErrorBody | null;
  const nested = errorBody?.error;
  if (nested?.message) {
    return new ApiError(status, {
      code: nested.code || "request_failed",
      message: nested.message,
      details: nested.details,
    });
  }

  if (typeof errorBody?.detail === "string") {
    return new ApiError(status, { code: "request_failed", message: errorBody.detail });
  }

  return new ApiError(status, {
    code: "request_failed",
    message: status >= 500 ? "The backend could not complete the request." : "The request could not be completed.",
  });
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { Accept: "application/json", ...init?.headers },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, { code: "network_error", message: "The backend is unavailable. Check that FastAPI is running." });
  }

  const body = await readJson(response);
  if (!response.ok) throw normalizeError(response.status, body);
  return body as T;
}

function encodeSegment(segment: string): string {
  return encodeURIComponent(segment);
}

export function createRepository(url: string, signal?: AbortSignal): Promise<{ repository: RepositoryIdentity; job: IndexingJob }> {
  return requestJson("/api/repositories", {
    method: "POST",
    signal,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
}

export function getWorkspace(owner: string, repo: string, signal?: AbortSignal): Promise<WorkspacePayload> {
  return requestJson(`/api/repositories/${encodeSegment(owner)}/${encodeSegment(repo)}/workspace`, { signal });
}

export function getJob(jobId: string, signal?: AbortSignal): Promise<IndexingJob> {
  return requestJson(`/api/jobs/${encodeSegment(jobId)}`, { signal });
}

export function getFile(owner: string, repo: string, path: string, signal?: AbortSignal): Promise<{ path: string; content: string }> {
  return requestJson(`/api/repositories/${encodeSegment(owner)}/${encodeSegment(repo)}/files?path=${encodeURIComponent(path)}`, { signal });
}

export type ChatStreamEvent =
  | { type: "message.started"; message_id: string }
  | { type: "message.delta"; text: string }
  | { type: "message.completed"; citations: Citation[] }
  | { type: "message.error"; code?: string; message?: string };

function parseSseFrame(frame: string): ChatStreamEvent | null {
  const data = frame
    .split(/\r?\n/)
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart())
    .join("\n");
  if (!data) return null;
  try {
    return JSON.parse(data) as ChatStreamEvent;
  } catch {
    throw new ApiError(502, { code: "invalid_stream", message: "The backend returned an invalid streamed event." });
  }
}

export async function* streamChat(repositoryId: string, question: string, signal?: AbortSignal): AsyncGenerator<ChatStreamEvent> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
      method: "POST",
      signal,
      headers: { Accept: "text/event-stream", "Content-Type": "application/json" },
      body: JSON.stringify({ repository_id: repositoryId, question }),
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, { code: "network_error", message: "The backend is unavailable. Check that FastAPI is running." });
  }

  if (!response.ok) throw normalizeError(response.status, await readJson(response));
  if (!response.body) throw new ApiError(502, { code: "stream_unavailable", message: "The backend did not provide a readable answer stream." });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      const frames = buffer.split(/\r?\n\r?\n/);
      buffer = frames.pop() || "";
      for (const frame of frames) {
        const event = parseSseFrame(frame);
        if (event) yield event;
      }
      if (done) break;
    }
    if (buffer.trim()) {
      const event = parseSseFrame(buffer);
      if (event) yield event;
    }
  } finally {
    reader.releaseLock();
  }
}
