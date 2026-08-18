import { Icon } from "./icon";
import type { TreeNode } from "../_lib/types";

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
      <button className={`flex w-full items-center gap-[7px] rounded-sm border-0 bg-transparent px-[7px] py-1.5 text-left text-[11px] [&>svg]:text-tree-icon ${isActive ? "bg-tree-active-bg font-bold text-green-ink [&>svg]:text-tree-active-icon" : "text-tree-row hover:bg-tree-hover-bg hover:text-tree-hover"}`} onClick={() => (node.type === "folder" ? onToggle(path) : onSelect(path))}>
        {node.type === "folder" ? <Icon name={isOpen ? "chevron-down" : "chevron-right"} size={13} /> : <span className="inline-block w-[13px]" />}
        <Icon name={node.type === "folder" ? "folder" : "file"} size={15} />
        <span>{node.name}</span>
      </button>
      {node.type === "folder" && isOpen && <div className="pl-[17px]">
        {node.children?.map((child) => <TreeItem key={`${path}/${child.name}`} node={child} path={`${path}/${child.name}`} expanded={expanded} onToggle={onToggle} activeFile={activeFile} onSelect={onSelect} />)}
      </div>}
    </div>
  );
}
