import { Icon } from "./icon";
import styles from "./workspace.module.css";

type WorkspaceHeaderProps = {
  repoName: string;
  isIndexing: boolean;
  indexProgress: number;
  jobStatus: "queued" | "indexing" | "completed" | "failed" | "cancelled";
};

export function WorkspaceHeader({ repoName, isIndexing, indexProgress, jobStatus }: WorkspaceHeaderProps) {
  return (
    <>
      <header className={styles.workspaceHeader}>
        <div className={styles.breadcrumbs}>
          <span className={styles.mobileMenu}><Icon name="menu" size={18} /></span>
          <span className={styles.crumbMuted}>Workspace</span>
          <span className={styles.crumbSlash}>/</span>
          <span>{repoName}</span>
        </div>
        <div className={styles.headerActions}>
          <div className={`${styles.indexStatus} ${isIndexing ? styles.indexing : jobStatus === "failed" ? styles.failed : styles.ready}`}>
            <span className={styles.statusDot} />{isIndexing ? `Indexing ${indexProgress}%` : jobStatus === "failed" ? "Indexing failed" : jobStatus === "cancelled" ? "Indexing cancelled" : "Indexed just now"}
          </div>
          <button className={styles.iconButton} aria-label="Settings"><Icon name="settings" size={17} /></button>
        </div>
      </header>
      {isIndexing && <div className={styles.progressTrack}><div className={styles.progressBar} style={{ width: `${indexProgress}%` }} /></div>}
    </>
  );
}
