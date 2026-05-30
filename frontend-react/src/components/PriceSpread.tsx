import { useMemo } from "react";
import type { Listing } from "../types";
import { retailerColor } from "../config";
import { formatBDT } from "../lib/format";

interface Props {
  listings: Listing[];
  variant?: "card" | "detail";
}

interface Dot {
  retailer: string;
  price: number;
  pct: number; // 0..100 position along the rail
  isBest: boolean;
}

/**
 * The signature visual of the whole app: a horizontal "market spread" rail that
 * plots every retailer's price between the cheapest (left, glowing) and the
 * dearest (right). One glance tells you how much the price varies and how good
 * the best deal really is — something a plain price label can never show.
 */
export function PriceSpread({ listings, variant = "card" }: Props) {
  const data = useMemo(() => {
    const priced = listings
      .filter((l) => l.in_stock && l.price_bdt != null)
      .map((l) => ({ retailer: l.retailer, price: l.price_bdt as number }));
    if (priced.length === 0) return null;

    const min = Math.min(...priced.map((p) => p.price));
    const max = Math.max(...priced.map((p) => p.price));
    const span = max - min;

    // Collapse duplicate retailers to their cheapest listing, then de-dupe dots
    // that would land on the exact same pixel by keeping the cheapest there.
    const dots: Dot[] = priced
      .map((p) => ({
        retailer: p.retailer,
        price: p.price,
        pct: span === 0 ? 50 : ((p.price - min) / span) * 100,
        isBest: p.price === min,
      }))
      .sort((a, b) => a.price - b.price);

    return { min, max, span, count: priced.length, dots };
  }, [listings]);

  if (!data) return null;

  const { min, max, span, count, dots } = data;
  const detail = variant === "detail";

  // Single retailer — no spread to show, just a clean "only here" note.
  if (count === 1 || span === 0) {
    return (
      <div className="flex items-center gap-2 text-[11px] text-ink-4">
        <span className="h-1.5 w-1.5 rounded-full bg-brand shadow-[0_0_8px_rgba(244,63,75,0.9)]" />
        {count === 1 ? "Only at " : "Same price at "}
        <span className="font-medium text-ink-3">{dots[0].retailer}</span>
        {count > 1 && ` · ${count} stores`}
      </div>
    );
  }

  return (
    <div className={detail ? "space-y-3" : "space-y-2"}>
      {/* The rail */}
      <div className="relative h-1.5 w-full rounded-full bg-line-2">
        {/* gradient fill from best → worst */}
        <div className="absolute inset-0 rounded-full bg-gradient-to-r from-ok/60 via-warn/40 to-brand/50" />
        {dots.map((d, i) => (
          <div
            key={`${d.retailer}-${i}`}
            className="group/dot absolute top-1/2 -translate-x-1/2 -translate-y-1/2"
            style={{ left: `${d.pct}%` }}
          >
            <span
              className={`block rounded-full ring-2 ring-surface transition-transform group-hover/dot:scale-150 ${
                d.isBest ? "h-3 w-3" : "h-2 w-2"
              }`}
              style={{
                background: d.isBest ? "#2dd4a7" : retailerColor(d.retailer),
                boxShadow: d.isBest
                  ? "0 0 10px rgba(45,212,167,0.9)"
                  : undefined,
              }}
            />
            {/* tooltip on hover */}
            <span className="pointer-events-none absolute bottom-full left-1/2 mb-1.5 -translate-x-1/2 whitespace-nowrap rounded-md border border-line bg-elevated px-2 py-1 text-[10px] font-medium text-ink opacity-0 transition-opacity group-hover/dot:opacity-100">
              {d.retailer} · {formatBDT(d.price)}
            </span>
          </div>
        ))}
      </div>

      {/* End labels */}
      <div className="flex items-center justify-between text-[10px] font-medium">
        <span className="flex items-center gap-1 text-ok">
          <span className="uppercase tracking-wide">low</span>
          {formatBDT(min)}
        </span>
        <span className="text-ink-4">
          {count} {count === 1 ? "store" : "stores"}
        </span>
        <span className="flex items-center gap-1 text-ink-3">
          {formatBDT(max)}
          <span className="uppercase tracking-wide text-ink-4">high</span>
        </span>
      </div>
    </div>
  );
}
