"use client";

import { useCallback, useEffect, useState } from "react";
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
  const repositoryKey = `${repository.owner}/${repository.name}`;
  const [stateRepositoryKey, setStateRepositoryKey] = useState(repositoryKey);

  if (stateRepositoryKey !== repositoryKey) {
    setStateRepositoryKey(repositoryKey);
    setWorkspace(null);
    setIsLoading(true);
    setError("");
  }

  const reload = useCallback(() => {
    setWorkspace(null);
    setIsLoading(true);
    setError("");
    setReloadKey((current) => current + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    void client.getWorkspace(repository.owner, repository.name, controller.signal)
      .then((payload) => {
        if (!controller.signal.aborted) setWorkspace(payload);
      })
      .catch((requestError: unknown) => {
        if (!controller.signal.aborted && !isAbortError(requestError)) {
          setError(messageFrom(requestError));
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false);
      });

    return () => {
      controller.abort();
    };
  }, [client, reloadKey, repository.name, repository.owner]);

  return { workspace, isLoading, error, reload };
}
