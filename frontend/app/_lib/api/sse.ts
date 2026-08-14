import type { ChatStreamEvent } from "../generated/sse-events";
import { ApiError, invalidStream } from "./errors";
import { isChatStreamEvent } from "./sse-validator";
import type { ApiTransport } from "./transport";

type SequenceState = {
  messageId: string | null;
  terminal: boolean;
};

function citationsHaveValidRanges(event: ChatStreamEvent): boolean {
  return event.type !== "message.completed" || event.citations.every((citation) => citation.start_line <= citation.end_line);
}

export function parseSseFrame(frame: string): ChatStreamEvent | null {
  const data = frame
    .split(/\r?\n/)
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart())
    .join("\n");
  if (!data) return null;

  let value: unknown;
  try {
    value = JSON.parse(data);
  } catch {
    throw invalidStream();
  }
  if (!isChatStreamEvent(value) || !citationsHaveValidRanges(value)) throw invalidStream();
  return value;
}

export function verifyEventSequence(
  event: ChatStreamEvent,
  repositoryId: string,
  conversationId: string,
  state: SequenceState,
): SequenceState {
  if (state.terminal || event.repository_id !== repositoryId || event.conversation_id !== conversationId) throw invalidStream();
  if (event.type === "message.started") {
    if (state.messageId !== null) throw invalidStream();
    return { messageId: event.message_id, terminal: false };
  }
  if (state.messageId === null || event.message_id !== state.messageId) throw invalidStream();
  return { messageId: state.messageId, terminal: event.type !== "message.delta" };
}

export async function* streamChatEvents(
  transport: ApiTransport,
  repositoryId: string,
  conversationId: string,
  question: string,
  signal?: AbortSignal,
): AsyncGenerator<ChatStreamEvent> {
  const response = await transport.request("/api/chat/stream", {
    method: "POST",
    signal,
    headers: { Accept: "text/event-stream", "Content-Type": "application/json" },
    body: JSON.stringify({ repository_id: repositoryId, conversation_id: conversationId, question }),
  });

  if (!response.ok) throw await transport.errorFromResponse(response);
  const contentType = response.headers.get("content-type")?.split(";", 1)[0].trim().toLowerCase();
  if (!response.body || contentType !== "text/event-stream") throw invalidStream();

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let state: SequenceState = { messageId: null, terminal: false };
  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
      const frames = buffer.split(/\r?\n\r?\n/);
      buffer = frames.pop() ?? "";
      for (const frame of frames) {
        const event = parseSseFrame(frame);
        if (event) {
          state = verifyEventSequence(event, repositoryId, conversationId, state);
          yield event;
        }
      }
      if (done) break;
    }

    if (buffer.trim()) {
      if (state.terminal) throw invalidStream();
      throw new ApiError(502, { code: "stream_incomplete", message: "The answer stream ended before it completed." });
    }
    if (!state.terminal) {
      throw new ApiError(502, { code: "stream_incomplete", message: "The answer stream ended before it completed." });
    }
  } finally {
    reader.releaseLock();
  }
}
