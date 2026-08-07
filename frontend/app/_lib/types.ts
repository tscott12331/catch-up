import type { ReactNode } from "react";

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

export type Citation = {
  file: string;
  start_line: number;
  end_line: number;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  error?: string;
  retryQuestion?: string;
};

export type TreeNode = {
  name: string;
  type: "file" | "folder";
  children?: TreeNode[];
};

export type RepositoryIdentity = {
  id: string;
  owner: string;
  name: string;
  url: string;
  default_branch: string;
};

export type JobStatus = "queued" | "indexing" | "completed" | "failed";

export type IndexingJob = {
  id: string;
  status: JobStatus;
  progress: number;
};

export type WorkspacePayload = {
  repository: RepositoryIdentity;
  tree: TreeNode[];
  selected_file: string;
  starter_questions: string[];
  messages: ChatMessage[];
  job: IndexingJob;
};

export type IconPathMap = Record<IconName, ReactNode>;
