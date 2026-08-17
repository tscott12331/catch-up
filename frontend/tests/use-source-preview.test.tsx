import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ApiClient, FilePayload } from "../app/_lib/api";
import { useSourcePreview } from "../app/_hooks/use-source-preview";
import type { Citation } from "../app/_lib/types";

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((next) => { resolve = next; });
  return { promise, resolve };
}

const citation: Citation = {
  id: "11111111-1111-4111-8111-111111111111",
  passage_id: "22222222-2222-4222-8222-222222222222",
  revision: "abc123",
  path: "src/features/checkout.ts",
  start_line: 2,
  end_line: 4,
};

describe("useSourcePreview", () => {
  it("loads an initial path that arrives after the workspace", async () => {
    const getFile = vi.fn().mockResolvedValue({ path: "README.md", content: "readme" });
    const client = { getFile } as unknown as ApiClient;
    const { result, rerender } = renderHook(
      ({ initialPath }) => useSourcePreview(client, { owner: "acme", name: "checkout" }, initialPath),
      { initialProps: { initialPath: "" } },
    );

    rerender({ initialPath: "README.md" });

    await waitFor(() => expect(result.current.preview).toEqual({ status: "ready", content: "readme" }));
    expect(result.current.activeFile).toBe("README.md");
    expect(getFile).toHaveBeenCalledWith("acme", "checkout", "README.md", expect.any(AbortSignal));
  });

  it("aborts the file request when the hook unmounts", () => {
    let signal: AbortSignal | undefined;
    const getFile = vi.fn((_owner: string, _repo: string, _path: string, requestSignal?: AbortSignal) => {
      signal = requestSignal;
      return new Promise<FilePayload>(() => {});
    });
    const client = { getFile } as unknown as ApiClient;
    const { unmount } = renderHook(() => useSourcePreview(client, { owner: "acme", name: "checkout" }, "a.ts"));

    unmount();

    expect(signal?.aborted).toBe(true);
  });

  it("prevents a slower file response from replacing the current selection", async () => {
    const first = deferred<FilePayload>();
    const second = deferred<FilePayload>();
    const getFile = vi.fn((_owner: string, _repo: string, path: string) => path === "a.ts" ? first.promise : second.promise);
    const client = { getFile } as unknown as ApiClient;
    const { result } = renderHook(() => useSourcePreview(client, { owner: "acme", name: "checkout" }, "a.ts"));

    act(() => result.current.selectFile("b.ts"));
    await act(async () => second.resolve({ path: "b.ts", content: "new" }));
    await waitFor(() => expect(result.current.preview).toEqual({ status: "ready", content: "new" }));
    await act(async () => first.resolve({ path: "a.ts", content: "old" }));
    expect(result.current.preview).toEqual({ status: "ready", content: "new" });
  });

  it("navigates citations and exposes folders to expand", async () => {
    const client = { getFile: vi.fn().mockResolvedValue({ path: citation.path, content: "source" }) } as unknown as ApiClient;
    const { result } = renderHook(() => useSourcePreview(client, { owner: "acme", name: "checkout" }, ""));

    act(() => result.current.selectCitation(citation));
    expect(result.current.activeFile).toBe(citation.path);
    expect(result.current.highlightedCitation).toBe(citation);
    expect([...result.current.citationParentFolders]).toEqual(["src", "src/features"]);
    await waitFor(() => expect(result.current.preview.status).toBe("ready"));
  });
});
