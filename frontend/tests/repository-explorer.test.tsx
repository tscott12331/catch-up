import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RepositoryExplorer } from "../app/_components/repository-explorer";

afterEach(() => vi.restoreAllMocks());

describe("RepositoryExplorer", () => {
  it("copies available active source content and disables copying when unavailable", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
    const explorerProps = {
      repoName: "checkout-service", visibleTree: [], explorerFilter: "", expanded: new Set<string>(), activeFile: "README.md", previewLines: ["# Checkout service"], previewStatus: "ready" as const, previewMessage: "", highlightedRange: null,
      onFilterChange: vi.fn(), onToggleFolder: vi.fn(), onSelectFile: vi.fn(), onClosePreview: vi.fn(),
    };
    const { rerender } = render(<RepositoryExplorer {...explorerProps} />);

    const copy = screen.getByRole("button", { name: "Copy active file contents" });
    expect(copy).toBeEnabled();
    fireEvent.click(copy);
    await waitFor(() => expect(writeText).toHaveBeenCalledWith("# Checkout service"));
    expect(await screen.findByText("Source copied to clipboard.")).toBeInTheDocument();

    rerender(<RepositoryExplorer {...explorerProps} previewStatus="unavailable" previewMessage="Source content is unavailable." />);
    expect(copy).toBeDisabled();
  });
});
