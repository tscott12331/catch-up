import { useState } from "react";
import { Icon } from "./icon";
import { TreeItem } from "./tree-item";
import { SourcePreview } from "./source-preview";
import type { Citation, TreeNode } from "../_lib/types";

type RepositoryExplorerProps = {
  repoName: string;
  visibleTree: TreeNode[];
  explorerFilter: string;
  expanded: Set<string>;
  activeFile: string;
  previewLines: string[];
  previewStatus: "idle" | "loading" | "ready" | "unavailable";
  previewMessage: string;
  highlightedRange: Citation | null;
  onFilterChange: (value: string) => void;
  onToggleFolder: (path: string) => void;
  onSelectFile: (path: string) => void;
  onClosePreview: () => void;
};

export function RepositoryExplorer({ repoName, visibleTree, explorerFilter, expanded, activeFile, previewLines, previewStatus, previewMessage, highlightedRange, onFilterChange, onToggleFolder, onSelectFile, onClosePreview }: RepositoryExplorerProps) {
  const [copyFeedback, setCopyFeedback] = useState<{ path: string; message: string } | null>(null);
  const canCopy = Boolean(activeFile) && previewStatus === "ready";

  async function copyActiveFile() {
    try {
      if (!navigator.clipboard) throw new Error("Clipboard access is unavailable.");
      await navigator.clipboard.writeText(previewLines.join("\n"));
      setCopyFeedback({ path: activeFile, message: "Source copied to clipboard." });
    } catch {
      setCopyFeedback({ path: activeFile, message: "Couldn’t copy source to clipboard." });
    }
  }

  return (
    <aside className="min-w-0 overflow-y-auto bg-explorer px-6 pt-[37px] pb-6 [scrollbar-width:thin] max-[760px]:min-h-[560px] max-[760px]:border-t max-[760px]:border-line" id="explorer">
      <div className="flex items-start justify-between"><div><p className="mb-[7px] text-[10px] font-bold tracking-[.14em] text-section uppercase">Source</p><h2 className="m-0 font-serif text-[21px] font-normal tracking-[-.03em]">Repository explorer</h2></div><div className="relative"><button className="grid size-[30px] place-items-center rounded-[7px] border border-transparent bg-transparent p-0 text-icon hover:border-line hover:bg-white hover:text-ink disabled:cursor-not-allowed disabled:opacity-45" aria-label="Copy active file contents" disabled={!canCopy} onClick={() => void copyActiveFile()}><Icon name="copy" size={16} /></button><span className="absolute top-[34px] right-0 z-1 w-max max-w-[210px] text-[10px] text-copy" role="status">{copyFeedback?.path === activeFile ? copyFeedback.message : ""}</span></div></div>
      <div className="my-6 mb-[15px] flex items-center gap-[9px] rounded-md border border-search-line bg-white px-[11px] py-[9px] text-search-icon"><Icon name="search" size={15} /><input className="w-full border-0 bg-transparent text-[11px] text-ink outline-0 placeholder:text-search-placeholder" value={explorerFilter} onChange={(event) => onFilterChange(event.target.value)} placeholder="Filter files" /></div>
      <div className="min-h-[200px] border-b border-tree-line pb-[22px] text-[11px] text-tree-copy"><span className="mb-2 block text-[10px] font-bold tracking-[.09em] text-tree-label uppercase">{repoName}</span>{visibleTree.map((node) => <TreeItem key={node.name} node={node} path={node.name} expanded={expanded} onToggle={onToggleFolder} activeFile={activeFile} onSelect={onSelectFile} />)}</div>
      <SourcePreview activeFile={activeFile} previewLines={previewLines} status={previewStatus} message={previewMessage} highlightedRange={highlightedRange} onClose={onClosePreview} />
    </aside>
  );
}
