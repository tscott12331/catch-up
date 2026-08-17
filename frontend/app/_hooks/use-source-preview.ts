"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { ApiClient } from "../_lib/api";
import { isAbortError } from "../_lib/api/errors";
import type { RepositoryRoute } from "../_lib/repository";
import { parentFolders } from "../_lib/tree";
import type { Citation } from "../_lib/types";

export type PreviewState =
  | { status: "idle" | "loading" }
  | { status: "ready"; content: string }
  | { status: "unavailable"; message: string };

export type SourcePreviewState = {
  activeFile: string;
  preview: PreviewState;
  highlightedCitation: Citation | null;
  citationParentFolders: Set<string>;
  selectFile: (path: string) => void;
  selectCitation: (citation: Citation) => void;
  closePreview: () => void;
};

export function useSourcePreview(
  client: ApiClient,
  repository: RepositoryRoute,
  initialPath: string,
): SourcePreviewState {
  const [activeFile, setActiveFile] = useState(initialPath);
  const [preview, setPreview] = useState<PreviewState>(initialPath ? { status: "loading" } : { status: "idle" });
  const [highlightedCitation, setHighlightedCitation] = useState<Citation | null>(null);
  const scopeKey = `${repository.owner}/${repository.name}\0${initialPath}`;
  const [stateScopeKey, setStateScopeKey] = useState(scopeKey);
  const requestController = useRef<AbortController | null>(null);

  if (stateScopeKey !== scopeKey) {
    setStateScopeKey(scopeKey);
    setActiveFile(initialPath);
    setHighlightedCitation(null);
    setPreview(initialPath ? { status: "loading" } : { status: "idle" });
  }

  useEffect(() => {
    requestController.current?.abort();
    if (!activeFile) return;

    const controller = new AbortController();
    requestController.current = controller;

    void client.getFile(repository.owner, repository.name, activeFile, controller.signal)
      .then((file) => {
        if (!controller.signal.aborted) {
          setPreview({ status: "ready", content: file.content });
        }
      })
      .catch((requestError: unknown) => {
        if (!controller.signal.aborted && !isAbortError(requestError)) {
          setPreview({ status: "unavailable", message: requestError instanceof Error ? requestError.message : "Source content is unavailable." });
        }
      });

    return () => {
      controller.abort();
      if (requestController.current === controller) requestController.current = null;
    };
  }, [activeFile, client, repository.name, repository.owner]);

  const citationParentFolders = useMemo(
    () => highlightedCitation ? parentFolders(highlightedCitation.path) : new Set<string>(),
    [highlightedCitation],
  );

  function selectFile(path: string) {
    setHighlightedCitation(null);
    setPreview({ status: "loading" });
    setActiveFile(path);
  }

  function selectCitation(citation: Citation) {
    setHighlightedCitation(citation);
    if (citation.path === activeFile) return;
    setPreview({ status: "loading" });
    setActiveFile(citation.path);
  }

  function closePreview() {
    requestController.current?.abort();
    setHighlightedCitation(null);
    setActiveFile("");
    setPreview({ status: "idle" });
  }

  return { activeFile, preview, highlightedCitation, citationParentFolders, selectFile, selectCitation, closePreview };
}
