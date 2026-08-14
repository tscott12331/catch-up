import type { TreeNode } from "./types";

export function filterTree(nodes: TreeNode[], rawQuery: string): TreeNode[] {
  const query = rawQuery.trim().toLowerCase();
  if (!query) return nodes;

  return nodes.flatMap((node) => {
    const children = node.children ? filterTree(node.children, query) : [];
    if (node.name.toLowerCase().includes(query) || children.length > 0) {
      return [{ ...node, ...(node.children ? { children } : {}) }];
    }
    return [];
  });
}

export function parentFolders(filePath: string): Set<string> {
  const parts = filePath.split("/").filter(Boolean);
  const folders = new Set<string>();
  for (let index = 1; index < parts.length; index += 1) {
    folders.add(parts.slice(0, index).join("/"));
  }
  return folders;
}
