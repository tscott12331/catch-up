import { describe, expect, it } from "vitest";
import { filterTree, parentFolders } from "../app/_lib/tree";
import type { TreeNode } from "../app/_lib/types";

const tree: TreeNode[] = [
  {
    name: "src",
    type: "folder",
    children: [
      { name: "checkout.ts", type: "file", children: null },
      { name: "orders.ts", type: "file", children: null },
    ],
  },
  { name: "README.md", type: "file", children: null },
];

describe("tree utilities", () => {
  it("filters case-insensitively while retaining matching ancestors", () => {
    expect(filterTree(tree, " CHECKOUT ")).toEqual([
      { name: "src", type: "folder", children: [{ name: "checkout.ts", type: "file", children: null }] },
    ]);
  });

  it("returns the original tree when the query is blank", () => {
    expect(filterTree(tree, "  ")).toBe(tree);
  });

  it("builds every parent folder without including the file", () => {
    expect([...parentFolders("src/features/checkout/index.ts")]).toEqual(["src", "src/features", "src/features/checkout"]);
  });
});
