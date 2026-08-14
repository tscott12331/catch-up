"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ApiClient } from "../_lib/api";
import { isAbortError } from "../_lib/api/errors";
import type { IndexingJob } from "../_lib/types";

const TERMINAL_STATUSES = new Set<IndexingJob["status"]>(["completed", "failed", "cancelled"]);

export type IndexingJobState = {
  job: IndexingJob | null;
  error: string;
  isRestarting: boolean;
  restart: () => Promise<void>;
};

function jobError(job: IndexingJob): string {
  if (job.status === "failed") return "Indexing failed. Retry the workspace to check again.";
  if (job.status === "cancelled") return "Indexing was cancelled.";
  return "";
}

function messageFrom(error: unknown): string {
  return error instanceof Error ? error.message : "Indexing progress could not be loaded.";
}

export function useIndexingJob(
  client: ApiClient,
  repositoryId: string | null,
  initialJob: IndexingJob | null,
  pollIntervalMs = 450,
): IndexingJobState {
  const [job, setJob] = useState<IndexingJob | null>(initialJob);
  const [error, setError] = useState(initialJob ? jobError(initialJob) : "");
  const [isRestarting, setIsRestarting] = useState(false);
  const generation = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const initialJobRef = useRef(initialJob);

  useEffect(() => {
    initialJobRef.current = initialJob;
  }, [initialJob]);

  const stopTracking = useCallback(() => {
    generation.current += 1;
    controller.current?.abort();
    controller.current = null;
    if (timer.current !== null) clearTimeout(timer.current);
    timer.current = null;
  }, []);

  const track = useCallback((seed: IndexingJob) => {
    stopTracking();
    const trackingGeneration = generation.current;
    const nextController = new AbortController();
    controller.current = nextController;
    let progress = seed.progress;
    setJob(seed);
    setError(jobError(seed));

    if (TERMINAL_STATUSES.has(seed.status)) return;

    const poll = async () => {
      try {
        const nextJob = await client.getJob(seed.id, nextController.signal);
        if (nextController.signal.aborted || generation.current !== trackingGeneration) return;
        if (nextJob.progress >= progress || TERMINAL_STATUSES.has(nextJob.status)) {
          progress = Math.max(progress, nextJob.progress);
          setJob(nextJob);
        }
        if (TERMINAL_STATUSES.has(nextJob.status)) {
          setError(jobError(nextJob));
          return;
        }
        timer.current = setTimeout(() => void poll(), pollIntervalMs);
      } catch (requestError) {
        if (!nextController.signal.aborted && generation.current === trackingGeneration && !isAbortError(requestError)) {
          setError(messageFrom(requestError));
        }
      }
    };

    void poll();
  }, [client, pollIntervalMs, stopTracking]);

  useEffect(() => {
    const seed = initialJobRef.current;
    if (seed) track(seed);
    else {
      stopTracking();
      setJob(null);
      setError("");
    }
    return stopTracking;
  }, [initialJob?.id, repositoryId, stopTracking, track]);

  const restart = useCallback(async () => {
    if (!repositoryId || isRestarting) return;
    stopTracking();
    const restartGeneration = generation.current;
    const restartController = new AbortController();
    controller.current = restartController;
    setIsRestarting(true);
    setError("");
    try {
      const nextJob = await client.createIndexingJob(repositoryId, restartController.signal);
      if (!restartController.signal.aborted && generation.current === restartGeneration) {
        setIsRestarting(false);
        track(nextJob);
      }
    } catch (requestError) {
      if (!restartController.signal.aborted && generation.current === restartGeneration && !isAbortError(requestError)) {
        setError(requestError instanceof Error ? requestError.message : "Indexing could not be restarted.");
      }
    } finally {
      if (!restartController.signal.aborted && generation.current === restartGeneration) setIsRestarting(false);
    }
  }, [client, isRestarting, repositoryId, stopTracking, track]);

  return { job, error, isRestarting, restart };
}
