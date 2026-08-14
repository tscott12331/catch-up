import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ApiClient } from "../app/_lib/api";
import { useIndexingJob } from "../app/_hooks/use-indexing-job";
import type { IndexingJob } from "../app/_lib/types";

function job(id: string, status: IndexingJob["status"], progress: number): IndexingJob {
  return { id, status, progress } as unknown as IndexingJob;
}

describe("useIndexingJob", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("polls on the configured timer and keeps progress monotonic", async () => {
    const getJob = vi.fn()
      .mockResolvedValueOnce(job("job-1", "indexing", 10))
      .mockResolvedValueOnce(job("job-1", "indexing", 5))
      .mockResolvedValueOnce(job("job-1", "completed", 100));
    const client = { getJob } as unknown as ApiClient;
    const { result } = renderHook(() => useIndexingJob(client, "repo-1", job("job-1", "indexing", 2), 100));

    await act(async () => { await Promise.resolve(); });
    expect(result.current.job?.progress).toBe(10);
    await act(async () => { vi.advanceTimersByTime(100); await Promise.resolve(); });
    expect(result.current.job?.progress).toBe(10);
    await act(async () => { vi.advanceTimersByTime(100); await Promise.resolve(); });
    expect(result.current.job).toMatchObject({ status: "completed", progress: 100 });
  });

  it("aborts polling before starting a replacement job", async () => {
    let pollingSignal: AbortSignal | undefined;
    const getJob = vi.fn((_id: string, signal?: AbortSignal) => {
      pollingSignal = signal;
      return new Promise<IndexingJob>(() => undefined);
    });
    const createIndexingJob = vi.fn().mockResolvedValue(job("job-2", "completed", 100));
    const client = { getJob, createIndexingJob } as unknown as ApiClient;
    const { result } = renderHook(() => useIndexingJob(client, "repo-1", job("job-1", "indexing", 2)));

    await act(async () => result.current.restart());
    expect(pollingSignal?.aborted).toBe(true);
    expect(result.current.job?.id).toBe("job-2");
    expect(result.current.error).toBe("");
  });
});
