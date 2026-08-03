/**
 * DealsView — daily AI-curated price-drop feed.
 *
 * Shows the biggest recent price drops across all 15 retailers.
 * Each card opens the ProductDrawer for full details + all retailer prices.
 */
import { useEffect, useState } from "react";
import { ArrowDownCircle, Loader2, RefreshCw, TrendingDown } from "lucide-react";
import { api } from "../api";
import { formatBDT } from "../lib/format";
import { CATEGORIES } from "../config";
import type { Deal, ProductSummary } from "../types";

interface Props {
  onOpenProduct: (p: ProductSummary) => void;
}

export function DealsView({ onOpenProduct }: Props) {
  const [deals, setDeals] = useState<Deal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [category, setCategory] = useState<string>("");
  const [limit] = useState(30);

  async function fetchDeals() {
    setLoading(true);
    setError(null);
    try {
      const res = await api.deals({ category: category || undefined, limit });
      setDeals(res.deals);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load deals");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchDeals(); }, [category]);

  function openDeal(deal: Deal) {
    // Stub ProductSummary so the drawer fetches the real data by ID
    onOpenProduct({
      id: deal.id,
      name: deal.name,
      brand: deal.brand,
      match_key: "",
      model_number: null,
      category: deal.category,
      specs: deal.specs || {},
      cheapest_price: deal.current_price,
      cheapest_retailer: deal.retailer,
      retailer_count: 1,
      listings: [],
    });
  }

  return (
    <div className="w-full space-y-6">
      {/* Hero */}
      <div className="rounded-2xl border border-line bg-surface-2 px-6 py-6">
        <div className="flex items-center gap-3">
          <div className="grid h-12 w-12 place-items-center rounded-xl bg-green-500/10">
            <TrendingDown className="h-6 w-6 text-green-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold">Daily Deals</h1>
            <p className="text-sm text-ink-3">
              Biggest price drops across all 15 retailers — updated after every scrape
            </p>
          </div>
        </div>
      </div>

      {/* Filter bar */}
      <div className="flex items-center gap-3">
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="field max-w-[220px]"
        >
          <option value="">All categories</option>
          {CATEGORIES.map((c) => (
            <option key={c.db} value={c.db}>{c.label}</option>
          ))}
        </select>
        <button
          onClick={fetchDeals}
          className="btn-ghost !rounded-xl"
          disabled={loading}
          title="Refresh"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
        </button>
        <span className="text-sm text-ink-4">
          {deals.length > 0 && !loading ? `${deals.length} deals found` : ""}
        </span>
      </div>

      {/* Content */}
      {loading && (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="h-8 w-8 animate-spin text-ink-4" />
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-950/20 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {!loading && !error && deals.length === 0 && (
        <div className="rounded-xl border border-line bg-surface-2 px-6 py-12 text-center">
          <TrendingDown className="mx-auto mb-3 h-10 w-10 text-ink-4" />
          <p className="text-sm text-ink-3">No price drops found yet.</p>
          <p className="mt-1 text-xs text-ink-4">
            Run a scraper sweep to populate price history, then check back here.
          </p>
        </div>
      )}

      {!loading && deals.length > 0 && (
        <div className="deal-grid gap-3">
          {deals.map((deal, i) => (
            <button
              key={i}
              onClick={() => openDeal(deal)}
              className="group flex flex-col gap-3 rounded-xl border border-line bg-surface p-4 text-left transition-all hover:border-green-500/40 hover:shadow-lg"
            >
              {/* Category badge */}
              <div className="flex items-center justify-between">
                <span className="rounded-md border border-line bg-surface-2 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-ink-4">
                  {deal.category}
                </span>
                <div className="flex items-center gap-1 rounded-md bg-green-500/10 px-2 py-0.5">
                  <ArrowDownCircle className="h-3 w-3 text-green-400" />
                  <span className="text-[11px] font-bold text-green-400">
                    -{deal.drop_pct}%
                  </span>
                </div>
              </div>

              {/* Name */}
              <div className="line-clamp-2 text-sm font-medium text-ink leading-snug">
                {deal.name}
              </div>

              {/* Retailer */}
              <div className="text-xs text-ink-4">{deal.retailer}</div>

              {/* Price */}
              <div className="flex items-end gap-2">
                <span className="text-lg font-bold text-brand">
                  {formatBDT(deal.current_price)}
                </span>
                <span className="mb-0.5 text-xs text-ink-4 line-through">
                  {formatBDT(deal.prev_price)}
                </span>
                <span className="mb-0.5 ml-auto text-xs font-semibold text-green-400">
                  ↓ {formatBDT(deal.drop_bdt)} off
                </span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
