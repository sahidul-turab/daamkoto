import { Activity, Bookmark, Boxes, Search, Sparkles, Store, X } from "lucide-react";

export type View = "browse" | "build" | "scraper";

interface Props {
  search: string;
  onSearch: (v: string) => void;
  onOpenChat: () => void;
  onOpenPalette: () => void;
  totalRetailers: number;
  view: View;
  onViewChange: (v: View) => void;
  buildCount: number;
  watchlistCount: number;
  onOpenWatchlist: () => void;
}

export function Header({
  search,
  onSearch,
  onOpenChat,
  onOpenPalette,
  totalRetailers,
  view,
  onViewChange,
  buildCount,
  watchlistCount,
  onOpenWatchlist,
}: Props) {
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-canvas/70 backdrop-blur-xl">
      <div className="mx-auto flex max-w-[1320px] flex-col gap-4 px-4 py-4 md:flex-row md:items-center md:gap-6 md:px-6">
        {/* Logo */}
        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-xl bg-brand-strong text-white shadow-[0_8px_24px_-8px_rgba(227,30,36,0.9)]">
            <span className="text-lg font-black">৳</span>
          </div>
          <div className="leading-none">
            <div className="text-xl font-extrabold tracking-tight">
              Daam<span className="text-brand">Koto</span>
            </div>
            <div className="mt-1 text-[11px] font-medium text-ink-3">
              দাম কত? · {totalRetailers > 0 ? `${totalRetailers} retailers` : "Bangladesh"}
            </div>
          </div>
        </div>

        {/* View switch */}
        <div className="flex shrink-0 rounded-xl border border-line bg-surface-2 p-1 text-sm font-semibold">
          <button
            onClick={() => onViewChange("browse")}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 transition-colors ${
              view === "browse" ? "bg-brand-strong text-white" : "text-ink-3 hover:text-ink"
            }`}
          >
            <Store className="h-4 w-4" /> Browse
          </button>
          <button
            onClick={() => onViewChange("build")}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 transition-colors ${
              view === "build" ? "bg-brand-strong text-white" : "text-ink-3 hover:text-ink"
            }`}
          >
            <Boxes className="h-4 w-4" /> Build
            {buildCount > 0 && (
              <span className="rounded-full bg-white/20 px-1.5 text-[10px] tabular-nums">
                {buildCount}
              </span>
            )}
          </button>
          <button
            onClick={() => onViewChange("scraper")}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 transition-colors ${
              view === "scraper" ? "bg-brand-strong text-white" : "text-ink-3 hover:text-ink"
            }`}
            title="Scraper Health Dashboard"
          >
            <Activity className="h-4 w-4" /> Scraper
          </button>
        </div>

        {/* Search */}
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-4" />
          <input
            value={search}
            onChange={(e) => onSearch(e.target.value)}
            placeholder="Search a part — e.g. RTX 4060, 16GB DDR5, 990 Pro…"
            className="field !rounded-xl !py-3 pl-10 pr-10"
          />
          {search ? (
            <button
              onClick={() => onSearch("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-4 hover:text-ink"
              aria-label="Clear search"
            >
              <X className="h-4 w-4" />
            </button>
          ) : (
            <button
              onClick={onOpenPalette}
              className="absolute right-2.5 top-1/2 hidden -translate-y-1/2 items-center gap-1 rounded-md border border-line bg-surface-2 px-2 py-1 text-[11px] font-semibold text-ink-4 transition-colors hover:border-line-2 hover:text-ink-2 sm:flex"
              aria-label="Open command palette"
            >
              <span className="text-sm leading-none">⌘</span>K
            </button>
          )}
        </div>

        {/* Watchlist */}
        <button
          onClick={onOpenWatchlist}
          className="btn-ghost relative shrink-0 !rounded-xl"
          title="Watchlist"
        >
          <Bookmark className="h-4 w-4" />
          {watchlistCount > 0 && (
            <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-brand-strong text-[9px] font-bold text-white">
              {watchlistCount}
            </span>
          )}
        </button>

        {/* AI button */}
        <button onClick={onOpenChat} className="btn-brand shrink-0">
          <Sparkles className="h-4 w-4" />
          Ask AI
        </button>
      </div>
    </header>
  );
}
