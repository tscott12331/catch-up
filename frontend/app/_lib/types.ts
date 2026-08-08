import type { ReactNode } from "react";
import type { components } from "./generated/openapi";

export type IconName =
  | "arrow-up"
  | "book"
  | "branch"
  | "check"
  | "chevron-down"
  | "chevron-right"
  | "code"
  | "copy"
  | "file"
  | "folder"
  | "github"
  | "logo"
  | "menu"
  | "plus"
  | "search"
  | "send"
  | "settings"
  | "sparkle"
  | "x";

export type Citation = components["schemas"]["Citation"];

export type ChatMessage = components["schemas"]["ChatMessage"] & {
  error?: string;
  retryQuestion?: string;
};

export type TreeNode = components["schemas"]["TreeNode"];

export type RepositoryIdentity = components["schemas"]["RepositoryIdentity"];

export type JobStatus = components["schemas"]["IndexingJob"]["status"];

export type IndexingJob = components["schemas"]["IndexingJob"];

export type WorkspacePayload = Omit<components["schemas"]["WorkspaceResponse"], "messages"> & {
  messages: ChatMessage[];
};

export type IconPathMap = Record<IconName, ReactNode>;
