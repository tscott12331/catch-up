import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ApiClient } from "../app/_lib/api";
import { useWorkspace } from "../app/_hooks/use-workspace";
import type { WorkspacePayload } from "../app/_lib/types";

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((next) => { resolve = next; });
  return { promise, resolve };
}

function payload(name: string): WorkspacePayload {
  return { repository: { name }, messages: [] } as unknown as WorkspacePayload;
}

describe("useWorkspace", () => {
  it("aborts the previous repository load and rejects its late response", async () => {
    const oldRequest = deferred<WorkspacePayload>();
    const newRequest = deferred<WorkspacePayload>();
    const signals: AbortSignal[] = [];
    const getWorkspace = vi.fn((owner: string, name: string, signal?: AbortSignal) => {
      signals.push(signal!);
      return name === "old" ? oldRequest.promise : newRequest.promise;
    });
    const client = { getWorkspace } as unknown as ApiClient;
    const { result, rerender } = renderHook(
      ({ name }) => useWorkspace(client, { owner: "acme", name }),
      { initialProps: { name: "old" } },
    );

    rerender({ name: "new" });
    expect(signals[0].aborted).toBe(true);
    await act(async () => oldRequest.resolve(payload("old")));
    expect(result.current.workspace).toBeNull();

    await act(async () => newRequest.resolve(payload("new")));
    await waitFor(() => expect(result.current.workspace?.repository.name).toBe("new"));
    expect(result.current.isLoading).toBe(false);
  });

  it("owns load errors and retries with a fresh request", async () => {
    const getWorkspace = vi.fn()
      .mockRejectedValueOnce(new Error("workspace failed"))
      .mockResolvedValueOnce(payload("checkout"));
    const client = { getWorkspace } as unknown as ApiClient;
    const { result } = renderHook(() => useWorkspace(client, { owner: "acme", name: "checkout" }));

    await waitFor(() => expect(result.current.error).toBe("workspace failed"));
    act(() => result.current.reload());
    await waitFor(() => expect(result.current.workspace).not.toBeNull());
    expect(result.current.error).toBe("");
  });
});
