import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, Search, X } from "lucide-react";
import { CATEGORIES } from "../../config";
import { FilterSidebar } from "../FilterSidebar";
import { FilterChips } from "../FilterChips";
import { ProductGrid } from "../ProductGrid";
import { Pagination } from "../Pagination";
import { ProductDrawer } from "../ProductDrawer";
import { DEFAULT_FILTERS } from "../../lib/filterDefaults";
import { useProductSearch } from "../../lib/useProductSearch";
import { isMulti, slotDef, type SlotId } from "../../lib/buildConfig";
import { formatBDT } from "../../lib/format";
import { retailerColor } from "../../config";
import type { Filters, ProductSummary } from "../../types";
import { PAGE_SIZE } from "../../config";

interface Props {
  slotId: SlotId | null;
  onClose: () => void;
  // Called when user selects a product. For single slots the parent closes the overlay;
  // for multi slots the overlay stays open so more items can be added.
  onPick: (slotId: SlotId, product: ProductSummary) => void;
  // Lines already chosen for the open slot (for the multi-line strip).
  chosenLines?: { product: ProductSummary; qty: number }[];
  onRemoveLine?: (index: number) => void;
}

export function SlotPicker({ slotId, onClose, onPick, chosenLines = [], onRemoveLine }: Props) {
  const [filters, setFilters] = useState<Filters>({ ...DEFAULT_FILTERS });
  const [page, setPage] = useState(1);
  const [drawerProduct, setDrawerProduct] = useState<ProductSummary | null>(null);
  const [addedId, setAddedId] = useState<number | null>(null);

  const def = slotId ? slotDef(slotId) : null;
  const catDef = def ? CATEGORIES.find((c) => c.db === def.category) ?? null : null;
  const multi = slotId ? isMulti(slotId) : false;

  const { products, total, loading } = useProductSearch(
    def?.category ?? "",
    filters,
    page,
  );

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const patchFilters = useCallback((patch: Partial<Filters>) => {
    setFilters((f) => ({ ...f, ...patch }));
    setPage(1);
  }, []);

  const resetFilters = useCallback(() => {
    setFilters({ ...DEFAULT_FILTERS });
    setPage(1);
  }, []);

  const handlePick = useCallback(
    (p: ProductSummary) => {
      if (!slotId) return;
      onPick(slotId, p);
      // Flash the "added" indicator.
      setAddedId(p.id);
      setTimeout(() => setAddedId(null), 1200);
      // Single slots close immediately; multi slots stay open.
      if (!multi) onClose();
    },
    [slotId, onPick, multi, onClose],
  );

  // Escape key closes the picker.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    if (slotId) window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [slotId, onClose]);

  // Reset filter state when the slot changes.
  const [lastSlot, setLastSlot] = useState<SlotId | null>(null);
  if (slotId !== lastSlot) {
    setLastSlot(slotId);
    if (slotId !== null) {
      setFilters({ ...DEFAULT_FILTERS });
      setPage(1);
    }
  }

  return (
    <>
      <AnimatePresence>
        {slotId && def && catDef && (
          <motion.div
            className="fixed inset-0 z-[55] flex flex-col"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
          >
            {/* Backdrop */}
            <div className="absolute inset-0 bg-black/70 backdrop-blur-md" onClick={onClose} />

            {/* Panel */}
            <motion.div
              className="relative mx-auto mt-[3vh] flex w-full max-w-[1200px] flex-col overflow-hidden rounded-2xl border border-line bg-surface shadow-2xl"
              style={{ maxHeight: "93vh" }}
              initial={{ opacity: 0, scale: 0.97, y: -10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.98, y: -8 }}
              transition={{ type: "spring", stiffness: 380, damping: 32 }}
              onClick={(e) => e.stopPropagation()}
            >
              {/* Header */}
              <div className="flex shrink-0 items-center justify-between border-b border-line px-5 py-3.5">
                <div>
                  <span className="text-sm font-bold text-ink">
                    Choose{" "}
                    <span className="text-brand">{def.label}</span>
                  </span>
                  {multi && (
                    <span className="ml-2 text-[11px] text-ink-4">
                      (add multiple — slot stays open)
                    </span>
                  )}
                </div>
                <button onClick={onClose} className="btn-ghost !rounded-lg !p-2">
                  <X className="h-4 w-4" />
                </button>
              </div>

              {/* Search bar */}
              <div className="shrink-0 border-b border-line px-4 py-3">
                <div className="flex items-center gap-3 rounded-xl border border-line bg-surface-2 px-3 py-2.5">
                  <Search className="h-4 w-4 shrink-0 text-ink-4" />
                  <input
                    autoFocus
                    value={filters.search}
                    onChange={(e) => patchFilters({ search: e.target.value })}
                    placeholder={`Search ${def?.label.toLowerCase() ?? ""}…`}
                    className="w-full bg-transparent text-sm text-ink outline-none placeholder:text-ink-4"
                  />
                  {filters.search && (
                    <button
                      onClick={() => patchFilters({ search: "" })}
                      className="shrink-0 text-ink-4 hover:text-ink"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              </div>

              {/* Multi-slot chosen lines strip */}
              {multi && chosenLines.length > 0 && (
                <div className="shrink-0 border-b border-line bg-surface-2/60 px-5 py-2.5">
                  <div className="mb-1 text-[11px] uppercase tracking-wide text-ink-4">
                    Added to build
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {chosenLines.map((l, i) => (
                      <div
                        key={i}
                        className="flex items-center gap-2 rounded-lg border border-line bg-surface px-2.5 py-1.5 text-xs"
                      >
                        <span
                          className="h-2 w-2 shrink-0 rounded-full"
                          style={{ background: retailerColor(l.product.cheapest_retailer ?? "") }}
                        />
                        <span className="max-w-[180px] truncate text-ink">{l.product.name}</span>
                        {l.qty > 1 && (
                          <span className="font-bold text-brand">×{l.qty}</span>
                        )}
                        <span className="text-ink-4">{formatBDT(l.product.cheapest_price)}</span>
                        {onRemoveLine && (
                          <button
                            onClick={() => onRemoveLine(i)}
                            className="ml-1 text-ink-4 hover:text-brand"
                          >
                            <X className="h-3 w-3" />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Body: sidebar + grid */}
              <div className="flex min-h-0 flex-1 overflow-hidden">
                {/* Sidebar */}
                <div className="hidden w-[260px] shrink-0 overflow-y-auto border-r border-line lg:block">
                  <FilterSidebar
                    category={catDef}
                    filters={filters}
                    onChange={patchFilters}
                    onReset={resetFilters}
                    resultCount={total}
                  />
                </div>

                {/* Main content */}
                <div className="flex flex-1 flex-col overflow-hidden">
                  {/* FilterChips */}
                  <div className="shrink-0 border-b border-line px-4 py-2">
                    <FilterChips
                      filters={filters}
                      onChange={patchFilters}
                      onReset={resetFilters}
                    />
                  </div>

                  {/* Product grid scroll area */}
                  <div className="relative flex-1 overflow-y-auto px-4 py-4">
                    <ProductGrid
                      products={products}
                      loading={loading}
                      onOpen={setDrawerProduct}
                      onAddToBuild={handlePick}
                      showAddToBuild={true}
                    />
                    {/* "Added" flash for multi slots */}
                    <AnimatePresence>
                      {addedId !== null && (
                        <motion.div
                          className="pointer-events-none absolute bottom-4 left-1/2 -translate-x-1/2"
                          initial={{ opacity: 0, y: 8 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: 4 }}
                        >
                          <div className="flex items-center gap-2 rounded-xl border border-ok/40 bg-surface/90 px-4 py-2.5 text-sm font-medium text-ok shadow-xl backdrop-blur-lg">
                            <Check className="h-4 w-4" />
                            Added to build
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>

                  {/* Pagination */}
                  {totalPages > 1 && (
                    <div className="shrink-0 border-t border-line px-4 py-3">
                      <Pagination page={page} totalPages={totalPages} onChange={setPage} />
                    </div>
                  )}
                </div>
              </div>

              {/* Footer for multi: done button */}
              {multi && (
                <div className="shrink-0 border-t border-line px-5 py-3 text-right">
                  <button onClick={onClose} className="btn-brand">
                    <Check className="h-4 w-4" />
                    Done
                  </button>
                </div>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Product drawer opened from inside the picker */}
      <ProductDrawer
        product={drawerProduct}
        bundleOnly={filters.bundleOnly}
        onClose={() => setDrawerProduct(null)}
        onAddToBuild={handlePick}
        isWatched={false}
        onToggleWatch={() => void 0}
      />
    </>
  );
}
