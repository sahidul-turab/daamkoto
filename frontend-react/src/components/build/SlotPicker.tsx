import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, PackageSearch, Search, SlidersHorizontal, X } from "lucide-react";
import { CATEGORIES, PAGE_SIZE, retailerColor } from "../../config";
import { FilterSidebar } from "../FilterSidebar";
import { FilterChips } from "../FilterChips";
import { Pagination } from "../Pagination";
import { ProductDrawer } from "../ProductDrawer";
import { BuildProductCard } from "./BuildProductCard";
import { DEFAULT_FILTERS } from "../../lib/filterDefaults";
import { useProductSearch } from "../../lib/useProductSearch";
import { isMulti, MAX_QTY, slotDef, type SlotId } from "../../lib/buildConfig";
import { formatBDT } from "../../lib/format";
import type { Filters, ProductSummary } from "../../types";

interface Props {
  slotId: SlotId | null;
  onClose: () => void;
  onPick: (slotId: SlotId, product: ProductSummary) => void;
  chosenLines?: { product: ProductSummary; qty: number }[];
  onRemoveLine?: (index: number) => void;
}

function PickerSkeletons() {
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: 9 }).map((_, index) => (
        <div key={index} className="rounded-2xl border border-line bg-surface-2/55 p-3">
          <div className="flex gap-3">
            <div className="skeleton h-[76px] w-[76px] shrink-0 rounded-xl" />
            <div className="flex-1 space-y-2 pt-1">
              <div className="skeleton h-3 w-16 rounded" />
              <div className="skeleton h-3 w-full rounded" />
              <div className="skeleton h-3 w-3/4 rounded" />
            </div>
          </div>
          <div className="skeleton mt-3 h-9 w-full rounded-xl" />
        </div>
      ))}
    </div>
  );
}

export function SlotPicker({ slotId, onClose, onPick, chosenLines = [], onRemoveLine }: Props) {
  const [session, setSession] = useState<{
    slotId: SlotId | null;
    filters: Filters;
    page: number;
  }>({ slotId: null, filters: { ...DEFAULT_FILTERS }, page: 1 });
  const [drawerProduct, setDrawerProduct] = useState<ProductSummary | null>(null);
  const [addedId, setAddedId] = useState<number | null>(null);
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);

  const def = slotId ? slotDef(slotId) : null;
  const catDef = def ? CATEGORIES.find((category) => category.db === def.category) ?? null : null;
  const multi = slotId ? isMulti(slotId) : false;
  const maxLines = ((def as Record<string, unknown> | null)?.maxLines as number | undefined) ?? 1;
  const slotFull = multi && chosenLines.length >= maxLines;
  const currentSession =
    session.slotId === slotId
      ? session
      : { slotId, filters: { ...DEFAULT_FILTERS }, page: 1 };
  const filters = currentSession.filters;
  const page = currentSession.page;

  const { products, total, loading } = useProductSearch(def?.category ?? "", filters, page);
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const patchFilters = useCallback((patch: Partial<Filters>) => {
    setSession((current) => {
      const baseFilters = current.slotId === slotId ? current.filters : { ...DEFAULT_FILTERS };
      return { slotId, filters: { ...baseFilters, ...patch }, page: 1 };
    });
  }, [slotId]);

  const resetFilters = useCallback(() => {
    setSession({ slotId, filters: { ...DEFAULT_FILTERS }, page: 1 });
  }, [slotId]);

  const setPage = useCallback((nextPage: number) => {
    setSession((current) => ({
      slotId,
      filters: current.slotId === slotId ? current.filters : { ...DEFAULT_FILTERS },
      page: nextPage,
    }));
  }, [slotId]);

  const handlePick = useCallback(
    (product: ProductSummary) => {
      if (!slotId) return;
      onPick(slotId, product);
      setDrawerProduct(null);
      setAddedId(product.id);
      window.setTimeout(() => setAddedId(null), 1200);
      if (!multi) onClose();
    },
    [slotId, onPick, multi, onClose],
  );

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        if (drawerProduct) return;
        if (mobileFiltersOpen) setMobileFiltersOpen(false);
        else onClose();
      }
    };
    if (slotId) window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [slotId, onClose, mobileFiltersOpen, drawerProduct]);

  // Each slot is a new shopping task; do not carry unrelated filters across it.
  useEffect(() => {
    setSession({ slotId, filters: { ...DEFAULT_FILTERS }, page: 1 });
    if (slotId !== null) {
      setDrawerProduct(null);
      setMobileFiltersOpen(false);
    }
  }, [slotId]);

  const drawerLine = drawerProduct
    ? chosenLines.find((line) => line.product.id === drawerProduct.id)
    : undefined;
  const canAddDrawerProduct =
    !!drawerProduct &&
    (!multi || (drawerLine ? drawerLine.qty < MAX_QTY : !slotFull));

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
            <div className="absolute inset-0 bg-black/70 backdrop-blur-md" onClick={onClose} />

            <motion.div
              role="dialog"
              aria-modal="true"
              aria-label={`Choose ${def.label}`}
              className="relative mx-auto mt-[2vh] flex w-[calc(100%-1rem)] max-w-[1600px] flex-col overflow-hidden rounded-2xl border border-line bg-surface shadow-2xl sm:w-[calc(100%-2rem)]"
              style={{ maxHeight: "96vh" }}
              initial={{ opacity: 0, scale: 0.97, y: -10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.98, y: -8 }}
              transition={{ type: "spring", stiffness: 380, damping: 32 }}
              onClick={(event) => event.stopPropagation()}
            >
              <div className="flex shrink-0 items-center justify-between gap-3 border-b border-line px-4 py-3 sm:px-5 sm:py-3.5">
                <div className="min-w-0">
                  <div className="truncate text-sm font-bold text-ink">
                    Choose <span className="text-brand">{def.label}</span>
                  </div>
                  <div className="mt-0.5 truncate text-[10px] text-ink-4">
                    {multi ? `Add up to ${maxLines} different products` : "Compare prices, then select one part"}
                  </div>
                </div>
                <button type="button" onClick={onClose} className="btn-ghost !rounded-lg !p-2" aria-label="Close part picker">
                  <X className="h-4 w-4" />
                </button>
              </div>

              <div className="shrink-0 border-b border-line px-3 py-3 sm:px-4">
                <div className="flex gap-2">
                  <div className="flex min-w-0 flex-1 items-center gap-3 rounded-xl border border-line bg-surface-2 px-3 py-2.5">
                    <Search className="h-4 w-4 shrink-0 text-ink-4" />
                    <input
                      autoFocus
                      value={filters.search}
                      onChange={(event) => patchFilters({ search: event.target.value })}
                      placeholder={`Search ${def.label.toLowerCase()}…`}
                      className="min-w-0 flex-1 bg-transparent text-sm text-ink outline-none placeholder:text-ink-4"
                    />
                    {filters.search && (
                      <button type="button" onClick={() => patchFilters({ search: "" })} className="shrink-0 text-ink-4 hover:text-ink" aria-label="Clear search">
                        <X className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => setMobileFiltersOpen(true)}
                    className="btn-ghost !px-3 !py-2.5 lg:hidden"
                    aria-label="Filters"
                  >
                    <SlidersHorizontal className="h-4 w-4" />
                    <span className="hidden sm:inline">Filters</span>
                  </button>
                </div>
              </div>

              {multi && chosenLines.length > 0 && (
                <div className="shrink-0 border-b border-line bg-surface-2/60 px-4 py-2.5 sm:px-5">
                  <div className="mb-1.5 flex items-center justify-between gap-3 text-[10px] uppercase tracking-wide text-ink-4">
                    <span>In this slot</span>
                    <span>{chosenLines.length}/{maxLines} products</span>
                  </div>
                  <div className="no-scrollbar flex gap-2 overflow-x-auto pb-1">
                    {chosenLines.map((line, index) => (
                      <div key={`${line.product.id}-${index}`} className="flex max-w-[270px] shrink-0 items-center gap-2 rounded-lg border border-line bg-surface px-2.5 py-1.5 text-xs">
                        <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: retailerColor(line.product.cheapest_retailer ?? "") }} />
                        <span className="max-w-[140px] truncate text-ink">{line.product.name}</span>
                        {line.qty > 1 && <span className="font-bold text-brand">×{line.qty}</span>}
                        <span className="shrink-0 text-ink-4">{formatBDT(line.product.cheapest_price)}</span>
                        {onRemoveLine && (
                          <button type="button" onClick={() => onRemoveLine(index)} className="ml-1 shrink-0 text-ink-4 hover:text-brand" aria-label={`Remove ${line.product.name}`}>
                            <X className="h-3 w-3" />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="relative flex min-h-0 flex-1 overflow-hidden">
                {mobileFiltersOpen && (
                  <div className="absolute inset-0 z-20 overflow-y-auto bg-surface p-3 lg:hidden">
                    <FilterSidebar
                      category={catDef}
                      filters={filters}
                      onChange={patchFilters}
                      onReset={resetFilters}
                      resultCount={total}
                      onClose={() => setMobileFiltersOpen(false)}
                    />
                    <button type="button" onClick={() => setMobileFiltersOpen(false)} className="btn-brand sticky bottom-3 mt-3 w-full">
                      Show {total.toLocaleString()} products
                    </button>
                  </div>
                )}

                <div className="hidden w-[270px] shrink-0 overflow-y-auto border-r border-line lg:block xl:w-[290px]">
                  <FilterSidebar category={catDef} filters={filters} onChange={patchFilters} onReset={resetFilters} resultCount={total} />
                </div>

                <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
                  <div className="shrink-0 border-b border-line px-3 py-2 sm:px-4">
                    <FilterChips filters={filters} onChange={patchFilters} onReset={resetFilters} />
                  </div>

                  <div className="relative flex-1 overflow-y-auto px-3 py-3 sm:px-4 sm:py-4">
                    {loading ? (
                      <PickerSkeletons />
                    ) : products.length === 0 ? (
                      <div className="grid min-h-72 place-items-center rounded-2xl border border-dashed border-line px-6 text-center">
                        <div>
                          <PackageSearch className="mx-auto h-7 w-7 text-ink-4" />
                          <div className="mt-3 text-sm font-bold text-ink">No products match</div>
                          <p className="mt-1 text-xs text-ink-4">Try removing a filter or widening the price range.</p>
                          <button type="button" onClick={resetFilters} className="btn-ghost mt-4 !py-2">Reset filters</button>
                        </div>
                      </div>
                    ) : (
                      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                        {products.map((product) => {
                          const selectedLine = chosenLines.find((line) => line.product.id === product.id);
                          const selected = !!selectedLine;
                          const atMaxQuantity = !!selectedLine && selectedLine.qty >= MAX_QTY;
                          return (
                            <BuildProductCard
                              key={product.id}
                              product={product}
                              selected={selected}
                              multi={multi}
                              disabled={(slotFull && !selected) || atMaxQuantity}
                              atMaxQuantity={atMaxQuantity}
                              onOpen={() => setDrawerProduct(product)}
                              onSelect={() => handlePick(product)}
                            />
                          );
                        })}
                      </div>
                    )}

                    <AnimatePresence>
                      {addedId !== null && (
                        <motion.div
                          className="pointer-events-none sticky bottom-3 z-10 mx-auto mt-3 w-fit"
                          initial={{ opacity: 0, y: 8 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: 4 }}
                        >
                          <div
                            className="flex items-center gap-2 rounded-xl border border-ok/40 bg-surface/95 px-4 py-2.5 text-sm font-medium text-ok shadow-xl backdrop-blur-lg"
                            role="status"
                            aria-live="polite"
                          >
                            <Check className="h-4 w-4" /> Added to build
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>

                  {totalPages > 1 && (
                    <div className="shrink-0 border-t border-line px-3 py-2.5 sm:px-4 sm:py-3">
                      <Pagination page={page} totalPages={totalPages} onChange={setPage} />
                    </div>
                  )}
                </div>
              </div>

              {multi && (
                <div className="shrink-0 border-t border-line px-4 py-2.5 text-right sm:px-5 sm:py-3">
                  <button type="button" onClick={onClose} className="btn-brand !py-2">
                    <Check className="h-4 w-4" /> Done adding {def.label.toLowerCase()}
                  </button>
                </div>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <ProductDrawer
        product={drawerProduct}
        bundleOnly={filters.bundleOnly}
        onClose={() => setDrawerProduct(null)}
        onAddToBuild={canAddDrawerProduct ? handlePick : undefined}
        isWatched={false}
        layer="picker"
      />
    </>
  );
}
