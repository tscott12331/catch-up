"use client";

import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import type { ApiClient } from "../_lib/api";
import { chatReducer, createChatState } from "../_lib/chat-reducer";
import type { Conversation, DisplayMessage } from "../_lib/types";

const EMPTY_MESSAGES: DisplayMessage[] = [];

function defaultIdFactory(): string {
  return globalThis.crypto.randomUUID();
}

function defaultNow(): string {
  return new Date().toISOString();
}

function messageFrom(error: unknown): string {
  return error instanceof Error ? error.message : "The answer could not be loaded. Try again.";
}

export type UseChatOptions = {
  client: ApiClient;
  repositoryId: string | null;
  initialConversation: Conversation | null;
  initialMessages?: DisplayMessage[];
  idFactory?: () => string;
  now?: () => string;
};

export type ChatSessionState = {
  conversation: Conversation | null;
  messages: DisplayMessage[];
  input: string;
  setInput: (value: string) => void;
  isThinking: boolean;
  error: string;
  resetError: string;
  runQuestion: (question: string) => Promise<boolean>;
  retryQuestion: (question: string) => Promise<boolean>;
  cancel: () => void;
  resetConversation: () => Promise<Conversation | null>;
};

export function useChat({
  client,
  repositoryId,
  initialConversation,
  initialMessages = EMPTY_MESSAGES,
  idFactory = defaultIdFactory,
  now = defaultNow,
}: UseChatOptions): ChatSessionState {
  const [state, dispatch] = useReducer(
    chatReducer,
    undefined,
    () => createChatState(initialConversation?.id ?? null, initialMessages),
  );
  const [conversation, setConversation] = useState<Conversation | null>(initialConversation);
  const [input, setInput] = useState("");
  const [error, setError] = useState("");
  const [resetError, setResetError] = useState("");
  const generation = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const busy = useRef(false);
  const initialConversationRef = useRef(initialConversation);

  useEffect(() => {
    initialConversationRef.current = initialConversation;
  }, [initialConversation]);

  useEffect(() => {
    const resetGeneration = ++generation.current;
    controller.current?.abort();
    controller.current = null;
    busy.current = false;
    queueMicrotask(() => {
      if (generation.current !== resetGeneration) return;
      const nextConversation = initialConversationRef.current;
      setConversation(nextConversation);
      setInput("");
      setError("");
      setResetError("");
      if (nextConversation) {
        dispatch({ type: "initialize", conversationId: nextConversation.id, messages: initialMessages });
      }
    });

    return () => {
      generation.current += 1;
      controller.current?.abort();
      controller.current = null;
      busy.current = false;
    };
  }, [initialConversation?.id, initialMessages, repositoryId]);

  const runQuestion = useCallback(async (rawQuestion: string): Promise<boolean> => {
    const question = rawQuestion.trim();
    if (!repositoryId || !conversation || !question || busy.current) return false;

    busy.current = true;
    controller.current?.abort();
    const streamController = new AbortController();
    controller.current = streamController;
    const streamGeneration = ++generation.current;
    const requestId = idFactory();
    const localUserId = idFactory();
    const localAssistantId = idFactory();
    const createdAt = now();
    let assistantMessageId = localAssistantId;
    let terminal = false;
    let streamError = "";

    dispatch({
      type: "enqueue",
      requestId,
      userMessage: {
        id: localUserId,
        conversation_id: conversation.id,
        role: "user",
        content: question,
        completion_state: "completed",
        created_at: createdAt,
        completed_at: createdAt,
        citations: [],
      },
      assistantMessage: {
        id: localAssistantId,
        conversation_id: conversation.id,
        role: "assistant",
        content: "",
        completion_state: "streaming",
        created_at: createdAt,
        completed_at: null,
        citations: [],
      },
    });
    setInput("");
    setError("");

    try {
      for await (const event of client.streamChat(repositoryId, conversation.id, question, streamController.signal)) {
        if (streamController.signal.aborted || generation.current !== streamGeneration) return false;

        if (event.type === "message.started") {
          assistantMessageId = event.message_id;
          dispatch({
            type: "started",
            requestId,
            userMessageId: event.user_message_id,
            assistantMessageId: event.message_id,
          });
        } else if (event.type === "message.delta") {
          dispatch({ type: "delta", requestId, assistantMessageId: event.message_id, text: event.text });
        } else if (event.type === "message.completed") {
          terminal = true;
          dispatch({
            type: "completed",
            requestId,
            assistantMessageId: event.message_id,
            citations: event.citations,
            completedAt: now(),
          });
        } else if (event.type === "message.error") {
          streamError = event.message || "The answer stream failed. Try the question again.";
          break;
        }
      }
      if (!terminal && !streamError) streamError = "The answer stream ended before it completed. Try again.";
    } catch (requestError) {
      if (streamController.signal.aborted) {
        if (generation.current === streamGeneration) {
          terminal = true;
          dispatch({ type: "cancelled", requestId, assistantMessageId, completedAt: now() });
        }
      } else {
        streamError = messageFrom(requestError);
      }
    } finally {
      if (generation.current === streamGeneration) {
        if (!terminal && streamError) {
          dispatch({
            type: "failed",
            requestId,
            assistantMessageId,
            error: streamError,
            retryQuestion: question,
            completedAt: now(),
          });
          setError(streamError);
        }
        busy.current = false;
        if (controller.current === streamController) controller.current = null;
      }
    }
    return terminal && !streamError;
  }, [client, conversation, idFactory, now, repositoryId]);

  const cancel = useCallback(() => {
    controller.current?.abort();
  }, []);

  const resetConversation = useCallback(async (): Promise<Conversation | null> => {
    if (!repositoryId) return null;
    generation.current += 1;
    controller.current?.abort();
    busy.current = false;
    const resetGeneration = generation.current;
    const resetController = new AbortController();
    controller.current = resetController;
    setError("");
    setResetError("");

    try {
      const nextConversation = await client.createConversation(repositoryId, resetController.signal);
      if (resetController.signal.aborted || generation.current !== resetGeneration) return null;
      setConversation(nextConversation);
      setInput("");
      dispatch({ type: "reset", conversationId: nextConversation.id });
      return nextConversation;
    } catch (requestError) {
      if (!resetController.signal.aborted && generation.current === resetGeneration) {
        setResetError(requestError instanceof Error ? requestError.message : "A new conversation could not be created.");
      }
      return null;
    } finally {
      if (generation.current === resetGeneration && controller.current === resetController) controller.current = null;
    }
  }, [client, repositoryId]);

  const sessionMatchesState = conversation !== null && state.conversationId === conversation.id;
  return {
    conversation,
    messages: sessionMatchesState ? state.messages : [],
    input,
    setInput,
    isThinking: sessionMatchesState && state.activeRequest !== null,
    error,
    resetError,
    runQuestion,
    retryQuestion: runQuestion,
    cancel,
    resetConversation,
  };
}
