import { Icon } from "./icon";
import type { Citation } from "../_lib/types";
import styles from "./workspace.module.css";

type SourcePreviewProps = {
  activeFile: string;
  previewLines: string[];
  status: "idle" | "loading" | "ready" | "unavailable";
  message: string;
  highlightedRange: Citation | null;
};

export function SourcePreview({ activeFile, previewLines, status, message, highlightedRange }: SourcePreviewProps) {
  return (
    <div className={styles.sourcePreview}>
      <div className={styles.sourceTitle}><span><Icon name="file" size={14} /> {activeFile || "Source preview"}</span><button aria-label="Close preview"><Icon name="x" size={15} /></button></div>
      <div className={styles.codeWindow}>
        {status === "loading" && <div className={styles.previewState}>Loading source…</div>}
        {status === "unavailable" && <div className={styles.previewState}>{message || "Source content is unavailable."}</div>}
        {status === "idle" && <div className={styles.previewState}>Select a source file to preview its contents.</div>}
        {status === "ready" && previewLines.map((line, index) => {
          const lineNumber = index + 1;
          const highlighted = highlightedRange?.file === activeFile && lineNumber >= highlightedRange.start_line && lineNumber <= highlightedRange.end_line;
          return <div className={`${styles.codeLine} ${highlighted ? styles.highlighted : ""}`} key={`${index}-${line}`}><span className={styles.lineNumber}>{lineNumber}</span><code>{line || " "}</code></div>;
        })}
      </div>
    </div>
  );
}
