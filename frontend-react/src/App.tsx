import { Suspense, lazy, useCallback, useEffect, useState } from "react";
import { api } from "./api";
import type { ProductSummary } from "./types";
import { useProductSearch } from "./lib/useProductSearch";
import { Header, type View } from "./components/Header";
import { CategoryTabs } from "./components/CategoryTabs";
import { FilterSidebar } from "./components/FilterSidebar";
import { FilterChips } from "./components/FilterChips";
import { ProductGrid } from "./components/ProductGrid";
import { Pagination } from "./components/Pagination";
import { HomeView } from "./components/HomeView";
import { AdminLogin } from "./components/AdminLogin";

// Everything below is off the browse view's first paint: three other views the
// user has to navigate to, and four overlays that only exist once opened. They
// are also, between them, the only remaining consumers of framer-motion — so
// splitting them here is what keeps that library (40 kB gzipped) out of the
// bundle a first-time visitor downloads before seeing a single price.
const ProductDrawer   = lazy(() => import("./components/ProductDrawer").then((m) => ({ default: m.ProductDrawer })));
const WatchlistPanel  = lazy(() => import("./components/WatchlistPanel").then((m) => ({ default: m.WatchlistPanel })));
const Chatbot         = lazy(() => import("./components/Chatbot").then((m) => ({ default: m.Chatbot })));
const CommandPalette  = lazy(() => import("./components/CommandPalette").then((m) => ({ default: m.CommandPalette })));
const DealsView       = lazy(() => import("./components/DealsView").then((m) => ({ default: m.DealsView })));
const BuildStudio     = lazy(() => import("./components/build/BuildStudio").then((m) => ({ default: m.BuildStudio })));
const ScraperDashboard = lazy(() => import("./components/ScraperDashboard").then((m) => ({ default: m.ScraperDashboard })));
import { useBuild } from "./lib/useBuild";
import { useWatchlist } from "./lib/useWatchlist";
import { useUrlFilters } from "./lib/useUrlFilters";
import { prefetchAllCategories } from "./lib/prefetch";
import { slotForCategory } from "./lib/buildConfig";
import { useAdminSession } from "./lib/useAdminSession";
import { CATEGORIES } from "./config";
import { Check, SlidersHorizontal } from "lucide-react";

/** Latches to true the first time `active` is true, and stays there. */
function useLatch(active: boolean): boolean {
  const [everActive, setEverActive] = useState(active);
  useEffect(() => {
    if (active) setEverActive(true);
  }, [active]);
  return everActive || active;
}

/** Placeholder while a lazily-loaded view's chunk arrives. */
function ViewLoading() {
  return (
    <div className="product-grid gap-4">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="skeleton h-40 rounded-2xl" />
      ))}
    </div>
  );
}

function viewFromLocation(): View {
  const hash = window.location.hash.toLowerCase();
  const params = new URLSearchParams(window.location.search);
  const browseKeys = new Set(["cat", "q", "brand", "min", "max", "stock", "bundle", "sort", "page"]);
  const hasBrowseQuery = [...params.keys()].some(
    (key) => browseKeys.has(key) || key.startsWith("spec_"),
  );
  if (hash.startsWith("#build")) return "build";
  if (hash.startsWith("#deals")) return "deals";
  if (hash.startsWith("#admin") || hash.startsWith("#scraper")) return "admin";
  if (hash.startsWith("#browse") || hasBrowseQuery) return "browse";
  return "home";
}

export default function App() {
  const {
    category, filters, page, setPage,
    onSelectCategory, patchFilters, resetFilters, totalPages,
  } = useUrlFilters();
  const admin = useAdminSession();

  const [selected, setSelected] = useState<ProductSummary | null>(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [watchlistOpen, setWatchlistOpen] = useState(false);
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);
  const [retailerCount, setRetailerCount] = useState(0);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [view, setView] = useState<View>(viewFromLocation);
  const [addedToast, setAddedToast] = useState<string | null>(null);

  // An overlay's chunk is only worth downloading once the user has actually
  // reached for it. These latch on first open and never go back to false, so
  // the component stays mounted and keeps its close animation afterwards.
  const drawerEverOpened    = useLatch(selected !== null);
  const chatEverOpened      = useLatch(chatOpen);
  const paletteEverOpened   = useLatch(paletteOpen);
  const watchlistEverOpened = useLatch(watchlistOpen);

  const { build, setPart, addLine, setQty, removeLine, setLineRetailer, removePart, clear, shareUrl, count: buildCount } = useBuild();
  const { items: watchlist, isWatched, toggle: toggleWatch, remove: removeWatched } = useWatchlist();

  const navigateView = useCallback((next: View) => {
    const hash = next === "home" ? "" : `#${next}`;
    const search = next === "home" ? "" : window.location.search;
    window.history.pushState(null, "", `${window.location.pathname}${search}${hash}`);
    setView(next);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  const goHome = useCallback(() => {
    resetFilters();
    onSelectCategory(CATEGORIES[0]);
    navigateView("home");
  }, [navigateView, onSelectCategory, resetFilters]);

  const browseCategory = useCallback((nextCategory: (typeof CATEGORIES)[number]) => {
    onSelectCategory(nextCategory);
    patchFilters({ search: "" });
    navigateView("browse");
  }, [navigateView, onSelectCategory, patchFilters]);

  useEffect(() => {
    const syncView = () => setView(viewFromLocation());
    window.addEventListener("popstate", syncView);
    window.addEventListener("hashchange", syncView);
    return () => {
      window.removeEventListener("popstate", syncView);
      window.removeEventListener("hashchange", syncView);
    };
  }, []);

  // Once: how many retailers exist (for the header subtitle).
  useEffect(() => {
    api
      .retailers()
      .then((r) => setRetailerCount(Array.isArray(r) ? r.length : 0))
      .catch(() => void 0);
  }, []);

  // Warm the other category tabs while the browser is idle, so switching tabs
  // costs a render rather than a round trip. Only in the browse view — there is
  // no point speculating on data the user is not about to look at.
  useEffect(() => {
    if (view !== "browse") return;
    return prefetchAllCategories(category.db);
  }, [view, category.db]);

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
    navigateView("build");
    setAddedToast(p.name);
    setTimeout(() => setAddedToast(null), 2200);
  }, [setPart, addLine, navigateView]);

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

  const { products, total, loading } = useProductSearch(
    view === "browse" ? category.db : "",
    filters,
    page,
    view === "browse",
  );
  const numTotalPages = totalPages(total);

  return (
    <div className="min-h-screen">
      <Header
        onGoHome={goHome}
        onOpenChat={() => setChatOpen(true)}
        onOpenPalette={() => setPaletteOpen(true)}
        totalRetailers={retailerCount}
        view={view}
        onViewChange={navigateView}
        buildCount={buildCount}
        watchlistCount={watchlist.length}
        onOpenWatchlist={() => setWatchlistOpen(true)}
        isAdmin={admin.authenticated}
        onLogout={() => {
          admin.logout();
          if (view === "admin") navigateView("home");
        }}
      />

      <main className="app-shell py-6">
        {view === "admin" ? (
          admin.authenticated && admin.token ? (
            <Suspense fallback={<ViewLoading />}>
              <ScraperDashboard
                adminToken={admin.token}
                onUnauthorized={admin.invalidate}
              />
            </Suspense>
          ) : (
            <AdminLogin checking={admin.checking} onLogin={admin.login} />
          )
        ) : view === "home" ? (
          <HomeView
            retailerCount={retailerCount}
            isAdmin={admin.authenticated}
            onSearch={() => setPaletteOpen(true)}
            onBrowseCategory={browseCategory}
            onOpenProduct={setSelected}
            onOpenBuild={() => navigateView("build")}
            onOpenDeals={() => navigateView("deals")}
          />
        ) : view === "deals" ? (
          <Suspense fallback={<ViewLoading />}>
            <DealsView onOpenProduct={setSelected} />
          </Suspense>
        ) : view === "build" ? (
          <Suspense fallback={<ViewLoading />}>
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
          </Suspense>
        ) : (
          <>
            <CategoryTabs active={category} onSelect={browseCategory} />

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

            <div className="browse-layout mt-4">
              <div
                className={`${mobileFiltersOpen ? "block" : "hidden"} lg:sticky lg:top-24 lg:block lg:max-h-[calc(100dvh-7rem)] lg:self-start lg:overflow-y-auto lg:overscroll-contain lg:pr-1`}
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
                  showOperationalMeta={admin.authenticated}
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

      {/* Overlays mount on first open and then stay mounted, so their chunk is
          never fetched for a visitor who only browses — but once loaded, the
          open/close exit animations still have a component to run against. */}
      {paletteEverOpened && (
        <Suspense fallback={null}>
          <CommandPalette
            open={paletteOpen}
            onClose={() => setPaletteOpen(false)}
            onSelect={setSelected}
          />
        </Suspense>
      )}

      {watchlistEverOpened && (
        <Suspense fallback={null}>
          <WatchlistPanel
            open={watchlistOpen}
            onClose={() => setWatchlistOpen(false)}
            items={watchlist}
            onRemove={removeWatched}
            onOpen={setSelected}
          />
        </Suspense>
      )}

      {drawerEverOpened && (
        <Suspense fallback={null}>
          <ProductDrawer
            product={selected}
            bundleOnly={filters.bundleOnly}
            onClose={() => setSelected(null)}
            onAddToBuild={addToBuild}
            isWatched={selected ? isWatched(selected.id) : false}
            onToggleWatch={toggleWatch}
            isAdmin={admin.authenticated}
          />
        </Suspense>
      )}

      {chatEverOpened && (
      <Suspense fallback={null}>
      <Chatbot
        open={chatOpen}
        onClose={() => setChatOpen(false)}
        onOpenProduct={(p) => {
          setChatOpen(false);
          setSelected(p);
        }}
        onAddToBuild={(_productId, _slot) => {
          // Agent requested add-to-build — switch to build view.
          // Full integration (auto-add by ID) is a future enhancement.
          navigateView("build");
        }}
        onApplyFilters={(cat, specs) => {
          // Agent applied filters — switch to browse with those filters
          const found = CATEGORIES.find((c) => c.db === cat || c.label === cat);
          if (found) onSelectCategory(found);
          if (Object.keys(specs).length > 0) patchFilters({ specs });
          setChatOpen(false);
          navigateView("browse");
        }}
        onOpenDeals={() => {
          setChatOpen(false);
          navigateView("deals");
        }}
        context={{
          category: category.db || null,
          filters: filters as unknown as Record<string, unknown>,
          build_slots: Object.fromEntries(
            Object.entries(build).flatMap(([slot, lines]) =>
              lines && lines.length > 0 ? [[slot, lines[0].product.id]] : []
            )
          ),
        }}
      />
      </Suspense>
      )}

      <footer className="app-shell flex flex-wrap items-center justify-center gap-x-3 gap-y-2 py-10 text-center text-xs text-ink-4">
        <span>DaamKoto · Prices in BDT · Bangladesh</span>
        <span aria-hidden="true">·</span>
        <button className="transition-colors hover:text-brand" onClick={() => navigateView("admin")}>
          {admin.authenticated ? "Admin dashboard" : "Owner access"}
        </button>
      </footer>
    </div>
  );
}
