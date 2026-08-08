import type { Citation, Conversation, IndexingJob, RepositoryCreateResponse, WorkspacePayload } from "./types";
import sseEventContract from "./generated/sse-events.json";

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

export function createRepository(url: string, signal?: AbortSignal): Promise<RepositoryCreateResponse> {
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

export function createConversation(repositoryId: string, signal?: AbortSignal): Promise<Conversation> {
  return requestJson("/api/conversations", {
    method: "POST",
    signal,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ repository_id: repositoryId }),
  });
}

export function createIndexingJob(repositoryId: string, signal?: AbortSignal): Promise<IndexingJob> {
  return requestJson(`/api/repositories/${encodeSegment(repositoryId)}/indexing-jobs`, { method: "POST", signal });
}

export function cancelJob(jobId: string, signal?: AbortSignal): Promise<IndexingJob> {
  return requestJson(`/api/jobs/${encodeSegment(jobId)}/cancel`, { method: "POST", signal });
}

export function getJob(jobId: string, signal?: AbortSignal): Promise<IndexingJob> {
  return requestJson(`/api/jobs/${encodeSegment(jobId)}`, { signal });
}

export function getFile(owner: string, repo: string, path: string, signal?: AbortSignal): Promise<{ path: string; content: string }> {
  return requestJson(`/api/repositories/${encodeSegment(owner)}/${encodeSegment(repo)}/files?path=${encodeURIComponent(path)}`, { signal });
}

export type ChatStreamEvent =
  | { type: "message.started"; repository_id: string; conversation_id: string; message_id: string; user_message_id: string }
  | { type: "message.delta"; repository_id: string; conversation_id: string; message_id: string; text: string }
  | { type: "message.completed"; repository_id: string; conversation_id: string; message_id: string; citations: Citation[] }
  | { type: "message.error"; repository_id: string; conversation_id: string; message_id: string; code: string; message: string };

type JsonSchema = {
  $defs?: Record<string, JsonSchema>;
  $ref?: string;
  oneOf?: JsonSchema[];
  const?: unknown;
  type?: string;
  required?: string[];
  properties?: Record<string, JsonSchema>;
  additionalProperties?: boolean;
  items?: JsonSchema;
  minLength?: number;
  minimum?: number;
  format?: string;
};

type JsonSchemaDocument = { schema: JsonSchema };
const chatSseSchema = sseEventContract as JsonSchemaDocument;
const uuid4Pattern = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function resolveSchema(schema: JsonSchema): JsonSchema {
  if (!schema.$ref) return schema;
  const prefix = "#/$defs/";
  if (!schema.$ref.startsWith(prefix)) return {};
  return chatSseSchema.schema.$defs?.[schema.$ref.slice(prefix.length)] || {};
}

function matchesSchema(value: unknown, sourceSchema: JsonSchema): boolean {
  const schema = resolveSchema(sourceSchema);
  if (schema.oneOf) return schema.oneOf.filter((candidate) => matchesSchema(value, candidate)).length === 1;
  if ("const" in schema && value !== schema.const) return false;
  if (schema.type === "object") {
    if (!isRecord(value)) return false;
    if (schema.required?.some((key) => !(key in value))) return false;
    if (schema.additionalProperties === false && Object.keys(value).some((key) => !schema.properties?.[key])) return false;
    return Object.entries(schema.properties || {}).every(([key, property]) => !(key in value) || matchesSchema(value[key], property));
  }
  if (schema.type === "array") return Array.isArray(value) && value.every((item) => matchesSchema(item, schema.items || {}));
  if (schema.type === "string") return typeof value === "string" && (schema.minLength === undefined || value.length >= schema.minLength) && (schema.format !== "uuid" || uuid4Pattern.test(value));
  if (schema.type === "integer") return typeof value === "number" && Number.isInteger(value) && (schema.minimum === undefined || value >= schema.minimum);
  return false;
}

function citationsHaveValidRanges(event: ChatStreamEvent): boolean {
  return event.type !== "message.completed" || event.citations.every((citation) => citation.start_line <= citation.end_line);
}

function invalidStream(message = "The backend returned an invalid streamed event."): ApiError {
  return new ApiError(502, { code: "invalid_stream", message });
}

function parseSseFrame(frame: string): ChatStreamEvent | null {
  const data = frame
    .split(/\r?\n/)
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart())
    .join("\n");
  if (!data) return null;
  try {
    const event: unknown = JSON.parse(data);
    if (!matchesSchema(event, chatSseSchema.schema) || !citationsHaveValidRanges(event as ChatStreamEvent)) throw invalidStream();
    return event as ChatStreamEvent;
  } catch {
    throw invalidStream();
  }
}

function verifyEventSequence(event: ChatStreamEvent, repositoryId: string, conversationId: string, messageId: string | null, terminal: boolean): { messageId: string; terminal: boolean } {
  if (terminal || event.repository_id !== repositoryId || event.conversation_id !== conversationId) throw invalidStream();
  if (event.type === "message.started") {
    if (messageId !== null) throw invalidStream();
    return { messageId: event.message_id, terminal: false };
  }
  if (messageId === null || event.message_id !== messageId) throw invalidStream();
  if (event.type === "message.delta") return { messageId, terminal: false };
  return { messageId, terminal: true };
}

export async function* streamChat(repositoryId: string, conversationId: string, question: string, signal?: AbortSignal): AsyncGenerator<ChatStreamEvent> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
      method: "POST",
      signal,
      headers: { Accept: "text/event-stream", "Content-Type": "application/json" },
      body: JSON.stringify({ repository_id: repositoryId, conversation_id: conversationId, question }),
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, { code: "network_error", message: "The backend is unavailable. Check that FastAPI is running." });
  }

  if (!response.ok) throw normalizeError(response.status, await readJson(response));
  if (!response.body || response.headers.get("content-type")?.split(";", 1)[0].trim().toLowerCase() !== "text/event-stream") throw invalidStream();

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let messageId: string | null = null;
  let terminal = false;
  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      const frames = buffer.split(/\r?\n\r?\n/);
      buffer = frames.pop() || "";
      for (const frame of frames) {
        const event = parseSseFrame(frame);
        if (event) {
          ({ messageId, terminal } = verifyEventSequence(event, repositoryId, conversationId, messageId, terminal));
          yield event;
        }
      }
      if (done) break;
    }
    if (buffer.trim()) throw terminal ? invalidStream() : new ApiError(502, { code: "stream_incomplete", message: "The answer stream ended before it completed." });
    if (!terminal) throw new ApiError(502, { code: "stream_incomplete", message: "The answer stream ended before it completed." });
  } finally {
    reader.releaseLock();
  }
}
