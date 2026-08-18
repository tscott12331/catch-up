import Link from "next/link";
import { Icon } from "./icon";

type BrandProps = {
  compact?: boolean;
};

export function Brand({ compact = false }: BrandProps) {
  return (
    <Link href="/" className={`flex items-center gap-2.5 font-bold tracking-[-.02em] ${compact ? "px-2.5 pb-8 text-[15px]" : ""}`}>
      <span className={`grid place-items-center bg-green text-white ${compact ? "size-[25px] rounded-[7px]" : "size-7 rounded-lg"}`}><Icon name="logo" size={compact ? 17 : 18} /></span>
      <span>catch-up</span>
    </Link>
  );
}
