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
        id: "repo_acme_checkout-service",
        owner: "acme",
        name: "checkout-service",
        url: "https://github.com/acme/checkout-service",
        default_branch: "main",
      },
      tree: [{ name: "README.md", type: "file" }],
      selected_file: "README.md",
      starter_questions: ["Where is authentication handled?"],
      messages: [{ id: "message_welcome", role: "assistant", content: "Welcome" }],
      job: { id: "job_acme_checkout-service", status: "completed", progress: 100 },
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
