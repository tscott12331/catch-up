import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ChatPanel } from "../app/_components/chat-panel";
import { RepositoryExplorer } from "../app/_components/repository-explorer";
import { Workspace } from "../app/_components/workspace";
import { getFile, getWorkspace } from "../app/_lib/api";

vi.mock("../app/_lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../app/_lib/api")>();
  return { ...actual, getFile: vi.fn(), getWorkspace: vi.fn() };
});

const getWorkspaceMock = vi.mocked(getWorkspace);
const getFileMock = vi.mocked(getFile);
const citation = { id: "66666666-6666-4666-8666-666666666666", passage_id: "77777777-7777-4777-8777-777777777777", revision: "abc123", path: "src/checkout.ts", start_line: 2, end_line: 3 };
const baseWorkspace = {
  repository: {
    id: "11111111-1111-4111-8111-111111111111",
    owner: "acme",
    name: "checkout-service",
    source_url: "https://github.com/acme/checkout-service",
    default_branch: "main",
    indexed_revision: "8a8b1b9f95ea2f76e67c11b79f138b5e8044be57",
  },
  conversation: { id: "22222222-2222-4222-8222-222222222222", repository_id: "11111111-1111-4111-8111-111111111111", created_at: "2026-08-08T04:00:00Z", updated_at: "2026-08-08T04:00:00Z" },
  tree: [{ name: "README.md", type: "file" as const }, { name: "src", type: "folder" as const, children: [{ name: "checkout.ts", type: "file" as const }] }],
  selected_file: "README.md",
  starter_questions: ["Where is authentication handled?"],
  messages: [{ id: "55555555-5555-4555-8555-555555555555", conversation_id: "22222222-2222-4222-8222-222222222222", role: "assistant" as const, content: "Welcome", completion_state: "completed" as const, created_at: "2026-08-08T04:00:00Z", completed_at: "2026-08-08T04:00:00Z", citations: [citation] }],
  passages: [],
  job: { id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", repository_id: "11111111-1111-4111-8111-111111111111", status: "completed" as const, stage: "completed" as const, progress: 100, created_at: "2026-08-08T04:00:00Z", updated_at: "2026-08-08T04:00:00Z", started_at: "2026-08-08T04:00:00Z", completed_at: "2026-08-08T04:00:00Z", error: null },
};

describe("Workspace", () => {
  beforeEach(() => {
    getWorkspaceMock.mockReset();
    getFileMock.mockReset();
    getWorkspaceMock.mockResolvedValue(baseWorkspace);
    getFileMock.mockImplementation(async (_owner, _repo, path) => ({ path, content: path === "src/checkout.ts" ? "export function checkout() {\n  return charge();\n}" : "# Checkout service" }));
  });

  afterEach(() => vi.restoreAllMocks());

  it("renders the loaded repository workspace and source preview", async () => {
    render(<Workspace repository={{ owner: "acme", name: "checkout-service" }} />);

    expect(await screen.findByText("Repository explorer")).toBeInTheDocument();
    await waitFor(() => expect(getFileMock).toHaveBeenCalledWith("acme", "checkout-service", "README.md", expect.any(AbortSignal)));
    expect(screen.getByText("# Checkout service")).toBeInTheDocument();
    expect(screen.getByText("Indexed just now")).toBeInTheDocument();
  });

  it("opens parent folders, loads a cited file, and scrolls to its first cited line", async () => {
    const scrollIntoView = vi.fn();
    Object.defineProperty(Element.prototype, "scrollIntoView", { configurable: true, value: scrollIntoView });
    const user = userEvent.setup();
    render(<Workspace repository={{ owner: "acme", name: "checkout-service" }} />);

    await user.click(await screen.findByRole("button", { name: /src\/checkout.ts/i }));

    expect(await screen.findByRole("button", { name: "checkout.ts" })).toBeInTheDocument();
    await waitFor(() => expect(getFileMock).toHaveBeenCalledWith("acme", "checkout-service", "src/checkout.ts", expect.any(AbortSignal)));
    expect(await screen.findByText("return charge();")).toBeInTheDocument();
    expect(scrollIntoView).toHaveBeenCalledWith({ block: "center" });
  });

  it("clears the active source and citation highlight when the preview is closed", async () => {
    const user = userEvent.setup();
    render(<Workspace repository={{ owner: "acme", name: "checkout-service" }} />);

    await user.click(await screen.findByRole("button", { name: /src\/checkout.ts/i }));
    expect(await screen.findByText("return charge();")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Close preview" }));

    expect(screen.getByText("Select a source file to preview its contents.")).toBeInTheDocument();
    expect(screen.queryByText("return charge();")).not.toBeInTheDocument();
  });

  it("copies available active source content and disables copying when unavailable", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
    expect(navigator.clipboard.writeText).toBe(writeText);
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

describe("ChatPanel", () => {
  it("does not render a second thinking row after assistant streaming content begins", () => {
    const commonProps = {
      suggestions: [], input: "", onInputChange: vi.fn(), onSubmit: vi.fn(), onNewChat: vi.fn(), onSelectCitation: vi.fn(), onRetry: vi.fn(), isThinking: true,
    };
    const { rerender } = render(<ChatPanel {...commonProps} messages={[{ id: "assistant", conversation_id: "22222222-2222-4222-8222-222222222222", role: "assistant", content: "", completion_state: "streaming", created_at: "2026-08-08T04:00:00Z", completed_at: null, citations: [] }]} />);
    expect(screen.getByText(/searching sources/)).toBeInTheDocument();

    rerender(<ChatPanel {...commonProps} messages={[{ id: "assistant", conversation_id: "22222222-2222-4222-8222-222222222222", role: "assistant", content: "Streaming answer", completion_state: "streaming", created_at: "2026-08-08T04:00:00Z", completed_at: null, citations: [] }]} />);
    expect(screen.queryByText(/searching sources/)).not.toBeInTheDocument();
    expect(screen.getByText("Streaming answer")).toBeInTheDocument();
  });
});
