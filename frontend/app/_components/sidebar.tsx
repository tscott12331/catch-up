import { Brand } from "./brand";
import { Icon } from "./icon";
import Link from "next/link";

type SidebarProps = {
  repoName: string;
  branch: string;
};

export function Sidebar({ repoName, branch }: SidebarProps) {
  return (
    <aside className="flex w-[242px] shrink-0 flex-col border-r border-line bg-sidebar px-4 pt-[26px] pb-[18px] max-[950px]:w-[205px] max-[760px]:hidden">
      <Brand compact />
      <Link className="flex items-center gap-[9px] rounded-[9px] border border-switcher-line bg-white/58 px-2.5 py-[11px] text-inherit no-underline [&>svg]:text-icon-muted" href="/" aria-label="Choose another repository">
        <div className="grid size-[26px] place-items-center rounded-[7px] bg-avatar-bg text-[10px] font-extrabold text-avatar-ink">CS</div>
        <div className="flex min-w-0 flex-1 flex-col gap-[3px]"><strong className="overflow-hidden text-xs text-ellipsis whitespace-nowrap">{repoName}</strong><span className="text-[10px] text-subtle-copy">{branch} · synced</span></div>
        <Icon name="chevron-down" size={14} />
      </Link>
      <nav className="pt-[29px]" aria-label="Primary navigation">
        <span className="block px-[11px] pb-[9px] text-[10px] font-bold tracking-[.11em] text-nav-label uppercase">Workspace</span>
        <a className="my-0.5 flex items-center gap-[11px] rounded-[7px] bg-nav-active-bg px-[11px] py-2.5 text-xs font-bold text-green-strong no-underline" href="#chat"><Icon name="sparkle" size={16} /> Ask the codebase</a>
        <a className="my-0.5 flex items-center gap-[11px] rounded-[7px] px-[11px] py-2.5 text-xs text-nav no-underline hover:bg-nav-hover-bg hover:text-ink" href="#explorer"><Icon name="code" size={16} /> Explorer</a>
      </nav>
      <div className="mt-auto">
        <div className="px-[11px] pt-[18px] text-[10px] text-local"><span className="mr-1.5 inline-block size-1.5 rounded-full bg-green align-px" /> Running locally</div>
      </div>
    </aside>
  );
}
