import { Bookmark, Boxes, Home, LockKeyhole, LogOut, Search, Sparkles, Store, Tag } from "lucide-react";

export type View = "home" | "browse" | "build" | "deals" | "admin";

interface Props {
  onGoHome: () => void;
  onOpenChat: () => void;
  onOpenPalette: () => void;
  totalRetailers: number;
  view: View;
  onViewChange: (v: View) => void;
  buildCount: number;
  watchlistCount: number;
  onOpenWatchlist: () => void;
  isAdmin: boolean;
  onLogout: () => void;
}

export function Header({
  onGoHome,
  onOpenChat,
  onOpenPalette,
  totalRetailers,
  view,
  onViewChange,
  buildCount,
  watchlistCount,
  onOpenWatchlist,
  isAdmin,
  onLogout,
}: Props) {
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-canvas/70 backdrop-blur-xl">
      <div className="app-shell flex flex-wrap items-center gap-3 py-3 lg:flex-nowrap lg:gap-4">
        {/* Logo */}
        <button
          type="button"
          onClick={onGoHome}
          className="order-1 flex shrink-0 items-center gap-3 rounded-xl text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
          aria-label="Go to DaamKoto homepage"
        >
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
        </button>

        {/* View switch */}
        <div className="no-scrollbar order-4 flex w-full shrink-0 overflow-x-auto rounded-xl border border-line bg-surface-2 p-1 text-sm font-semibold lg:order-2 lg:w-auto">
          <button
            onClick={() => onViewChange("home")}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 transition-colors ${
              view === "home" ? "bg-brand-strong text-white" : "text-ink-3 hover:text-ink"
            }`}
          >
            <Home className="h-4 w-4" /> Home
          </button>
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
            onClick={() => onViewChange("deals")}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 transition-colors ${
              view === "deals" ? "bg-brand-strong text-white" : "text-ink-3 hover:text-ink"
            }`}
            title="Daily price-drop deals"
          >
            <Tag className="h-4 w-4" /> Deals
          </button>
          <button
            onClick={() => onViewChange("admin")}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 transition-colors ${
              view === "admin" ? "bg-brand-strong text-white" : "text-ink-3 hover:text-ink"
            }`}
            title={isAdmin ? "Owner dashboard" : "Owner sign in"}
          >
            <LockKeyhole className="h-4 w-4" /> Admin
            {isAdmin && <span className="h-1.5 w-1.5 rounded-full bg-ok" />}
          </button>
        </div>

        {/* Search */}
        <button
          type="button"
          onClick={onOpenPalette}
          className="group order-5 flex w-full items-center gap-3 rounded-xl border border-brand/45 bg-brand-strong/[0.07] px-3.5 py-2.5 text-left shadow-[0_8px_30px_-18px_rgba(239,35,42,0.9)] transition-all hover:border-brand hover:bg-brand-strong/[0.12] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand lg:order-3 lg:flex-1"
          aria-label="Search products across all categories"
        >
          <Search className="h-4 w-4 shrink-0 text-brand" />
          <span className="min-w-0 flex-1 truncate text-sm font-semibold text-ink-2 group-hover:text-ink">
            Search products
            <span className="ml-2 hidden font-normal text-ink-4 xl:inline">RTX 4060, Ryzen 7, 990 Pro…</span>
          </span>
          <span className="hidden shrink-0 items-center gap-1 rounded-md border border-brand/25 bg-surface-2 px-2 py-1 text-[10px] font-semibold text-ink-4 sm:flex">
            Ctrl K
          </span>
        </button>

        {/* Watchlist */}
        <button
          onClick={onOpenWatchlist}
          className="btn-ghost order-2 ml-auto shrink-0 !rounded-xl lg:order-4 lg:ml-0"
          title="Watchlist"
        >
          <Bookmark className="h-4 w-4" />
          {watchlistCount > 0 && (
            <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-brand-strong text-[9px] font-bold text-white">
              {watchlistCount}
            </span>
          )}
        </button>

        {isAdmin && (
          <button
            onClick={onLogout}
            className="btn-ghost order-3 shrink-0 !rounded-xl !p-3 lg:order-5"
            title="Sign out of admin"
            aria-label="Sign out of admin"
          >
            <LogOut className="h-4 w-4" />
          </button>
        )}

        {/* AI button */}
        <button onClick={onOpenChat} className="btn-brand order-3 shrink-0 lg:order-5" aria-label="Ask AI">
          <Sparkles className="h-4 w-4" />
          <span className="hidden sm:inline">Ask AI</span>
        </button>
      </div>
    </header>
  );
}
