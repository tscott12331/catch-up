import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ApiClient } from "../app/_lib/api";
import type { ChatStreamEvent } from "../app/_lib/generated/sse-events";
import { useChat } from "../app/_hooks/use-chat";
import type { Conversation } from "../app/_lib/types";

const repositoryId = "11111111-1111-4111-8111-111111111111";
const conversationId = "22222222-2222-4222-8222-222222222222";
const nextConversationId = "33333333-3333-4333-8333-333333333333";
const assistantId = "44444444-4444-4444-8444-444444444444";
const userId = "55555555-5555-4555-8555-555555555555";

function conversation(id = conversationId): Conversation {
  return { id, repository_id: repositoryId } as Conversation;
}

async function* events(items: ChatStreamEvent[]): AsyncGenerator<ChatStreamEvent> {
  for (const event of items) yield event;
}

function ids(): () => string {
  const values = ["request-1", "local-user", "local-assistant"];
  return () => values.shift()!;
}

describe("useChat", () => {
  it("streams through the reducer and uses caller-injected IDs and timestamps", async () => {
    const streamChat = vi.fn(() => events([
      { type: "message.started", repository_id: repositoryId, conversation_id: conversationId, message_id: assistantId, user_message_id: userId },
      { type: "message.delta", repository_id: repositoryId, conversation_id: conversationId, message_id: assistantId, text: "Hello" },
      { type: "message.completed", repository_id: repositoryId, conversation_id: conversationId, message_id: assistantId, citations: [] },
    ]));
    const client = { streamChat } as unknown as ApiClient;
    const { result } = renderHook(() => useChat({
      client,
      repositoryId,
      initialConversation: conversation(),
      idFactory: ids(),
      now: () => "2026-08-11T00:00:00.000Z",
    }));

    let completed = false;
    await act(async () => { completed = await result.current.runQuestion("  Question  "); });

    expect(completed).toBe(true);
    expect(streamChat).toHaveBeenCalledWith(repositoryId, conversationId, "Question", expect.any(AbortSignal));
    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[0]).toMatchObject({ id: userId, content: "Question", created_at: "2026-08-11T00:00:00.000Z" });
    expect(result.current.messages[1]).toMatchObject({ id: assistantId, content: "Hello", completion_state: "completed" });
    expect(result.current.isThinking).toBe(false);
    expect(result.current.error).toBe("");
  });

  it("marks premature streams failed with retry context", async () => {
    const client = { streamChat: vi.fn(() => events([
      { type: "message.started", repository_id: repositoryId, conversation_id: conversationId, message_id: assistantId, user_message_id: userId },
      { type: "message.delta", repository_id: repositoryId, conversation_id: conversationId, message_id: assistantId, text: "Partial" },
    ])) } as unknown as ApiClient;
    const { result } = renderHook(() => useChat({ client, repositoryId, initialConversation: conversation(), idFactory: ids() }));

    await act(async () => { await result.current.runQuestion("Question"); });

    expect(result.current.messages[1]).toMatchObject({
      content: "Partial",
      completion_state: "failed",
      retryQuestion: "Question",
      error: "The answer stream ended before it completed. Try again.",
    });
    expect(result.current.error).toBe("The answer stream ended before it completed. Try again.");
  });

  it("aborts and hides an old stream when repository identity changes", async () => {
    let signal: AbortSignal | undefined;
    async function* blockedEvents(_repositoryId: string, _conversationId: string, _question: string, nextSignal?: AbortSignal) {
      signal = nextSignal;
      yield { type: "message.started", repository_id: repositoryId, conversation_id: conversationId, message_id: assistantId, user_message_id: userId } as ChatStreamEvent;
      await new Promise<void>((_resolve, reject) => nextSignal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), { once: true }));
    }
    const client = { streamChat: vi.fn(blockedEvents) } as unknown as ApiClient;
    const { result, rerender } = renderHook(
      ({ repo, chat }) => useChat({ client, repositoryId: repo, initialConversation: conversation(chat), idFactory: ids() }),
      { initialProps: { repo: repositoryId, chat: conversationId } },
    );

    let streamPromise!: Promise<boolean>;
    act(() => { streamPromise = result.current.runQuestion("Question"); });
    await waitFor(() => expect(signal).toBeDefined());
    rerender({ repo: "66666666-6666-4666-8666-666666666666", chat: nextConversationId });
    await act(async () => { await streamPromise; });

    expect(signal?.aborted).toBe(true);
    expect(result.current.conversation?.id).toBe(nextConversationId);
    expect(result.current.messages).toEqual([]);
    expect(result.current.error).toBe("");
  });

  it("keeps conversation-reset errors separate from stream errors", async () => {
    const createConversation = vi.fn().mockRejectedValue(new Error("reset failed"));
    const client = { createConversation, streamChat: vi.fn() } as unknown as ApiClient;
    const { result } = renderHook(() => useChat({ client, repositoryId, initialConversation: conversation() }));

    await act(async () => { await result.current.resetConversation(); });

    expect(result.current.resetError).toBe("reset failed");
    expect(result.current.error).toBe("");
    expect(result.current.conversation?.id).toBe(conversationId);
  });

  it("resets to the newly created conversation and clears messages", async () => {
    const createConversation = vi.fn().mockResolvedValue(conversation(nextConversationId));
    const client = { createConversation, streamChat: vi.fn() } as unknown as ApiClient;
    const { result } = renderHook(() => useChat({ client, repositoryId, initialConversation: conversation() }));

    await act(async () => { await result.current.resetConversation(); });

    expect(result.current.conversation?.id).toBe(nextConversationId);
    expect(result.current.messages).toEqual([]);
    expect(createConversation).toHaveBeenCalledWith(repositoryId, expect.any(AbortSignal));
  });
});
