import type { KeyboardEvent, SubmitEvent } from "react";
import { Icon } from "./icon";
import type { ChatMessage, Citation } from "../_lib/types";
import styles from "./workspace.module.css";

type ChatPanelProps = {
  messages: ChatMessage[];
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
    <section className={styles.chatPanel} id="chat">
      <div className={styles.panelHeading}>
        <div><p className={styles.sectionKicker}>Conversation</p><h2>Ask the codebase</h2></div>
        <button className={styles.newChat} onClick={onNewChat}><Icon name="plus" size={15} /> New chat</button>
      </div>
      <div className={styles.suggestionRow}>
        {suggestions.map((suggestion) => <button key={suggestion} onClick={() => onInputChange(suggestion)}>{suggestion}</button>)}
      </div>
      <div className={styles.messages} aria-live="polite">
        {messages.map((message) => (
          <article className={`${styles.message} ${styles[message.role]}`} key={message.id}>
            <div className={`${styles.messageAvatar} ${styles[message.role]}`}>
              {message.role === "assistant" ? <Icon name="logo" size={15} /> : "you"}
            </div>
            <div className={styles.messageBody}>
              <div className={styles.messageMeta}><strong>{message.role === "assistant" ? "catch-up" : "You"}</strong>{message.role === "assistant" && <span>· grounded answer</span>}</div>
              {message.content && <p>{message.content}</p>}
              {message.citations && <div className={styles.citations}>
                <span className={styles.citationLabel}>Sources</span>
                {message.citations.map((citation) => (
                  <button className={styles.citation} key={`${citation.file}-${citation.start_line}`} onClick={() => onSelectCitation(citation)}>
                    <Icon name="file" size={13} /><span>{citation.file}</span><small>{citation.start_line}–{citation.end_line}</small>
                  </button>
                ))}
              </div>}
              {message.error && <div className={styles.messageError} role="alert"><span>{message.error}</span>{message.retryQuestion && <button onClick={() => onRetry(message.retryQuestion || "")}>Try again</button>}</div>}
            </div>
          </article>
        ))}
        {isThinking && <article className={`${styles.message} ${styles.assistant}`}>
          <div className={`${styles.messageAvatar} ${styles.assistant}`}><Icon name="logo" size={15} /></div>
          <div className={styles.messageBody}><div className={styles.messageMeta}><strong>catch-up</strong><span>· searching sources</span></div><div className={styles.thinking}><i /><i /><i /></div></div>
        </article>}
      </div>
      <form className={styles.composer} onSubmit={onSubmit}>
        <textarea value={input} onChange={(event) => onInputChange(event.target.value)} onKeyDown={handleKeyDown} placeholder="Ask anything about this repository..." rows={2} />
        <div className={styles.composerFooter}><span><Icon name="sparkle" size={14} /> Answers cite source files</span><button className={styles.sendButton} type="submit" disabled={!input.trim() || isThinking} aria-label="Send question"><Icon name="arrow-up" size={17} /></button></div>
      </form>
    </section>
  );
}
