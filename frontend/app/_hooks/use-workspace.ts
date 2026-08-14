"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ApiClient } from "../_lib/api";
import { isAbortError } from "../_lib/api/errors";
import type { RepositoryRoute } from "../_lib/repository";
import type { WorkspacePayload } from "../_lib/types";

export type WorkspaceState = {
  workspace: WorkspacePayload | null;
  isLoading: boolean;
  error: string;
  reload: () => void;
};

function messageFrom(error: unknown): string {
  return error instanceof Error ? error.message : "The workspace could not be loaded.";
}

export function useWorkspace(client: ApiClient, repository: RepositoryRoute): WorkspaceState {
  const [workspace, setWorkspace] = useState<WorkspacePayload | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const generation = useRef(0);

  const reload = useCallback(() => setReloadKey((current) => current + 1), []);

  useEffect(() => {
    const requestGeneration = ++generation.current;
    const controller = new AbortController();
    queueMicrotask(() => {
      if (!controller.signal.aborted && generation.current === requestGeneration) {
        setWorkspace(null);
        setIsLoading(true);
        setError("");
      }
    });

    void client.getWorkspace(repository.owner, repository.name, controller.signal)
      .then((payload) => {
        if (!controller.signal.aborted && generation.current === requestGeneration) setWorkspace(payload);
      })
      .catch((requestError: unknown) => {
        if (!controller.signal.aborted && generation.current === requestGeneration && !isAbortError(requestError)) {
          setError(messageFrom(requestError));
        }
      })
      .finally(() => {
        if (!controller.signal.aborted && generation.current === requestGeneration) setIsLoading(false);
      });

    return () => {
      controller.abort();
      if (generation.current === requestGeneration) generation.current += 1;
    };
  }, [client, reloadKey, repository.name, repository.owner]);

  return { workspace, isLoading, error, reload };
}
