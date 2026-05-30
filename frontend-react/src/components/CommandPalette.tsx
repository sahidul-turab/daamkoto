import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { CornerDownLeft, Search, Store } from "lucide-react";
import { api } from "../api";
import { formatBDT } from "../lib/format";
import type { ProductSummary } from "../types";

interface Props {
  open: boolean;
  onClose: () => void;
  onSelect: (p: ProductSummary) => void;
}

/**
 * ⌘K / Ctrl-K command palette — instant fuzzy part search across the entire
 * catalogue with full keyboard navigation. Standard in world-class apps
 * (Linear, Vercel, Raycast); essentially unheard-of on local tech retail sites.
 */
export function CommandPalette({ open, onClose, onSelect }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ProductSummary[]>([]);
  const [active, setActive] = useState(0);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const reqId = useRef(0);

  useEffect(() => {
    if (open) {
      setQuery("");
      setResults([]);
      setActive(0);
      setTimeout(() => inputRef.current?.focus(), 40);
    }
  }, [open]);

  // Debounced search across all categories.
  useEffect(() => {
    if (!open) return;
    const q = query.trim();
    if (q.length < 2) {
      setResults([]);
      return;
    }
    const id = ++reqId.current;
    setLoading(true);
    const handle = setTimeout(() => {
      api
        .products({ search: q, in_stock_only: true, sort: "store_count_desc", limit: 8 })
        .then((res) => {
          if (id !== reqId.current) return;
          setResults(res.products);
          setActive(0);
        })
        .catch(() => id === reqId.current && setResults([]))
        .finally(() => id === reqId.current && setLoading(false));
    }, 180);
    return () => clearTimeout(handle);
  }, [query, open]);

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter" && results[active]) {
      e.preventDefault();
      onSelect(results[active]);
      onClose();
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-[60] flex items-start justify-center px-4 pt-[12vh]"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-md"
            onClick={onClose}
          />
          <motion.div
            className="glass relative w-full max-w-2xl overflow-hidden !bg-surface/90"
            initial={{ opacity: 0, scale: 0.97, y: -8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.98, y: -8 }}
            transition={{ type: "spring", stiffness: 420, damping: 34 }}
          >
            {/* Search input */}
            <div className="flex items-center gap-3 border-b border-line px-4">
              <Search className="h-5 w-5 shrink-0 text-ink-4" />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder="Search any part across all stores…"
                className="w-full bg-transparent py-4 text-base text-ink outline-none placeholder:text-ink-4"
              />
              <kbd className="hidden shrink-0 rounded-md border border-line bg-surface-2 px-2 py-1 text-[10px] font-medium text-ink-4 sm:block">
                ESC
              </kbd>
            </div>

            {/* Results */}
            <div className="max-h-[52vh] overflow-y-auto p-2">
              {query.trim().length < 2 ? (
                <div className="px-4 py-10 text-center text-sm text-ink-4">
                  Start typing — e.g. <span className="text-ink-3">“4070”</span>,{" "}
                  <span className="text-ink-3">“990 pro”</span>,{" "}
                  <span className="text-ink-3">“b650”</span>
                </div>
              ) : loading && results.length === 0 ? (
                <div className="space-y-2 p-2">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <div key={i} className="skeleton h-12 rounded-lg" />
                  ))}
                </div>
              ) : results.length === 0 ? (
                <div className="px-4 py-10 text-center text-sm text-ink-4">
                  No parts match “{query}”.
                </div>
              ) : (
                results.map((p, i) => (
                  <button
                    key={p.id}
                    onMouseEnter={() => setActive(i)}
                    onClick={() => {
                      onSelect(p);
                      onClose();
                    }}
                    className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors ${
                      i === active ? "bg-brand-strong/15" : "hover:bg-surface-2"
                    }`}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        {p.brand && (
                          <span className="text-[11px] font-bold uppercase tracking-wide text-brand">
                            {p.brand}
                          </span>
                        )}
                        <span className="text-[10px] text-ink-4">{p.category}</span>
                      </div>
                      <div className="line-clamp-1 text-sm font-medium text-ink">
                        {p.name}
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-3">
                      <span className="flex items-center gap-1 text-[11px] text-ink-4">
                        <Store className="h-3 w-3" />
                        {p.retailer_count}
                      </span>
                      <span className="text-sm font-bold tabular-nums text-ink">
                        {formatBDT(p.cheapest_price)}
                      </span>
                      {i === active && (
                        <CornerDownLeft className="h-3.5 w-3.5 text-brand" />
                      )}
                    </div>
                  </button>
                ))
              )}
            </div>

            {/* Footer hint */}
            <div className="flex items-center justify-between border-t border-line px-4 py-2 text-[10px] text-ink-4">
              <span className="flex items-center gap-3">
                <span className="flex items-center gap-1">
                  <kbd className="rounded border border-line px-1">↑</kbd>
                  <kbd className="rounded border border-line px-1">↓</kbd>
                  navigate
                </span>
                <span className="flex items-center gap-1">
                  <kbd className="rounded border border-line px-1">↵</kbd>
                  open
                </span>
              </span>
              <span>DaamKoto</span>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
