import { AnimatePresence, motion } from "framer-motion";
import { Bookmark, ExternalLink, Trash2, X } from "lucide-react";
import type { ProductSummary } from "../types";
import { retailerColor } from "../config";
import { formatBDT } from "../lib/format";

interface Props {
  open: boolean;
  onClose: () => void;
  items: ProductSummary[];
  onRemove: (id: number) => void;
  onOpen: (p: ProductSummary) => void;
}

export function WatchlistPanel({ open, onClose, items, onRemove, onOpen }: Props) {
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.div
            className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l border-line bg-surface shadow-2xl"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 360, damping: 38 }}
          >
            <div className="flex items-center justify-between border-b border-line p-5">
              <div className="flex items-center gap-2 text-sm font-bold">
                <Bookmark className="h-4 w-4 text-brand" />
                Watchlist
                {items.length > 0 && (
                  <span className="rounded-full bg-brand-strong/15 px-2 py-0.5 text-xs text-brand">
                    {items.length}
                  </span>
                )}
              </div>
              <button onClick={onClose} className="btn-ghost !rounded-lg !p-2">
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4">
              {items.length === 0 ? (
                <div className="flex flex-col items-center justify-center gap-3 py-20 text-center">
                  <div className="grid h-14 w-14 place-items-center rounded-2xl bg-surface-2">
                    <Bookmark className="h-7 w-7 text-ink-4" />
                  </div>
                  <div className="text-sm font-bold text-ink">Nothing saved yet</div>
                  <div className="text-xs text-ink-4">
                    Click the bookmark icon on any product to track it here.
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  {items.map((p) => (
                    <div
                      key={p.id}
                      className="glass flex items-start gap-3 p-3 transition-all hover:border-line-2"
                    >
                      <div
                        className="min-w-0 flex-1 cursor-pointer"
                        onClick={() => onOpen(p)}
                      >
                        {p.brand && (
                          <span className="text-[11px] font-bold uppercase tracking-wide text-brand">
                            {p.brand}
                          </span>
                        )}
                        <div className="line-clamp-2 text-[13px] font-medium text-ink hover:text-white">
                          {p.name}
                        </div>
                        <div className="mt-1.5 flex items-center gap-2">
                          <span className="text-base font-extrabold tabular-nums text-ink">
                            {formatBDT(p.cheapest_price)}
                          </span>
                          {p.cheapest_retailer && (
                            <span className="flex items-center gap-1 text-[11px] text-ink-3">
                              <span
                                className="h-1.5 w-1.5 rounded-full"
                                style={{ background: retailerColor(p.cheapest_retailer) }}
                              />
                              {p.cheapest_retailer}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="flex shrink-0 flex-col gap-2">
                        {p.listings[0]?.product_url && (
                          <a
                            href={p.listings[0].product_url}
                            target="_blank"
                            rel="noreferrer"
                            className="btn-ghost !rounded-lg !p-1.5"
                          >
                            <ExternalLink className="h-3.5 w-3.5" />
                          </a>
                        )}
                        <button
                          onClick={() => onRemove(p.id)}
                          className="rounded-lg p-1.5 text-ink-4 transition-colors hover:text-brand"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
