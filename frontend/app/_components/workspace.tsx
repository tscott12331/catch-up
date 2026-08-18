"use client";

import type { SubmitEvent } from "react";
import { useMemo, useState } from "react";
import { useChat } from "../_hooks/use-chat";
import { useIndexingJob } from "../_hooks/use-indexing-job";
import { useSourcePreview } from "../_hooks/use-source-preview";
import { useWorkspace } from "../_hooks/use-workspace";
import { apiClient, type ApiClient } from "../_lib/api";
import type { RepositoryRoute } from "../_lib/repository";
import { filterTree, parentFolders } from "../_lib/tree";
import type { Citation } from "../_lib/types";
import { ChatPanel } from "./chat-panel";
import { RepositoryExplorer } from "./repository-explorer";
import { Sidebar } from "./sidebar";
import { WorkspaceHeader } from "./workspace-header";
import styles from "./workspace.module.css";

type WorkspaceProps = {
  repository: RepositoryRoute;
  client?: ApiClient;
};

type ExpansionState = {
  workspaceKey: string;
  paths: Set<string>;
};

type FilterState = {
  repositoryKey: string;
  value: string;
};

export function Workspace({ repository: routeRepository, client = apiClient }: WorkspaceProps) {
  const workspaceState = useWorkspace(client, routeRepository);
  const workspace = workspaceState.workspace;
  const indexing = useIndexingJob(
    client,
    workspace?.repository.id ?? null,
    workspace?.job ?? null,
  );
  const source = useSourcePreview(
    client,
    workspace ? { owner: workspace.repository.owner, name: workspace.repository.name } : routeRepository,
    workspace?.selected_file ?? "",
  );
  const chat = useChat({
    client,
    repositoryId: workspace?.repository.id ?? null,
    initialConversation: workspace?.conversation ?? null,
    initialMessages: workspace?.messages,
  });
  const [filter, setFilter] = useState<FilterState>({ repositoryKey: "", value: "" });
  const [expansion, setExpansion] = useState<ExpansionState>({ workspaceKey: "", paths: new Set() });

  const repositoryKey = `${routeRepository.owner}/${routeRepository.name}`;
  const explorerFilter = filter.repositoryKey === repositoryKey ? filter.value : "";
  const workspaceKey = workspace ? `${workspace.repository.id}:${workspace.selected_file}` : "";
  const defaultExpanded = useMemo(() => parentFolders(workspace?.selected_file ?? ""), [workspace?.selected_file]);
  const expanded = expansion.workspaceKey === workspaceKey ? expansion.paths : defaultExpanded;
  const visibleTree = useMemo(
    () => filterTree(workspace?.tree ?? [], explorerFilter),
    [explorerFilter, workspace?.tree],
  );

  function updateExpanded(update: (current: Set<string>) => Set<string>) {
    setExpansion((current) => ({
      workspaceKey,
      paths: update(current.workspaceKey === workspaceKey ? current.paths : defaultExpanded),
    }));
  }

  function toggleFolder(path: string) {
    updateExpanded((current) => {
      const next = new Set(current);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }

  function selectCitation(citation: Citation) {
    updateExpanded((current) => new Set([...current, ...parentFolders(citation.path)]));
    source.selectCitation(citation);
  }

  function submitQuestion(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    void chat.runQuestion(chat.input);
  }

  if (workspaceState.isLoading) {
    return <main className={styles.stateShell}><div className={styles.stateCard}><span className={styles.stateKicker}>Workspace</span><h1>Loading repository workspace…</h1><p>Fetching the file tree, conversation, and indexing status.</p></div></main>;
  }

  const trackedJob = indexing.job?.repository_id === workspace?.repository.id ? indexing.job : null;
  const job = trackedJob ?? workspace?.job ?? null;
  if (workspaceState.error || !workspace || !job) {
    return <main className={styles.stateShell}><div className={styles.stateCard}><span className={styles.stateKicker}>Workspace unavailable</span><h1>We couldn’t open this repository.</h1><p>{workspaceState.error || "The backend returned an incomplete workspace."}</p><button className={styles.retryButton} onClick={workspaceState.reload}>Retry workspace</button></div></main>;
  }

  const isIndexing = job.status === "queued" || job.status === "indexing";
  const previewLines = source.preview.status === "ready" ? source.preview.content.split("\n") : [];

  return (
    <main className={styles.appShell}>
      <Sidebar repoName={workspace.repository.name} branch={workspace.repository.default_branch} />
      <section className={`${styles.workspace} scroller-y`}>
        <WorkspaceHeader repoName={workspace.repository.name} isIndexing={isIndexing} indexProgress={job.progress} jobStatus={job.status} />
        {indexing.error && <div className={styles.workspaceNotice} role="alert"><span>{indexing.error}</span><button disabled={indexing.isRestarting} onClick={() => void indexing.restart()}>Retry</button></div>}
        {chat.resetError && <div className={styles.workspaceNotice} role="alert"><span>{chat.resetError}</span><button onClick={() => void chat.resetConversation()}>Retry new chat</button></div>}
        <div className={styles.workspaceGrid}>
          <ChatPanel
            messages={chat.messages}
            suggestions={workspace.starter_questions}
            input={chat.input}
            isThinking={chat.isThinking}
            onInputChange={chat.setInput}
            onSubmit={submitQuestion}
            onNewChat={() => void chat.resetConversation()}
            onSelectCitation={selectCitation}
            onRetry={(question) => void chat.retryQuestion(question)}
          />
          <RepositoryExplorer
            repoName={workspace.repository.name}
            visibleTree={visibleTree}
            explorerFilter={explorerFilter}
            expanded={expanded}
            activeFile={source.activeFile}
            previewLines={previewLines}
            previewStatus={source.preview.status}
            previewMessage={source.preview.status === "unavailable" ? source.preview.message : ""}
            highlightedRange={source.highlightedCitation}
            onFilterChange={(value) => setFilter({ repositoryKey, value })}
            onToggleFolder={toggleFolder}
            onSelectFile={source.selectFile}
            onClosePreview={source.closePreview}
          />
        </div>
      </section>
    </main>
  );
}
