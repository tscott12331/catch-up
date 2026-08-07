import { Brand } from "./brand";
import { Icon } from "./icon";
import Link from "next/link";
import styles from "./workspace.module.css";

type SidebarProps = {
  repoName: string;
  branch: string;
};

export function Sidebar({ repoName, branch }: SidebarProps) {
  return (
    <aside className={styles.sidebar}>
      <Brand compact />
      <Link className={styles.repoSwitcher} href="/" aria-label="Choose another repository">
        <div className={styles.repoAvatar}>CS</div>
        <div className={styles.repoSwitcherCopy}><strong>{repoName}</strong><span>{branch} · synced</span></div>
        <Icon name="chevron-down" size={14} />
      </Link>
      <nav className={styles.sideNav} aria-label="Primary navigation">
        <span className={styles.navLabel}>Workspace</span>
        <a className={`${styles.navItem} ${styles.active}`} href="#chat"><Icon name="sparkle" size={16} /> Ask the codebase</a>
        <a className={styles.navItem} href="#explorer"><Icon name="code" size={16} /> Explorer</a>
        <span className={`${styles.navLabel} ${styles.navLabelSpaced}`}>Repository</span>
        <a className={styles.navItem} href="#overview"><Icon name="book" size={16} /> Overview</a>
        <a className={styles.navItem} href="#branches"><Icon name="branch" size={16} /> Branches <span className={styles.navSoon}>soon</span></a>
      </nav>
      <div className={styles.sidebarBottom}>
        <a className={styles.navItem} href="#settings"><Icon name="settings" size={16} /> Settings</a>
        <div className={styles.localBadge}><span className={styles.statusDot} /> Running locally</div>
      </div>
    </aside>
  );
}
