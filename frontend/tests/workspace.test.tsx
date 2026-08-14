import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Workspace } from "../app/_components/workspace";
import type { ApiClient } from "../app/_lib/api";
import type { ChatStreamEvent } from "../app/_lib/generated/sse-events";
import type { IndexingJob, WorkspacePayload } from "../app/_lib/types";

const repositoryId = "11111111-1111-4111-8111-111111111111";
const conversationId = "22222222-2222-4222-8222-222222222222";
const assistantId = "33333333-3333-4333-8333-333333333333";
const userId = "44444444-4444-4444-8444-444444444444";
const citation = { id: "66666666-6666-4666-8666-666666666666", passage_id: "77777777-7777-4777-8777-777777777777", revision: "abc123", path: "src/checkout.ts", start_line: 2, end_line: 3 };

const baseWorkspace: WorkspacePayload = {
  repository: {
    id: repositoryId,
    owner: "acme",
    name: "checkout-service",
    source_url: "https://github.com/acme/checkout-service",
    default_branch: "main",
    indexed_revision: "8a8b1b9f95ea2f76e67c11b79f138b5e8044be57",
  },
  conversation: { id: conversationId, repository_id: repositoryId, created_at: "2026-08-08T04:00:00Z", updated_at: "2026-08-08T04:00:00Z" },
  tree: [{ name: "README.md", type: "file" }, { name: "src", type: "folder", children: [{ name: "checkout.ts", type: "file" }] }],
  selected_file: "README.md",
  starter_questions: ["Where is authentication handled?"],
  messages: [{ id: "55555555-5555-4555-8555-555555555555", conversation_id: conversationId, role: "assistant", content: "Welcome", completion_state: "completed", created_at: "2026-08-08T04:00:00Z", completed_at: "2026-08-08T04:00:00Z", citations: [citation] }],
  job: { id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", repository_id: repositoryId, status: "completed", stage: "completed", progress: 100, created_at: "2026-08-08T04:00:00Z", updated_at: "2026-08-08T04:00:00Z", started_at: "2026-08-08T04:00:00Z", completed_at: "2026-08-08T04:00:00Z", error: null },
};

async function* noEvents(): AsyncGenerator<ChatStreamEvent> {}

function fakeClient(overrides: Partial<ApiClient> = {}): ApiClient {
  return {
    createRepository: vi.fn(),
    getWorkspace: vi.fn().mockResolvedValue(baseWorkspace),
    createConversation: vi.fn().mockResolvedValue(baseWorkspace.conversation),
    createIndexingJob: vi.fn().mockResolvedValue(baseWorkspace.job),
    cancelJob: vi.fn().mockResolvedValue(baseWorkspace.job),
    getJob: vi.fn().mockResolvedValue(baseWorkspace.job),
    getFile: vi.fn(async (_owner, _repo, path) => ({ path, content: path === "src/checkout.ts" ? "export function checkout() {\n  return charge();\n}" : "# Checkout service\nDetails" })),
    streamChat: vi.fn(noEvents),
    ...overrides,
  };
}

function renderWorkspace(client: ApiClient) {
  return render(<Workspace repository={{ owner: "acme", name: "checkout-service" }} client={client} />);
}

afterEach(() => vi.restoreAllMocks());

describe("Workspace", () => {
  it("renders the loaded repository workspace and source preview through an injected client", async () => {
    const client = fakeClient();
    renderWorkspace(client);

    expect(await screen.findByText("Repository explorer")).toBeInTheDocument();
    await waitFor(() => expect(client.getFile).toHaveBeenCalledWith("acme", "checkout-service", "README.md", expect.any(AbortSignal)));
    expect(screen.getByText("# Checkout service")).toBeInTheDocument();
    expect(screen.getByText("Indexed just now")).toBeInTheDocument();
  });

  it("opens parent folders and loads a cited file", async () => {
    Object.defineProperty(Element.prototype, "scrollIntoView", { configurable: true, value: vi.fn() });
    const client = fakeClient();
    const user = userEvent.setup();
    renderWorkspace(client);

    await user.click(await screen.findByRole("button", { name: /src\/checkout.ts/i }));

    expect(await screen.findByRole("button", { name: "checkout.ts" })).toBeInTheDocument();
    await waitFor(() => expect(client.getFile).toHaveBeenCalledWith("acme", "checkout-service", "src/checkout.ts", expect.any(AbortSignal)));
    expect(await screen.findByText("return charge();")).toBeInTheDocument();
    expect(document.querySelector('[data-line-number="2"]')?.className).toContain("highlighted");
  });

  it("keeps an already-loaded source visible when a streamed answer cites that active file", async () => {
    const activeCitation = { ...citation, path: "README.md", start_line: 1, end_line: 2 };
    async function* answerEvents(): AsyncGenerator<ChatStreamEvent> {
      yield { type: "message.started", repository_id: repositoryId, conversation_id: conversationId, message_id: assistantId, user_message_id: userId };
      yield { type: "message.delta", repository_id: repositoryId, conversation_id: conversationId, message_id: assistantId, text: "Streaming answer" };
      yield { type: "message.completed", repository_id: repositoryId, conversation_id: conversationId, message_id: assistantId, citations: [activeCitation] };
    }
    const scrollIntoView = vi.fn();
    Object.defineProperty(Element.prototype, "scrollIntoView", { configurable: true, value: scrollIntoView });
    const client = fakeClient({ streamChat: vi.fn(answerEvents) });
    const user = userEvent.setup();
    renderWorkspace(client);

    const composer = await screen.findByPlaceholderText("Ask anything about this repository...");
    await waitFor(() => expect(screen.getByText("# Checkout service")).toBeInTheDocument());
    await user.type(composer, "How does it work?");
    await user.click(screen.getByRole("button", { name: "Send question" }));
    expect(await screen.findByText("Streaming answer")).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: /README.md/i })[0]);

    expect(screen.getByText("# Checkout service")).toBeInTheDocument();
    expect(document.querySelector('[data-line-number="1"]')?.className).toContain("highlighted");
    expect(scrollIntoView).toHaveBeenCalledWith({ block: "center" });
    expect(client.getFile).toHaveBeenCalledTimes(1);
  });

  it("closes the active source preview", async () => {
    const client = fakeClient();
    const user = userEvent.setup();
    renderWorkspace(client);

    expect(await screen.findByText("# Checkout service")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Close preview" }));

    expect(screen.getByText("Select a source file to preview its contents.")).toBeInTheDocument();
    expect(screen.queryByText("# Checkout service")).not.toBeInTheDocument();
  });

  it("retries workspace loading without invoking indexing", async () => {
    const getWorkspace = vi.fn()
      .mockRejectedValueOnce(new Error("Repository was not found."))
      .mockResolvedValueOnce(baseWorkspace);
    const client = fakeClient({ getWorkspace });
    const user = userEvent.setup();
    renderWorkspace(client);

    expect(await screen.findByText("Repository was not found.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry workspace" }));

    expect(await screen.findByText("Repository explorer")).toBeInTheDocument();
    expect(getWorkspace).toHaveBeenCalledTimes(2);
    expect(client.createIndexingJob).not.toHaveBeenCalled();
  });

  it("restarts failed indexing without reloading the workspace", async () => {
    const failedJob: IndexingJob = { ...baseWorkspace.job, status: "failed", stage: "failed", progress: 42, completed_at: null, error: { code: "index_failed", message: "Index failed." } };
    const replacementJob: IndexingJob = { ...baseWorkspace.job, id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb" };
    const client = fakeClient({
      getWorkspace: vi.fn().mockResolvedValue({ ...baseWorkspace, job: failedJob }),
      createIndexingJob: vi.fn().mockResolvedValue(replacementJob),
    });
    const user = userEvent.setup();
    renderWorkspace(client);

    const notice = await screen.findByRole("alert");
    expect(notice).toHaveTextContent("Indexing failed");
    await user.click(screen.getByRole("button", { name: "Retry" }));

    await waitFor(() => expect(screen.getByText("Indexed just now")).toBeInTheDocument());
    expect(client.createIndexingJob).toHaveBeenCalledWith(repositoryId, expect.any(AbortSignal));
    expect(client.getWorkspace).toHaveBeenCalledTimes(1);
  });

  it("keeps new-conversation failures separate from indexing errors", async () => {
    const client = fakeClient({ createConversation: vi.fn().mockRejectedValue(new Error("A new conversation could not be created.")) });
    const user = userEvent.setup();
    renderWorkspace(client);

    await user.click(await screen.findByRole("button", { name: /new chat/i }));

    const notice = await screen.findByRole("alert");
    expect(notice).toHaveTextContent("A new conversation could not be created.");
    expect(screen.queryByText(/Indexing failed/)).not.toBeInTheDocument();
    expect(client.createIndexingJob).not.toHaveBeenCalled();
  });
});
