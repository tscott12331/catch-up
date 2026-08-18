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
    return <main className="grid min-h-screen place-items-center bg-canvas p-6"><div className="w-[min(520px,100%)] rounded-xl border border-line bg-panel p-[38px] shadow-state-card"><span className="mb-2.5 block text-[10px] font-bold tracking-[.14em] text-green uppercase">Workspace</span><h1 className="m-0 font-serif text-[29px] font-normal tracking-[-.03em]">Loading repository workspace…</h1><p className="mt-3.5 mb-[22px] text-[13px] leading-[1.65] text-copy-soft">Fetching the file tree, conversation, and indexing status.</p></div></main>;
  }

  const trackedJob = indexing.job?.repository_id === workspace?.repository.id ? indexing.job : null;
  const job = trackedJob ?? workspace?.job ?? null;
  if (workspaceState.error || !workspace || !job) {
    return <main className="grid min-h-screen place-items-center bg-canvas p-6"><div className="w-[min(520px,100%)] rounded-xl border border-line bg-panel p-[38px] shadow-state-card"><span className="mb-2.5 block text-[10px] font-bold tracking-[.14em] text-green uppercase">Workspace unavailable</span><h1 className="m-0 font-serif text-[29px] font-normal tracking-[-.03em]">We couldn’t open this repository.</h1><p className="mt-3.5 mb-[22px] text-[13px] leading-[1.65] text-copy-soft">{workspaceState.error || "The backend returned an incomplete workspace."}</p><button className="rounded-md border border-action-line bg-action-bg px-[11px] py-2 text-[11px] font-bold text-green-ink" onClick={workspaceState.reload}>Retry workspace</button></div></main>;
  }

  const isIndexing = job.status === "queued" || job.status === "indexing";
  const previewLines = source.preview.status === "ready" ? source.preview.content.split("\n") : [];

  return (
    <main className="flex max-h-screen bg-canvas max-[760px]:block">
      <Sidebar repoName={workspace.repository.name} branch={workspace.repository.default_branch} />
      <section className="flex min-w-0 flex-1 flex-col overflow-y-auto [scrollbar-width:thin]">
        <WorkspaceHeader repoName={workspace.repository.name} isIndexing={isIndexing} indexProgress={job.progress} jobStatus={job.status} />
        {indexing.error && <div className="flex items-center justify-between gap-4 border-b border-danger-line bg-danger-soft px-[31px] py-[9px] text-[11px] text-danger-ink" role="alert"><span>{indexing.error}</span><button className="rounded-md border border-action-line bg-action-bg px-[11px] py-2 text-[11px] font-bold text-green-ink" disabled={indexing.isRestarting} onClick={() => void indexing.restart()}>Retry</button></div>}
        {chat.resetError && <div className="flex items-center justify-between gap-4 border-b border-danger-line bg-danger-soft px-[31px] py-[9px] text-[11px] text-danger-ink" role="alert"><span>{chat.resetError}</span><button className="rounded-md border border-action-line bg-action-bg px-[11px] py-2 text-[11px] font-bold text-green-ink" onClick={() => void chat.resetConversation()}>Retry new chat</button></div>}
        <div className="grid min-h-0 flex-1 grid-cols-[minmax(480px,1fr)_370px] overflow-y-hidden max-[950px]:grid-cols-[minmax(400px,1fr)_320px] max-[760px]:block">
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
