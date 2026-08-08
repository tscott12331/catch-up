import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Workspace } from "../app/_components/workspace";
import { getFile, getWorkspace } from "../app/_lib/api";

vi.mock("../app/_lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../app/_lib/api")>();
  return { ...actual, getFile: vi.fn(), getWorkspace: vi.fn() };
});

const getWorkspaceMock = vi.mocked(getWorkspace);
const getFileMock = vi.mocked(getFile);

describe("Workspace", () => {
  beforeEach(() => {
    getWorkspaceMock.mockReset();
    getFileMock.mockReset();
    getWorkspaceMock.mockResolvedValue({
      repository: {
        id: "11111111-1111-4111-8111-111111111111",
        owner: "acme",
        name: "checkout-service",
        source_url: "https://github.com/acme/checkout-service",
        default_branch: "main",
        indexed_revision: "8a8b1b9f95ea2f76e67c11b79f138b5e8044be57",
      },
      conversation: { id: "22222222-2222-4222-8222-222222222222", repository_id: "11111111-1111-4111-8111-111111111111", created_at: "2026-08-08T04:00:00Z", updated_at: "2026-08-08T04:00:00Z" },
      tree: [{ name: "README.md", type: "file" }],
      selected_file: "README.md",
      starter_questions: ["Where is authentication handled?"],
      messages: [{ id: "55555555-5555-4555-8555-555555555555", conversation_id: "22222222-2222-4222-8222-222222222222", role: "assistant", content: "Welcome", completion_state: "completed", created_at: "2026-08-08T04:00:00Z", completed_at: "2026-08-08T04:00:00Z", citations: [] }],
      passages: [],
      job: { id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", repository_id: "11111111-1111-4111-8111-111111111111", status: "completed", stage: "completed", progress: 100, created_at: "2026-08-08T04:00:00Z", updated_at: "2026-08-08T04:00:00Z", started_at: "2026-08-08T04:00:00Z", completed_at: "2026-08-08T04:00:00Z", error: null },
    });
    getFileMock.mockResolvedValue({ path: "README.md", content: "# Checkout service" });
  });

  it("renders the loaded repository workspace and source preview", async () => {
    render(<Workspace repository={{ owner: "acme", name: "checkout-service" }} />);

    expect(await screen.findByText("Repository explorer")).toBeInTheDocument();
    await waitFor(() => expect(getFileMock).toHaveBeenCalledWith("acme", "checkout-service", "README.md", expect.any(AbortSignal)));
    expect(screen.getByText("# Checkout service")).toBeInTheDocument();
    expect(screen.getByText("Indexed just now")).toBeInTheDocument();
  });
});
