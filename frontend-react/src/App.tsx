import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import type { ProductSummary } from "./types";
import { useProductSearch } from "./lib/useProductSearch";
import { Header, type View } from "./components/Header";
import { CategoryTabs } from "./components/CategoryTabs";
import { FilterSidebar } from "./components/FilterSidebar";
import { FilterChips } from "./components/FilterChips";
import { ProductGrid } from "./components/ProductGrid";
import { ProductDrawer } from "./components/ProductDrawer";
import { WatchlistPanel } from "./components/WatchlistPanel";
import { Chatbot } from "./components/Chatbot";
import { Pagination } from "./components/Pagination";
import { CommandPalette } from "./components/CommandPalette";
import { BuildStudio } from "./components/build/BuildStudio";
import { ScraperDashboard } from "./components/ScraperDashboard";
import { useBuild } from "./lib/useBuild";
import { useWatchlist } from "./lib/useWatchlist";
import { useUrlFilters } from "./lib/useUrlFilters";
import { slotForCategory } from "./lib/buildConfig";
import { Check, SlidersHorizontal } from "lucide-react";

export default function App() {
  const {
    category, filters, page, setPage,
    onSelectCategory, patchFilters, resetFilters, totalPages,
  } = useUrlFilters();

  const [selected, setSelected] = useState<ProductSummary | null>(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [watchlistOpen, setWatchlistOpen] = useState(false);
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);
  const [retailerCount, setRetailerCount] = useState(0);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [view, setView] = useState<View>(() => {
    if (window.location.hash.startsWith("#build"))   return "build";
    if (window.location.hash.startsWith("#scraper")) return "scraper";
    return "browse";
  });
  const [addedToast, setAddedToast] = useState<string | null>(null);

  const { build, setPart, addLine, setQty, removeLine, setLineRetailer, removePart, clear, shareUrl, count: buildCount } = useBuild();
  const { items: watchlist, isWatched, toggle: toggleWatch, remove: removeWatched } = useWatchlist();

  // Once: how many retailers exist (for the header subtitle).
  useEffect(() => {
    api
      .retailers()
      .then((r) => setRetailerCount(Array.isArray(r) ? r.length : 0))
      .catch(() => void 0);
  }, []);

  // "Add to Build" — called from ProductCard / ProductDrawer. Adds the product and
  // redirects to the build view so the user immediately sees their updated build.
  const addToBuild = useCallback((p: ProductSummary) => {
    const slotId = slotForCategory(p.category);
    if (!slotId) return;
    if (["ram", "storage"].includes(slotId)) {
      addLine(slotId, p);
    } else {
      setPart(slotId, p);
    }
    setView("build");
    setAddedToast(p.name);
    setTimeout(() => setAddedToast(null), 2200);
  }, [setPart, addLine, setView]);

  // Global ⌘K / Ctrl-K.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      } else if (e.key === "Escape") {
        setPaletteOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Pointer-reactive aurora.
  useEffect(() => {
    let raf = 0;
    const onMove = (e: PointerEvent) => {
      if (raf) return;
      raf = requestAnimationFrame(() => {
        raf = 0;
        document.body.style.setProperty("--aurora-x", `${(e.clientX / window.innerWidth) * 100}%`);
        document.body.style.setProperty("--aurora-y", `${(e.clientY / window.innerHeight) * 100}%`);
      });
    };
    window.addEventListener("pointermove", onMove);
    return () => { window.removeEventListener("pointermove", onMove); if (raf) cancelAnimationFrame(raf); };
  }, []);

  const { products, total, loading } = useProductSearch(category.db, filters, page);
  const numTotalPages = totalPages(total);

  return (
    <div className="min-h-screen">
      <Header
        search={filters.search}
        onSearch={(v) => patchFilters({ search: v })}
        onOpenChat={() => setChatOpen(true)}
        onOpenPalette={() => setPaletteOpen(true)}
        totalRetailers={retailerCount}
        view={view}
        onViewChange={setView}
        buildCount={buildCount}
        watchlistCount={watchlist.length}
        onOpenWatchlist={() => setWatchlistOpen(true)}
      />

      <main className="mx-auto max-w-[1320px] px-4 py-6 md:px-6">
        {view === "scraper" ? (
          <ScraperDashboard />
        ) : view === "build" ? (
          <BuildStudio
            build={build}
            onSetPart={setPart}
            onAddLine={addLine}
            onRemoveLine={removeLine}
            onSetQty={setQty}
            onSetLineRetailer={setLineRetailer}
            onRemove={removePart}
            onClear={clear}
            onShare={shareUrl}
            onOpenProduct={setSelected}
          />
        ) : (
          <>
            <CategoryTabs active={category} onSelect={onSelectCategory} />

            <div className="mt-6 flex items-center justify-between">
              <h1 className="text-lg font-bold">
                {category.label}
                <span className="ml-2 text-sm font-medium text-ink-4">
                  {loading ? "…" : `${total.toLocaleString()} products`}
                </span>
              </h1>
              <button
                className="btn-ghost !rounded-lg lg:hidden"
                onClick={() => setMobileFiltersOpen((o) => !o)}
              >
                <SlidersHorizontal className="h-4 w-4" /> Filters
              </button>
            </div>

            <div className="mt-4 grid gap-6 lg:grid-cols-[280px_1fr]">
              <div
                className={`${mobileFiltersOpen ? "block" : "hidden"} lg:block lg:sticky lg:top-24 lg:self-start`}
              >
                <FilterSidebar
                  category={category}
                  filters={filters}
                  onChange={patchFilters}
                  onReset={resetFilters}
                  resultCount={total}
                />
              </div>
              <div>
                <FilterChips filters={filters} onChange={patchFilters} onReset={resetFilters} />
                <ProductGrid
                  products={products}
                  loading={loading}
                  onOpen={setSelected}
                  onAddToBuild={addToBuild}
                />
                <Pagination page={page} totalPages={numTotalPages} onChange={setPage} />
              </div>
            </div>
          </>
        )}
      </main>

      {/* "Added to build" toast */}
      {addedToast && (
        <div className="fixed bottom-6 left-1/2 z-[70] -translate-x-1/2 animate-fade-up">
          <div className="flex items-center gap-2 rounded-xl border border-ok/40 bg-surface/90 px-4 py-3 text-sm font-medium text-ok shadow-xl backdrop-blur-lg">
            <Check className="h-4 w-4" />
            Added to build
          </div>
        </div>
      )}

      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        onSelect={setSelected}
      />

      <WatchlistPanel
        open={watchlistOpen}
        onClose={() => setWatchlistOpen(false)}
        items={watchlist}
        onRemove={removeWatched}
        onOpen={setSelected}
      />

      <ProductDrawer
        product={selected}
        bundleOnly={filters.bundleOnly}
        onClose={() => setSelected(null)}
        onAddToBuild={addToBuild}
        isWatched={selected ? isWatched(selected.id) : false}
        onToggleWatch={toggleWatch}
      />
      <Chatbot
        open={chatOpen}
        onClose={() => setChatOpen(false)}
        onOpenProduct={(p) => {
          setChatOpen(false);
          setSelected(p);
        }}
      />

      <footer className="mx-auto max-w-[1320px] px-6 py-10 text-center text-xs text-ink-4">
        DaamKoto · Prices in BDT, updated on every scrape · Bangladesh
      </footer>
    </div>
  );
}
