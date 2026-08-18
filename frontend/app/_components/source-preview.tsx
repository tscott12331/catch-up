import { useEffect, useRef } from "react";
import { Icon } from "./icon";
import type { Citation } from "../_lib/types";

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
    <div className="mt-[21px] overflow-hidden rounded-[7px] border border-tree-line bg-white">
      <div className="flex items-center justify-between border-b border-source-line px-[11px] py-2.5 text-[10px] text-source-copy"><span className="flex items-center gap-1.5 overflow-hidden text-ellipsis whitespace-nowrap"><Icon name="file" size={14} /> {activeFile || "Source preview"}</span><button className="border-0 bg-transparent text-message-muted" aria-label="Close preview" onClick={onClose} disabled={!activeFile}><Icon name="x" size={15} /></button></div>
      <div className="overflow-auto bg-panel py-2.5 font-mono text-[9px] leading-[1.9]">
        {status === "loading" && <div className="px-3 py-[18px] font-[inherit] text-[10px] leading-normal text-preview-state">Loading source…</div>}
        {status === "unavailable" && <div className="px-3 py-[18px] font-[inherit] text-[10px] leading-normal text-preview-state">{message || "Source content is unavailable."}</div>}
        {status === "idle" && <div className="px-3 py-[18px] font-[inherit] text-[10px] leading-normal text-preview-state">Select a source file to preview its contents.</div>}
        {status === "ready" && previewLines.map((line, index) => {
          const lineNumber = index + 1;
          const highlighted = range !== null && lineNumber >= range.start && lineNumber <= range.end;
          return <div className={`flex min-w-max pr-4 text-code-copy ${highlighted ? "highlighted bg-code-highlight" : ""}`} data-line-number={lineNumber} key={`${index}-${line}`} ref={(element) => {
            if (element) lineRefs.current.set(lineNumber, element);
            else lineRefs.current.delete(lineNumber);
          }}><span className="w-8 pr-[9px] text-right text-line-number select-none">{lineNumber}</span><code className="whitespace-pre">{line || " "}</code></div>;
        })}
      </div>
    </div>
  );
}
