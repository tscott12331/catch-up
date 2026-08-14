import { createApiClient } from "./api/client";

export { ApiError, type ApiErrorPayload } from "./api/errors";
export { createApiClient, type ApiClient, type FilePayload } from "./api/client";
export type { ChatStreamEvent } from "./generated/sse-events";

export const apiClient = createApiClient();

export const createRepository = apiClient.createRepository;
export const getWorkspace = apiClient.getWorkspace;
export const createConversation = apiClient.createConversation;
export const createIndexingJob = apiClient.createIndexingJob;
export const cancelJob = apiClient.cancelJob;
export const getJob = apiClient.getJob;
export const getFile = apiClient.getFile;
export const streamChat = apiClient.streamChat;
