"use client";

import type { SubmitEvent } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createConversation, createIndexingJob, getFile, getJob, getWorkspace, streamChat } from "../_lib/api";
import type { RepositoryRoute } from "../_lib/repository";
import type { Citation, DisplayMessage, IndexingJob, TreeNode, WorkspacePayload } from "../_lib/types";
import { ChatPanel } from "./chat-panel";
import { RepositoryExplorer } from "./repository-explorer";
import { Sidebar } from "./sidebar";
import { WorkspaceHeader } from "./workspace-header";
import styles from "./workspace.module.css";

type WorkspaceProps = { repository: RepositoryRoute };

type PreviewState =
  | { status: "idle" | "loading" }
  | { status: "ready"; content: string }
  | { status: "unavailable"; message: string };

function filterTree(nodes: TreeNode[], query: string): TreeNode[] {
  if (!query) return nodes;
  return nodes.flatMap((node) => {
    const children = node.children ? filterTree(node.children, query) : [];
    if (node.name.toLowerCase().includes(query) || children.length > 0) {
      return [{ ...node, ...(node.children ? { children } : {}) }];
    }
    return [];
  });
}

function parentFolders(filePath: string): Set<string> {
  const parts = filePath.split("/");
  const folders = new Set<string>();
  for (let index = 1; index < parts.length; index += 1) {
    folders.add(parts.slice(0, index).join("/"));
  }
  return folders;
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

export function Workspace({ repository: routeRepository }: WorkspaceProps) {
  const [workspace, setWorkspace] = useState<WorkspacePayload | null>(null);
  const [workspaceLoading, setWorkspaceLoading] = useState(true);
  const [workspaceError, setWorkspaceError] = useState("");
  const [job, setJob] = useState<IndexingJob | null>(null);
  const [jobError, setJobError] = useState("");
  const [input, setInput] = useState("");
  const [isThinking, setIsThinking] = useState(false);
  const [activeFile, setActiveFile] = useState("");
  const [explorerFilter, setExplorerFilter] = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [citationHighlight, setCitationHighlight] = useState<Citation | null>(null);
  const [preview, setPreview] = useState<PreviewState>({ status: "idle" });
  const streamController = useRef<AbortController | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true

    return () => {
      mounted.current = false;
      streamController.current?.abort();
    };
  }, []);

  const loadWorkspace = useCallback(async () => {
    const controller = new AbortController();
    try {
      const payload = await getWorkspace(routeRepository.owner, routeRepository.name, controller.signal);
      if (!mounted.current) return;
      setWorkspace(payload);
      setJob(payload.job);
      setJobError(payload.job.status === "failed" ? "Indexing failed. Retry the workspace to check again." : payload.job.status === "cancelled" ? "Indexing was cancelled." : "");
      setActiveFile(payload.selected_file);
      setExpanded(parentFolders(payload.selected_file));
      setMessages(payload.messages);
      setPreview({ status: "loading" });
    } catch (error) {
      if (!mounted.current || isAbortError(error)) return;
      setWorkspaceError(error instanceof Error ? error.message : "The workspace could not be loaded.");
    } finally {
      if (mounted.current) setWorkspaceLoading(false);
    }
  }, [routeRepository.name, routeRepository.owner]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadWorkspace(), 0);
    return () => window.clearTimeout(timer);
  }, [loadWorkspace]);

  useEffect(() => {
    if (!workspace || workspace.job.status === "completed" || workspace.job.status === "failed" || workspace.job.status === "cancelled") return;
    const jobId = workspace.job.id;
    let cancelled = false;
    let timer: number | undefined;
    const controller = new AbortController();

    async function poll() {
      try {
        const nextJob = await getJob(jobId, controller.signal);
        if (cancelled) return;
        setJob((current) => {
          if (!current || nextJob.status === "completed" || nextJob.status === "failed" || nextJob.status === "cancelled" || nextJob.progress >= current.progress) return nextJob;
          return current;
        });
        if (nextJob.status === "completed" || nextJob.status === "failed" || nextJob.status === "cancelled") {
          if (nextJob.status === "failed") setJobError("Indexing failed. Retry the workspace to check again.");
          if (nextJob.status === "cancelled") setJobError("Indexing was cancelled.");
          return;
        }
        timer = window.setTimeout(() => void poll(), 450);
      } catch (error) {
        if (cancelled || isAbortError(error)) return;
        setJobError(error instanceof Error ? error.message : "Indexing progress could not be loaded.");
      }
    }

    void poll();
    return () => {
      cancelled = true;
      controller.abort();
      if (timer) window.clearTimeout(timer);
    };
  }, [workspace]);

  useEffect(() => {
    if (!workspace || !activeFile) return;
    const controller = new AbortController();
    void getFile(workspace.repository.owner, workspace.repository.name, activeFile, controller.signal)
      .then((file) => {
        if (!controller.signal.aborted && mounted.current) setPreview({ status: "ready", content: file.content });
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted && mounted.current) {
          setPreview({ status: "unavailable", message: error instanceof Error ? error.message : "Source content is unavailable." });
        }
      });
    return () => controller.abort();
  }, [activeFile, workspace]);

  const visibleTree = useMemo(() => {
    if (!workspace) return [];
    return filterTree(workspace.tree, explorerFilter.trim().toLowerCase());
  }, [explorerFilter, workspace]);

  function toggleFolder(path: string) {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }

  function selectFile(path: string) {
    setCitationHighlight(null);
    setPreview({ status: "loading" });
    setActiveFile(path);
  }

  function selectCitation(citation: Citation) {
    setExpanded((current) => new Set([...current, ...parentFolders(citation.path)]));
    setCitationHighlight(citation);
    if (citation.path === activeFile) return;
    setPreview({ status: "loading" });
    setActiveFile(citation.path);
  }

  function closePreview() {
    setCitationHighlight(null);
    setPreview({ status: "idle" });
    setActiveFile("");
  }

  function retryWorkspace() {
    setWorkspaceLoading(true);
    setWorkspaceError("");
    setJobError("");
    if (!workspace) {
      void loadWorkspace();
      return;
    }
    void createIndexingJob(workspace.repository.id)
      .then((nextJob) => {
        if (!mounted.current) return;
        setJob(nextJob);
        setWorkspace((current) => current ? { ...current, job: nextJob } : current);
      })
      .catch((error: unknown) => {
        if (mounted.current) setJobError(error instanceof Error ? error.message : "Indexing could not be restarted.");
      })
      .finally(() => {
        if (mounted.current) setWorkspaceLoading(false);
      });
  }

  const runQuestion = useCallback(async (rawQuestion: string) => {
    if (!workspace || isThinking) return;
    const question = rawQuestion.trim();
    if (!question) return;

    streamController.current?.abort();
    const controller = new AbortController();
    streamController.current = controller;
    const userId = `user-${Date.now()}`;
    const localAssistantId = `assistant-${Date.now()}`;
    const createdAt = new Date().toISOString();
    let assistantId = localAssistantId;
    let completed = false;
    let streamError = "";
    setMessages((current) => [
      ...current,
      { id: userId, conversation_id: workspace.conversation.id, role: "user", content: question, completion_state: "completed", created_at: createdAt, completed_at: createdAt, citations: [] },
      { id: localAssistantId, conversation_id: workspace.conversation.id, role: "assistant", content: "", completion_state: "streaming", created_at: createdAt, completed_at: null, citations: [] },
    ]);
    setInput("");
    setIsThinking(true);

    try {
      for await (const event of streamChat(workspace.repository.id, workspace.conversation.id, question, controller.signal)) {
        if (event.type === "message.started") {
          assistantId = event.message_id;
          setMessages((current) => current.map((message) => {
            if (message.id === localAssistantId) return { ...message, id: assistantId };
            if (message.id === userId) return { ...message, id: event.user_message_id };
            return message;
          }));
        } else if (event.type === "message.delta") {
          setMessages((current) => current.map((message) => message.id === assistantId ? { ...message, content: message.content + event.text } : message));
        } else if (event.type === "message.completed") {
          completed = true;
          setMessages((current) => current.map((message) => message.id === assistantId ? { ...message, citations: event.citations, completion_state: "completed", completed_at: new Date().toISOString() } : message));
        } else if (event.type === "message.error") {
          streamError = event.message || "The answer stream failed. Try the question again.";
          break;
        }
      }
      if (!completed && !streamError) streamError = "The answer stream ended before it completed. Try again.";
    } catch (error) {
      if (!isAbortError(error)) streamError = error instanceof Error ? error.message : "The answer could not be loaded. Try again.";
    } finally {
      if (streamError && mounted.current) {
        setMessages((current) => current.map((message) => message.id === assistantId ? { ...message, content: message.content || "I couldn’t complete that answer.", completion_state: "failed", completed_at: new Date().toISOString(), error: streamError, retryQuestion: question } : message));
      }
      if (mounted.current) setIsThinking(false);
      if (streamController.current === controller) streamController.current = null;
    }
  }, [isThinking, workspace]);

  function submitQuestion(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    void runQuestion(input);
  }

  async function resetChat() {
    if (!workspace) return;
    streamController.current?.abort();
    setIsThinking(false);
    setInput("");
    try {
      const conversation = await createConversation(workspace.repository.id);
      if (!mounted.current) return;
      setWorkspace((current) => current ? { ...current, conversation, messages: [] } : current);
      setMessages([]);
    } catch (error) {
      if (mounted.current) setJobError(error instanceof Error ? error.message : "A new conversation could not be created.");
    }
  }

  if (workspaceLoading) {
    return <main className={styles.stateShell}><div className={styles.stateCard}><span className={styles.stateKicker}>Workspace</span><h1>Loading repository workspace…</h1><p>Fetching the file tree, conversation, and indexing status.</p></div></main>;
  }

  if (workspaceError || !workspace || !job) {
    return <main className={styles.stateShell}><div className={styles.stateCard}><span className={styles.stateKicker}>Workspace unavailable</span><h1>We couldn’t open this repository.</h1><p>{workspaceError || "The backend returned an incomplete workspace."}</p><button className={styles.retryButton} onClick={retryWorkspace}>Retry workspace</button></div></main>;
  }

  const isIndexing = job.status === "queued" || job.status === "indexing";
  const previewLines = preview.status === "ready" ? preview.content.split("\n") : [];

  return (
    <main className={styles.appShell}>
      <Sidebar repoName={workspace.repository.name} branch={workspace.repository.default_branch} />
      <section className={styles.workspace}>
        <WorkspaceHeader repoName={workspace.repository.name} isIndexing={isIndexing} indexProgress={job.progress} jobStatus={job.status} />
        {jobError && <div className={styles.workspaceNotice} role="alert"><span>{jobError}</span><button onClick={retryWorkspace}>Retry</button></div>}
        <div className={styles.workspaceGrid}>
          <ChatPanel messages={messages} suggestions={workspace.starter_questions} input={input} isThinking={isThinking} onInputChange={setInput} onSubmit={submitQuestion} onNewChat={() => void resetChat()} onSelectCitation={selectCitation} onRetry={(question) => void runQuestion(question)} />
          <RepositoryExplorer repoName={workspace.repository.name} visibleTree={visibleTree} explorerFilter={explorerFilter} expanded={expanded} activeFile={activeFile} previewLines={previewLines} previewStatus={preview.status} previewMessage={preview.status === "unavailable" ? preview.message : ""} highlightedRange={citationHighlight} onFilterChange={setExplorerFilter} onToggleFolder={toggleFolder} onSelectFile={selectFile} onClosePreview={closePreview} />
        </div>
      </section>
    </main>
  );
}
