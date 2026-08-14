import type { Citation, DisplayMessage } from "./types";

export type ActiveChatRequest = {
  requestId: string;
  conversationId: string;
  userMessageId: string;
  assistantMessageId: string;
  phase: "queued" | "streaming";
};

export type ChatState = {
  conversationId: string | null;
  messages: DisplayMessage[];
  activeRequest: ActiveChatRequest | null;
};

export type ChatAction =
  | { type: "initialize"; conversationId: string; messages: DisplayMessage[] }
  | { type: "enqueue"; requestId: string; userMessage: DisplayMessage; assistantMessage: DisplayMessage }
  | { type: "started"; requestId: string; userMessageId: string; assistantMessageId: string }
  | { type: "delta"; requestId: string; assistantMessageId: string; text: string }
  | { type: "completed"; requestId: string; assistantMessageId: string; citations: Citation[]; completedAt: string }
  | { type: "failed"; requestId: string; assistantMessageId: string; error: string; retryQuestion: string; completedAt: string }
  | { type: "cancelled"; requestId: string; assistantMessageId: string; completedAt: string }
  | { type: "reset"; conversationId: string };

const FAILED_ANSWER_FALLBACK = "I couldn’t complete that answer.";

export function createChatState(conversationId: string | null = null, messages: DisplayMessage[] = []): ChatState {
  return { conversationId, messages, activeRequest: null };
}

function matchesActiveRequest(state: ChatState, requestId: string, assistantMessageId?: string): state is ChatState & { activeRequest: ActiveChatRequest } {
  return state.activeRequest !== null
    && state.activeRequest.requestId === requestId
    && (assistantMessageId === undefined || state.activeRequest.assistantMessageId === assistantMessageId);
}

function replaceMessage(messages: DisplayMessage[], messageId: string, update: (message: DisplayMessage) => DisplayMessage): DisplayMessage[] {
  return messages.map((message) => message.id === messageId ? update(message) : message);
}

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case "initialize":
      return createChatState(action.conversationId, action.messages);

    case "enqueue": {
      if (
        state.activeRequest !== null
        || state.conversationId === null
        || action.userMessage.conversation_id !== state.conversationId
        || action.assistantMessage.conversation_id !== state.conversationId
      ) {
        return state;
      }

      return {
        ...state,
        messages: [...state.messages, action.userMessage, action.assistantMessage],
        activeRequest: {
          requestId: action.requestId,
          conversationId: state.conversationId,
          userMessageId: action.userMessage.id,
          assistantMessageId: action.assistantMessage.id,
          phase: "queued",
        },
      };
    }

    case "started": {
      if (!matchesActiveRequest(state, action.requestId) || state.activeRequest.phase !== "queued") return state;

      const { userMessageId: localUserMessageId, assistantMessageId: localAssistantMessageId } = state.activeRequest;
      return {
        ...state,
        messages: state.messages.map((message) => {
          if (message.id === localUserMessageId) return { ...message, id: action.userMessageId };
          if (message.id === localAssistantMessageId) return { ...message, id: action.assistantMessageId };
          return message;
        }),
        activeRequest: {
          ...state.activeRequest,
          userMessageId: action.userMessageId,
          assistantMessageId: action.assistantMessageId,
          phase: "streaming",
        },
      };
    }

    case "delta":
      if (!matchesActiveRequest(state, action.requestId, action.assistantMessageId) || state.activeRequest.phase !== "streaming") return state;
      return {
        ...state,
        messages: replaceMessage(state.messages, action.assistantMessageId, (message) => ({ ...message, content: message.content + action.text })),
      };

    case "completed":
      if (!matchesActiveRequest(state, action.requestId, action.assistantMessageId) || state.activeRequest.phase !== "streaming") return state;
      return {
        ...state,
        messages: replaceMessage(state.messages, action.assistantMessageId, (message) => ({
          ...message,
          citations: action.citations,
          completion_state: "completed",
          completed_at: action.completedAt,
          error: undefined,
          retryQuestion: undefined,
        })),
        activeRequest: null,
      };

    case "failed":
      if (!matchesActiveRequest(state, action.requestId, action.assistantMessageId)) return state;
      return {
        ...state,
        messages: replaceMessage(state.messages, action.assistantMessageId, (message) => ({
          ...message,
          content: message.content || FAILED_ANSWER_FALLBACK,
          completion_state: "failed",
          completed_at: action.completedAt,
          error: action.error,
          retryQuestion: action.retryQuestion,
        })),
        activeRequest: null,
      };

    case "cancelled":
      if (!matchesActiveRequest(state, action.requestId, action.assistantMessageId)) return state;
      return {
        ...state,
        messages: replaceMessage(state.messages, action.assistantMessageId, (message) => ({
          ...message,
          completion_state: "cancelled",
          completed_at: action.completedAt,
          error: undefined,
          retryQuestion: undefined,
        })),
        activeRequest: null,
      };

    case "reset":
      return createChatState(action.conversationId);
  }
}
