import Link from "next/link";
import { Icon } from "./icon";
import styles from "./shared.module.css";

type BrandProps = {
  compact?: boolean;
};

export function Brand({ compact = false }: BrandProps) {
  return (
    <Link href="/" className={`${styles.brand} ${compact ? styles.brandCompact : ""}`}>
      <span className={`${styles.brandMark} ${compact ? styles.compact : ""}`}><Icon name="logo" size={compact ? 17 : 18} /></span>
      <span>catch-up</span>
    </Link>
  );
}
