import { Icon } from "./icon";
import type { TreeNode } from "../_lib/types";
import styles from "./workspace.module.css";

type TreeItemProps = {
  node: TreeNode;
  path: string;
  expanded: Set<string>;
  onToggle: (path: string) => void;
  activeFile: string;
  onSelect: (path: string) => void;
};

export function TreeItem({ node, path, expanded, onToggle, activeFile, onSelect }: TreeItemProps) {
  const isOpen = expanded.has(path);
  const isActive = path === activeFile;

  return (
    <div>
      <button className={`${styles.treeRow} ${isActive ? styles.treeRowActive : ""}`} onClick={() => (node.type === "folder" ? onToggle(path) : onSelect(path))}>
        {node.type === "folder" ? <Icon name={isOpen ? "chevron-down" : "chevron-right"} size={13} /> : <span className={styles.treeSpacer} />}
        <Icon name={node.type === "folder" ? "folder" : "file"} size={15} />
        <span>{node.name}</span>
      </button>
      {node.type === "folder" && isOpen && <div className={styles.treeChildren}>
        {node.children?.map((child) => <TreeItem key={`${path}/${child.name}`} node={child} path={`${path}/${child.name}`} expanded={expanded} onToggle={onToggle} activeFile={activeFile} onSelect={onSelect} />)}
      </div>}
    </div>
  );
}
