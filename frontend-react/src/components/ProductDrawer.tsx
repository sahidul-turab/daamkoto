import { lazy, Suspense, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  Bookmark,
  BookmarkCheck,
  Check,
  ExternalLink,
  LineChart as LineChartIcon,
  Plus,
  Trophy,
  X,
} from "lucide-react";
import { slotForCategory } from "../lib/buildConfig";
import { api } from "../api";
import { retailerColor } from "../config";
import { formatBDT, formatSpecValue, humanizeKey } from "../lib/format";
import type { ProductHistory, ProductSummary, SellerSpecs } from "../types";
import { PriceSpread } from "./PriceSpread";

// Lazy-loaded so recharts (~150 kB gzipped) stays out of the initial bundle
// and only downloads the first time a product drawer is opened.
const PriceHistoryChart = lazy(() =>
  import("./PriceHistoryChart").then((m) => ({ default: m.PriceHistoryChart })),
);

interface Props {
  product: ProductSummary | null;
  bundleOnly?: boolean;
  onClose: () => void;
  onAddToBuild?: (p: ProductSummary) => void;
  isWatched?: boolean;
  onToggleWatch?: (p: ProductSummary) => void;
}

export function ProductDrawer({ product, bundleOnly = false, onClose, onAddToBuild, isWatched, onToggleWatch }: Props) {
  const [history, setHistory] = useState<ProductHistory | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [sellerSpecs, setSellerSpecs] = useState<SellerSpecs | null>(null);

  useEffect(() => {
    if (!product) return;
    setHistory(null);
    setSellerSpecs(null);
    setLoadingHistory(true);
    api
      .history(product.id)
      .then(setHistory)
      .catch(() => setHistory(null))
      .finally(() => setLoadingHistory(false));
    api.sellerSpecs(product.id).then(setSellerSpecs).catch(() => null);
  }, [product]);

  // Close on Escape
  useEffect(() => {
    if (!product) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [product, onClose]);

  const listings = product
    ? [...product.listings]
        .filter((l) => !bundleOnly || l.pc_bundle_only)
        .sort((a, b) => {
          if (a.price_bdt == null) return 1;
          if (b.price_bdt == null) return -1;
          return a.price_bdt - b.price_bdt;
        })
    : [];

  const cheapest = product?.cheapest_price ?? null;
  const specEntries = product
    ? Object.entries(product.specs).filter(
        ([, v]) => v !== null && v !== "" && v !== false,
      )
    : [];

  return (
    <AnimatePresence>
      {product && (
        <>
          <motion.div
            className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.div
            className="fixed inset-y-0 right-0 z-50 flex w-full max-w-xl flex-col border-l border-line bg-surface shadow-2xl"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 360, damping: 38 }}
          >
            {/* Header */}
            <div className="flex items-start justify-between gap-4 border-b border-line p-5">
              <div>
                {product.brand && (
                  <span className="chip !border-brand/30 !bg-brand-strong/10 !text-brand">
                    {product.brand}
                  </span>
                )}
                <h2 className="mt-2 text-lg font-bold leading-snug">
                  {product.name}
                </h2>
                {product.model_number && (
                  <div className="mt-1 text-xs text-ink-4">
                    MPN: {product.model_number}
                  </div>
                )}
              </div>
              <div className="flex items-center gap-2">
                {onAddToBuild && slotForCategory(product.category) && (
                  <button
                    onClick={() => onAddToBuild(product)}
                    className="btn-brand !py-2 !text-xs"
                  >
                    <Plus className="h-3.5 w-3.5" /> Add to Build
                  </button>
                )}
                {onToggleWatch && (
                  <button
                    onClick={() => onToggleWatch(product)}
                    className={`btn-ghost !rounded-lg !p-2 ${isWatched ? "!border-brand/40 !text-brand" : ""}`}
                    aria-label={isWatched ? "Remove from watchlist" : "Add to watchlist"}
                    title={isWatched ? "Remove from watchlist" : "Save to watchlist"}
                  >
                    {isWatched
                      ? <BookmarkCheck className="h-4 w-4" />
                      : <Bookmark className="h-4 w-4" />
                    }
                  </button>
                )}
                <button
                  onClick={onClose}
                  className="btn-ghost !rounded-lg !p-2"
                  aria-label="Close"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-5">
              {/* Listings comparison */}
              <div className="mb-6">
                <div className="label">
                  Price comparison · {listings.length}{" "}
                  {listings.length === 1 ? "store" : "stores"}
                </div>
                {/* Signature spread overview */}
                <div className="mb-4 rounded-xl border border-line bg-surface-2/60 p-4">
                  <PriceSpread listings={product.listings} variant="detail" />
                </div>
                <div className="flex flex-col gap-2">
                  {listings.map((l, i) => {
                    const isCheapest =
                      l.price_bdt != null && l.price_bdt === cheapest && l.in_stock;
                    return (
                      <a
                        key={`${l.retailer}-${i}`}
                        href={l.product_url ?? "#"}
                        target="_blank"
                        rel="noreferrer"
                        className={`group flex items-center justify-between gap-3 rounded-xl border px-4 py-3 transition-all ${
                          isCheapest
                            ? "border-ok/40 bg-ok/5"
                            : "border-line bg-surface-2 hover:border-line-2"
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <span
                            className="h-8 w-1 rounded-full"
                            style={{ background: retailerColor(l.retailer) }}
                          />
                          <div>
                            <div className="flex items-center gap-2 text-sm font-semibold">
                              {l.retailer}
                              {isCheapest && (
                                <span className="inline-flex items-center gap-1 rounded-md bg-ok/15 px-1.5 py-0.5 text-[10px] font-bold uppercase text-ok">
                                  <Trophy className="h-3 w-3" /> Best
                                </span>
                              )}
                            </div>
                            <div className="mt-0.5 flex items-center gap-1 text-[11px]">
                              {l.in_stock ? (
                                <span className="flex items-center gap-1 text-ok">
                                  <Check className="h-3 w-3" /> In stock
                                </span>
                              ) : (
                                <span className="text-ink-4">
                                  {l.stock_status === "upcoming"
                                    ? "Upcoming"
                                    : "Out of stock"}
                                </span>
                              )}
                            </div>
                            {l.pc_bundle_only && (
                              <div className="mt-0.5 text-[10px] font-medium italic text-amber-600">
                                ⚠ PC bundle only
                              </div>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-base font-bold">
                            {formatBDT(l.price_bdt)}
                          </span>
                          <ExternalLink className="h-3.5 w-3.5 text-ink-4 transition-colors group-hover:text-brand" />
                        </div>
                      </a>
                    );
                  })}
                </div>
              </div>

              {/* Price history */}
              <div className="mb-6">
                <div className="label flex items-center gap-1.5">
                  <LineChartIcon className="h-3.5 w-3.5" /> Price history
                </div>
                {loadingHistory ? (
                  <div className="skeleton h-64 rounded-xl" />
                ) : (
                  <Suspense fallback={<div className="skeleton h-64 rounded-xl" />}>
                    <PriceHistoryChart history={history?.history ?? []} />
                  </Suspense>
                )}
              </div>

              {/* Seller-specs disagreement panel */}
              {sellerSpecs && Object.keys(sellerSpecs.differing).length > 0 && (
                <div className="mb-6">
                  <div className="label flex items-center gap-1.5">
                    <AlertTriangle className="h-3.5 w-3.5 text-warn" />
                    Retailers disagree on these specs
                  </div>
                  <div className="overflow-hidden rounded-xl border border-warn/30 bg-warn/5">
                    {Object.entries(sellerSpecs.differing).map(([key, vals], i) => (
                      <div
                        key={key}
                        className={`px-4 py-2.5 text-sm ${i % 2 ? "bg-surface-2/40" : ""}`}
                      >
                        <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-ink-4">
                          {humanizeKey(key)}
                        </div>
                        <div className="flex flex-wrap gap-x-4 gap-y-1">
                          {Object.entries(vals).map(([retailer, val]) => (
                            <span key={retailer} className="text-[12px]">
                              <span className="text-ink-3">{retailer}:</span>{" "}
                              <span className="font-medium text-ink">{val ?? "—"}</span>
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Specs */}
              {specEntries.length > 0 && (
                <div>
                  <div className="label">Specifications</div>
                  <div className="overflow-hidden rounded-xl border border-line">
                    {specEntries.map(([k, v], i) => (
                      <div
                        key={k}
                        className={`flex justify-between gap-4 px-4 py-2.5 text-sm ${
                          i % 2 ? "bg-surface-2" : "bg-surface"
                        }`}
                      >
                        <span className="text-ink-3">{humanizeKey(k)}</span>
                        <span className="text-right font-medium text-ink">
                          {formatSpecValue(v)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
