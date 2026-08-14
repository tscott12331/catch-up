import type { Conversation, IndexingJob, RepositoryCreateResponse, WorkspacePayload } from "../types";
import type { ChatStreamEvent } from "../generated/sse-events";
import { streamChatEvents } from "./sse";
import { createTransport, type TransportOptions } from "./transport";

export type FilePayload = { path: string; content: string };

export type ApiClient = {
  createRepository(url: string, signal?: AbortSignal): Promise<RepositoryCreateResponse>;
  getWorkspace(owner: string, repo: string, signal?: AbortSignal): Promise<WorkspacePayload>;
  createConversation(repositoryId: string, signal?: AbortSignal): Promise<Conversation>;
  createIndexingJob(repositoryId: string, signal?: AbortSignal): Promise<IndexingJob>;
  cancelJob(jobId: string, signal?: AbortSignal): Promise<IndexingJob>;
  getJob(jobId: string, signal?: AbortSignal): Promise<IndexingJob>;
  getFile(owner: string, repo: string, path: string, signal?: AbortSignal): Promise<FilePayload>;
  streamChat(repositoryId: string, conversationId: string, question: string, signal?: AbortSignal): AsyncGenerator<ChatStreamEvent>;
};

function encodeSegment(segment: string): string {
  return encodeURIComponent(segment);
}

export function createApiClient(options: TransportOptions = {}): ApiClient {
  const transport = createTransport(options);
  return {
    createRepository(url, signal) {
      return transport.requestJson("/api/repositories", {
        method: "POST",
        signal,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
    },
    getWorkspace(owner, repo, signal) {
      return transport.requestJson(`/api/repositories/${encodeSegment(owner)}/${encodeSegment(repo)}/workspace`, { signal });
    },
    createConversation(repositoryId, signal) {
      return transport.requestJson("/api/conversations", {
        method: "POST",
        signal,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repository_id: repositoryId }),
      });
    },
    createIndexingJob(repositoryId, signal) {
      return transport.requestJson(`/api/repositories/${encodeSegment(repositoryId)}/indexing-jobs`, { method: "POST", signal });
    },
    cancelJob(jobId, signal) {
      return transport.requestJson(`/api/jobs/${encodeSegment(jobId)}/cancel`, { method: "POST", signal });
    },
    getJob(jobId, signal) {
      return transport.requestJson(`/api/jobs/${encodeSegment(jobId)}`, { signal });
    },
    getFile(owner, repo, path, signal) {
      return transport.requestJson(`/api/repositories/${encodeSegment(owner)}/${encodeSegment(repo)}/files?path=${encodeURIComponent(path)}`, { signal });
    },
    streamChat(repositoryId, conversationId, question, signal) {
      return streamChatEvents(transport, repositoryId, conversationId, question, signal);
    },
  };
}
