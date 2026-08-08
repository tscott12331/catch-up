import { useState } from "react";
import { Icon } from "./icon";
import { TreeItem } from "./tree-item";
import { SourcePreview } from "./source-preview";
import type { Citation, TreeNode } from "../_lib/types";
import styles from "./workspace.module.css";

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
    <aside className={styles.explorerPanel} id="explorer">
      <div className={styles.explorerHeading}><div><p className={styles.sectionKicker}>Source</p><h2>Repository explorer</h2></div><div className={styles.copyAction}><button className={styles.iconButton} aria-label="Copy active file contents" disabled={!canCopy} onClick={() => void copyActiveFile()}><Icon name="copy" size={16} /></button><span className={styles.copyFeedback} role="status">{copyFeedback?.path === activeFile ? copyFeedback.message : ""}</span></div></div>
      <div className={styles.explorerSearch}><Icon name="search" size={15} /><input value={explorerFilter} onChange={(event) => onFilterChange(event.target.value)} placeholder="Filter files" /></div>
      <div className={styles.treeRoot}><span className={styles.treeRootLabel}>{repoName}</span>{visibleTree.map((node) => <TreeItem key={node.name} node={node} path={node.name} expanded={expanded} onToggle={onToggleFolder} activeFile={activeFile} onSelect={onSelectFile} />)}</div>
      <SourcePreview activeFile={activeFile} previewLines={previewLines} status={previewStatus} message={previewMessage} highlightedRange={highlightedRange} onClose={onClosePreview} />
    </aside>
  );
}
