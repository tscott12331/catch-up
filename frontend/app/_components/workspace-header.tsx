import { Icon } from "./icon";

type WorkspaceHeaderProps = {
  repoName: string;
  isIndexing: boolean;
  indexProgress: number;
  jobStatus: "queued" | "indexing" | "completed" | "failed" | "cancelled";
};

export function WorkspaceHeader({ repoName, isIndexing, indexProgress, jobStatus }: WorkspaceHeaderProps) {
  const statusDot = isIndexing
    ? "bg-orange animate-status-pulse"
    : jobStatus === "failed"
      ? "bg-danger"
      : "bg-green";

  return (
    <>
      <header className="flex min-h-[70px] items-center justify-between border-b border-line bg-white/55 px-[31px] max-[950px]:px-[25px] max-[760px]:min-h-[60px] max-[760px]:px-[17px]">
        <div className="flex items-center gap-2.5 text-xs font-semibold text-header-copy">
          <span className="mr-1 hidden max-[760px]:inline-flex"><Icon name="menu" size={18} /></span>
          <span className="font-normal text-header-muted">Workspace</span>
          <span className="font-normal text-header-muted">/</span>
          <span>{repoName}</span>
        </div>
        <div className="flex items-center gap-5 max-[760px]:gap-2.5">
          <div className="text-[11px] text-status max-[760px]:text-[10px]">
            <span className={`mr-2 inline-block size-[7px] rounded-full align-px ${statusDot}`} />{isIndexing ? `Indexing ${indexProgress}%` : jobStatus === "failed" ? "Indexing failed" : jobStatus === "cancelled" ? "Indexing cancelled" : "Indexed just now"}
          </div>
          <button className="grid size-[30px] place-items-center rounded-[7px] border border-transparent bg-transparent p-0 text-icon hover:border-line hover:bg-white hover:text-ink disabled:cursor-not-allowed disabled:opacity-45" aria-label="Settings"><Icon name="settings" size={17} /></button>
        </div>
      </header>
      {isIndexing && <div className="h-0.5 bg-progress"><div className="h-full bg-green transition-[width] duration-250 ease-[ease]" style={{ width: `${indexProgress}%` }} /></div>}
    </>
  );
}
