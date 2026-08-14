import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ChatPanel } from "../app/_components/chat-panel";

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
