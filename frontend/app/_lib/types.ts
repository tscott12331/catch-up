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

export type Message = components["schemas"]["Message"];

export type Conversation = components["schemas"]["Conversation"];

export type IndexingError = components["schemas"]["IndexingError"];

export type DisplayMessage = Message & {
  error?: string;
  retryQuestion?: string;
};

export type TreeNode = components["schemas"]["TreeNode"];

export type Repository = components["schemas"]["Repository"];

export type JobStatus = components["schemas"]["IndexingJob"]["status"];

export type JobStage = components["schemas"]["IndexingJob"]["stage"];

export type MessageCompletionState = components["schemas"]["Message"]["completion_state"];

export type IndexingJob = components["schemas"]["IndexingJob"];

export type WorkspacePayload = components["schemas"]["WorkspaceResponse"];

export type RepositoryCreateResponse = components["schemas"]["RepositoryCreateResponse"];

export type IconPathMap = Record<IconName, ReactNode>;
