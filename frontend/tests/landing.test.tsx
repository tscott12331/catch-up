import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Landing } from "../app/_components/landing";
import { ApiError, createRepository } from "../app/_lib/api";

const push = vi.fn();

vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("../app/_lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../app/_lib/api")>();
  return { ...actual, createRepository: vi.fn() };
});

const createRepositoryMock = vi.mocked(createRepository);

describe("Landing", () => {
  beforeEach(() => {
    push.mockReset();
    createRepositoryMock.mockReset();
  });

  it("creates a repository and opens its workspace", async () => {
    createRepositoryMock.mockResolvedValue({
      repository: {
        id: "repo_acme_checkout-service",
        owner: "acme",
        name: "checkout-service",
        url: "https://github.com/acme/checkout-service",
        default_branch: "main",
      },
      job: { id: "job_acme_checkout-service", status: "queued", progress: 0 },
    });
    const user = userEvent.setup();

    render(<Landing />);
    await user.type(screen.getByLabelText("Repository URL"), "https://github.com/acme/checkout-service");
    await user.click(screen.getByRole("button", { name: /connect/i }));

    await waitFor(() => expect(createRepositoryMock).toHaveBeenCalledWith("https://github.com/acme/checkout-service"));
    expect(push).toHaveBeenCalledWith("/repositories/acme/checkout-service");
  });

  it("shows the backend error when repository creation fails", async () => {
    createRepositoryMock.mockRejectedValue(new ApiError(422, { code: "invalid_repository_url", message: "Use a public GitHub repository URL." }));
    const user = userEvent.setup();

    render(<Landing />);
    await user.type(screen.getByLabelText("Repository URL"), "not a repository");
    await user.click(screen.getByRole("button", { name: /connect/i }));

    expect(await screen.findByText("Use a public GitHub repository URL.")).toBeInTheDocument();
  });
});
