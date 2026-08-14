import { describe, expect, it } from "vitest";
import { chatReducer, createChatState, type ChatState } from "../app/_lib/chat-reducer";
import type { Citation, DisplayMessage } from "../app/_lib/types";

const conversationId = "22222222-2222-4222-8222-222222222222";
const nextConversationId = "33333333-3333-4333-8333-333333333333";
const requestId = "request-1";
const createdAt = "2026-08-10T12:00:00.000Z";
const completedAt = "2026-08-10T12:00:01.000Z";

function message(overrides: Partial<DisplayMessage> = {}): DisplayMessage {
  return {
    id: "message-1",
    conversation_id: conversationId,
    role: "assistant",
    content: "",
    completion_state: "streaming",
    created_at: createdAt,
    completed_at: null,
    citations: [],
    ...overrides,
  };
}

function citation(): Citation {
  return {
    id: "55555555-5555-4555-8555-555555555555",
    passage_id: "66666666-6666-4666-8666-666666666666",
    revision: "abc123",
    path: "src/checkout.ts",
    start_line: 4,
    end_line: 8,
  };
}

function enqueue(state: ChatState = createChatState(conversationId)): ChatState {
  return chatReducer(state, {
    type: "enqueue",
    requestId,
    userMessage: message({ id: "local-user", role: "user", content: "How does checkout work?", completion_state: "completed", completed_at: createdAt }),
    assistantMessage: message({ id: "local-assistant" }),
  });
}

function start(state: ChatState = enqueue()): ChatState {
  return chatReducer(state, {
    type: "started",
    requestId,
    userMessageId: "server-user",
    assistantMessageId: "server-assistant",
  });
}

describe("chatReducer", () => {
  it("initializes server messages and clears any active request", () => {
    const seeded = [message({ id: "seed", completion_state: "completed", completed_at: createdAt })];
    const state = chatReducer(enqueue(), { type: "initialize", conversationId, messages: seeded });

    expect(state).toEqual({ conversationId, messages: seeded, activeRequest: null });
  });

  it("enqueues caller-created messages and rejects a concurrent request", () => {
    const state = enqueue();
    const concurrent = enqueue(state);

    expect(state.messages.map(({ id }) => id)).toEqual(["local-user", "local-assistant"]);
    expect(state.activeRequest).toEqual({
      requestId,
      conversationId,
      userMessageId: "local-user",
      assistantMessageId: "local-assistant",
      phase: "queued",
    });
    expect(concurrent).toBe(state);
  });

  it("rejects messages for a different or missing conversation", () => {
    const missingConversation = enqueue(createChatState());
    const wrongConversation = chatReducer(createChatState(nextConversationId), {
      type: "enqueue",
      requestId,
      userMessage: message({ id: "local-user", role: "user" }),
      assistantMessage: message({ id: "local-assistant" }),
    });

    expect(missingConversation).toEqual(createChatState());
    expect(wrongConversation).toEqual(createChatState(nextConversationId));
  });

  it("replaces temporary IDs when the server starts the message", () => {
    const state = start();

    expect(state.messages.map(({ id }) => id)).toEqual(["server-user", "server-assistant"]);
    expect(state.activeRequest).toMatchObject({
      userMessageId: "server-user",
      assistantMessageId: "server-assistant",
      phase: "streaming",
    });
  });

  it("appends deltas without mutating the previous state", () => {
    const started = start();
    const first = chatReducer(started, { type: "delta", requestId, assistantMessageId: "server-assistant", text: "Checkout " });
    const second = chatReducer(first, { type: "delta", requestId, assistantMessageId: "server-assistant", text: "uses a saga." });

    expect(started.messages[1].content).toBe("");
    expect(second.messages[1].content).toBe("Checkout uses a saga.");
  });

  it("completes the active assistant with citations", () => {
    const state = chatReducer(start(), {
      type: "completed",
      requestId,
      assistantMessageId: "server-assistant",
      citations: [citation()],
      completedAt,
    });

    expect(state.messages[1]).toMatchObject({ completion_state: "completed", completed_at: completedAt, citations: [citation()] });
    expect(state.activeRequest).toBeNull();
  });

  it("marks failures, preserves partial content, and records retry context", () => {
    const partial = chatReducer(start(), { type: "delta", requestId, assistantMessageId: "server-assistant", text: "Partial" });
    const failed = chatReducer(partial, {
      type: "failed",
      requestId,
      assistantMessageId: "server-assistant",
      error: "The stream disconnected.",
      retryQuestion: "How does checkout work?",
      completedAt,
    });

    expect(failed.messages[1]).toMatchObject({
      content: "Partial",
      completion_state: "failed",
      completed_at: completedAt,
      error: "The stream disconnected.",
      retryQuestion: "How does checkout work?",
    });
    expect(failed.activeRequest).toBeNull();
  });

  it("uses fallback content when a failure occurs before any delta", () => {
    const queued = enqueue();
    const failed = chatReducer(queued, {
      type: "failed",
      requestId,
      assistantMessageId: "local-assistant",
      error: "The request failed.",
      retryQuestion: "Retry me",
      completedAt,
    });

    expect(failed.messages[1].content).toBe("I couldn’t complete that answer.");
  });

  it("marks a queued or streaming assistant as cancelled", () => {
    const state = chatReducer(start(), {
      type: "cancelled",
      requestId,
      assistantMessageId: "server-assistant",
      completedAt,
    });

    expect(state.messages[1]).toMatchObject({ completion_state: "cancelled", completed_at: completedAt });
    expect(state.activeRequest).toBeNull();
  });

  it("ignores events from stale requests and mismatched message IDs", () => {
    const state = start();
    const staleRequest = chatReducer(state, { type: "delta", requestId: "old-request", assistantMessageId: "server-assistant", text: "stale" });
    const staleMessage = chatReducer(state, { type: "delta", requestId, assistantMessageId: "old-assistant", text: "stale" });
    const duplicateStart = chatReducer(state, { type: "started", requestId, userMessageId: "other-user", assistantMessageId: "other-assistant" });

    expect(staleRequest).toBe(state);
    expect(staleMessage).toBe(state);
    expect(duplicateStart).toBe(state);
  });

  it("resets to a new conversation and rejects late events from the previous stream", () => {
    const reset = chatReducer(start(), { type: "reset", conversationId: nextConversationId });
    const lateCompletion = chatReducer(reset, {
      type: "completed",
      requestId,
      assistantMessageId: "server-assistant",
      citations: [citation()],
      completedAt,
    });

    expect(reset).toEqual(createChatState(nextConversationId));
    expect(lateCompletion).toBe(reset);
  });
});
