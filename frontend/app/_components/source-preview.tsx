import { useEffect, useRef } from "react";
import { Icon } from "./icon";
import type { Citation } from "../_lib/types";
import styles from "./workspace.module.css";

type SourcePreviewProps = {
  activeFile: string;
  previewLines: string[];
  status: "idle" | "loading" | "ready" | "unavailable";
  message: string;
  highlightedRange: Citation | null;
  onClose: () => void;
};

function highlightedLineRange(activeFile: string, previewLines: string[], citation: Citation | null): { start: number; end: number } | null {
  if (!citation || citation.path !== activeFile || previewLines.length === 0) return null;
  const start = Math.min(Math.max(citation.start_line, 1), previewLines.length);
  const end = Math.min(Math.max(citation.end_line, start), previewLines.length);
  return { start, end };
}

export function SourcePreview({ activeFile, previewLines, status, message, highlightedRange, onClose }: SourcePreviewProps) {
  const lineRefs = useRef(new Map<number, HTMLDivElement>());
  const range = highlightedLineRange(activeFile, previewLines, highlightedRange);

  useEffect(() => {
    if (status === "ready" && range) lineRefs.current.get(range.start)?.scrollIntoView({ block: "center" });
  }, [range, status]);

  return (
    <div className={styles.sourcePreview}>
      <div className={styles.sourceTitle}><span><Icon name="file" size={14} /> {activeFile || "Source preview"}</span><button aria-label="Close preview" onClick={onClose} disabled={!activeFile}><Icon name="x" size={15} /></button></div>
      <div className={styles.codeWindow}>
        {status === "loading" && <div className={styles.previewState}>Loading source…</div>}
        {status === "unavailable" && <div className={styles.previewState}>{message || "Source content is unavailable."}</div>}
        {status === "idle" && <div className={styles.previewState}>Select a source file to preview its contents.</div>}
        {status === "ready" && previewLines.map((line, index) => {
          const lineNumber = index + 1;
          const highlighted = range !== null && lineNumber >= range.start && lineNumber <= range.end;
          return <div className={`${styles.codeLine} ${highlighted ? styles.highlighted : ""}`} data-line-number={lineNumber} key={`${index}-${line}`} ref={(element) => {
            if (element) lineRefs.current.set(lineNumber, element);
            else lineRefs.current.delete(lineNumber);
          }}><span className={styles.lineNumber}>{lineNumber}</span><code>{line || " "}</code></div>;
        })}
      </div>
    </div>
  );
}
