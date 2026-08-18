import type { KeyboardEvent, SubmitEvent } from "react";
import { Icon } from "./icon";
import type { Citation, DisplayMessage } from "../_lib/types";

type ChatPanelProps = {
  messages: DisplayMessage[];
  suggestions: string[];
  input: string;
  isThinking: boolean;
  onInputChange: (value: string) => void;
  onSubmit: (event: SubmitEvent<HTMLFormElement>) => void;
  onNewChat: () => void;
  onSelectCitation: (citation: Citation) => void;
  onRetry: (question: string) => void;
};

export function ChatPanel({ messages, suggestions, input, isThinking, onInputChange, onSubmit, onNewChat, onSelectCitation, onRetry }: ChatPanelProps) {
  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  return (
    <section className="flex min-w-0 flex-col overflow-y-hidden border-r border-line bg-panel px-[42px] pt-[37px] pb-7 max-[950px]:px-[27px] max-[760px]:min-h-[calc(100vh-62px)] max-[760px]:border-r-0 max-[760px]:px-[17px] max-[760px]:pt-7 max-[760px]:pb-[18px]" id="chat">
      <div className="flex items-start justify-between">
        <div><p className="mb-[7px] text-[10px] font-bold tracking-[.14em] text-section uppercase">Conversation</p><h2 className="m-0 font-serif text-[25px] font-normal tracking-[-.03em] max-[430px]:text-[22px]">Ask the codebase</h2></div>
        <button className="inline-flex items-center gap-[7px] rounded-md border border-button-line bg-white px-[11px] py-2 text-[11px] text-button-copy hover:border-interactive-line hover:text-green max-[430px]:text-[10px]" onClick={onNewChat}><Icon name="plus" size={15} /> New chat</button>
      </div>
      <div className="mt-[27px] mb-2 flex gap-2 overflow-x-auto max-[430px]:mt-[22px]">
        {suggestions.map((suggestion) => <button className="shrink-0 rounded-[20px] border border-chip-line bg-transparent px-[11px] py-2 text-[11px] text-chip-copy hover:border-interactive-line hover:bg-chip-hover hover:text-green" key={suggestion} onClick={() => onInputChange(suggestion)}>{suggestion}</button>)}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-0.5 pt-[17px] pb-6 [scrollbar-width:thin]" aria-live="polite">
        {messages.map((message) => (
          <article className="my-[22px] flex max-w-[730px] gap-3 first:mt-[11px]" key={message.id}>
            <div className={`grid size-[25px] shrink-0 place-items-center rounded-[7px] text-[9px] font-bold uppercase ${message.role === "assistant" ? "bg-green text-white" : "bg-avatar-soft text-avatar-copy"}`}>
              {message.role === "assistant" ? <Icon name="logo" size={15} /> : "you"}
            </div>
            <div className="min-w-0 flex-1">
              <div className="mt-0.5 mb-2 flex items-center gap-[7px] text-[11px] text-message-meta"><strong>{message.role === "assistant" ? "catch-up" : "You"}</strong>{message.role === "assistant" && <span className="font-normal text-message-muted">· grounded answer</span>}</div>
              {message.content && <p className={`m-0 max-w-[650px] whitespace-pre-line text-[13px] leading-[1.75] max-[760px]:text-xs ${message.role === "user" ? "text-copy-strong" : "text-copy"}`}>{message.content}</p>}
              {message.citations && <div className="mt-[15px] flex flex-wrap items-center gap-[7px]">
                <span className="mr-[3px] text-[10px] text-citation-label uppercase">Sources</span>
                {message.citations.map((citation) => (
                  <button className="inline-flex items-center gap-1.5 rounded-[5px] border border-citation-line bg-action-bg px-2 py-1.5 text-[10px] text-citation-copy hover:bg-citation-hover" key={`${citation.passage_id}-${citation.start_line}`} onClick={() => onSelectCitation(citation)}>
                    <Icon name="file" size={13} /><span>{citation.path}</span><small className="text-[9px] text-citation-meta">{citation.start_line}–{citation.end_line}</small>
                  </button>
                ))}
              </div>}
              {message.error && <div className="mt-3 flex items-center gap-2.5 text-[11px] text-error-copy" role="alert"><span>{message.error}</span>{message.retryQuestion && <button className="rounded-md border border-action-line bg-action-bg px-[11px] py-2 text-[11px] font-bold text-green-ink" onClick={() => onRetry(message.retryQuestion || "")}>Try again</button>}</div>}
            </div>
          </article>
        ))}
        {isThinking && !messages.some((message) => message.role === "assistant" && message.completion_state === "streaming" && message.content) && <article className="my-[22px] flex max-w-[730px] gap-3 first:mt-[11px]">
          <div className="grid size-[25px] shrink-0 place-items-center rounded-[7px] bg-green text-[9px] font-bold text-white uppercase"><Icon name="logo" size={15} /></div>
          <div className="min-w-0 flex-1"><div className="mt-0.5 mb-2 flex items-center gap-[7px] text-[11px] text-message-meta"><strong>catch-up</strong><span className="font-normal text-message-muted">· searching sources</span></div><div className="flex gap-1 pt-[7px] [&>i]:size-[5px] [&>i]:animate-thinking-bounce [&>i]:rounded-full [&>i]:bg-thinking [&>i:nth-child(2)]:[animation-delay:.15s] [&>i:nth-child(3)]:[animation-delay:.3s]"><i /><i /><i /></div></div>
        </article>}
      </div>
      <form className="rounded-[9px] border border-composer-line bg-white py-[5px] pr-[5px] pl-[15px] shadow-composer focus-within:border-composer-focus focus-within:ring-3 focus-within:ring-green/10" onSubmit={onSubmit}>
        <textarea className="block w-full resize-none border-0 text-[13px] leading-normal text-composer-copy outline-0 placeholder:text-composer-placeholder" value={input} onChange={(event) => onInputChange(event.target.value)} onKeyDown={handleKeyDown} placeholder="Ask anything about this repository..." rows={2} />
        <div className="mt-[5px] flex items-center justify-between text-[10px] text-composer-meta"><span className="inline-flex items-center gap-[5px]"><Icon name="sparkle" size={14} /> Answers cite source files</span><button className="inline-flex size-[29px] items-center justify-center gap-2 rounded-[7px] border-0 bg-green text-white transition-[background,transform] duration-200 hover:-translate-y-px hover:bg-green-hover disabled:cursor-default disabled:opacity-40 disabled:transform-none" type="submit" disabled={!input.trim() || isThinking} aria-label="Send question"><Icon name="arrow-up" size={17} /></button></div>
      </form>
    </section>
  );
}
