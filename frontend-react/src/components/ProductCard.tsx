import { useMemo, useRef, type MouseEvent } from "react";
import { ArrowRight, Plus, Store, TrendingDown } from "lucide-react";
import type { ProductSummary } from "../types";
import { retailerColor } from "../config";
import { formatBDT, humanizeKey } from "../lib/format";
import { useCountUp } from "../lib/useCountUp";
import { PriceSpread } from "./PriceSpread";
import { slotForCategory } from "../lib/buildConfig";

// Spec keys worth surfacing on the card face, in priority order per category.
const HIGHLIGHT_SPECS = [
  "capacity", "generation", "speed", "vram", "chipset", "chipset_brand",
  "memory_type", "socket", "series", "cores", "interface", "nand_type",
  "wattage", "efficiency", "type", "radiator_size", "form_factor",
  "fan_size", "side_panel", "color",
];

function pickSpecs(specs: Record<string, unknown>, max = 3) {
  const out: { key: string; value: string }[] = [];
  for (const key of HIGHLIGHT_SPECS) {
    const v = specs[key];
    if (v === undefined || v === null || v === "" || v === false) continue;
    out.push({ key, value: v === true ? humanizeKey(key) : String(v) });
    if (out.length >= max) break;
  }
  return out;
}

interface Props {
  product: ProductSummary;
  index: number;
  onOpen: (p: ProductSummary) => void;
  onAddToBuild?: (p: ProductSummary) => void;
  showAddToBuild?: boolean;
}

function staleness(scraped_at: string): { label: string; color: string } {
  const hours = (Date.now() - new Date(scraped_at).getTime()) / 3_600_000;
  if (hours < 24) return { label: "today", color: "#16a34a" };
  const days = Math.floor(hours / 24);
  if (hours < 72) return { label: `${days}d ago`, color: "#d97706" };
  return { label: `${days}d ago`, color: "#ef4444" };
}

export function ProductCard({ product, index, onOpen, onAddToBuild, showAddToBuild = false }: Props) {
  const cardRef = useRef<HTMLDivElement>(null);

  const inStock = product.listings.filter((l) => l.in_stock && l.price_bdt != null);
  const prices = inStock.map((l) => l.price_bdt as number);
  const max = prices.length ? Math.max(...prices) : null;
  const savings = max != null && product.cheapest_price != null ? max - product.cheapest_price : 0;

  const cheapestListing = inStock.length
    ? inStock.reduce((a, b) => (a.price_bdt! <= b.price_bdt! ? a : b))
    : null;

  const chips = useMemo(() => pickSpecs(product.specs), [product.specs]);
  const animatedPrice = useCountUp(product.cheapest_price);

  const canAddToBuild = showAddToBuild && !!slotForCategory(product.category) && !!onAddToBuild;

  // 3D tilt — pointer-driven CSS perspective transform + subtle glare overlay.
  const onMove = (e: MouseEvent<HTMLDivElement>) => {
    const el = cardRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const x = e.clientX - r.left;
    const y = e.clientY - r.top;
    const cx = r.width / 2;
    const cy = r.height / 2;
    const tiltX = ((y - cy) / cy) * -8;
    const tiltY = ((x - cx) / cx) * 8;
    el.style.transform = `perspective(900px) rotateX(${tiltX}deg) rotateY(${tiltY}deg) translateZ(4px)`;
    el.style.setProperty("--mx", `${x}px`);
    el.style.setProperty("--my", `${y}px`);
    // glare
    const glare = el.querySelector<HTMLSpanElement>(".card-glare");
    if (glare) {
      const pctX = (x / r.width) * 100;
      const pctY = (y / r.height) * 100;
      glare.style.background = `radial-gradient(circle at ${pctX}% ${pctY}%, rgba(255,255,255,0.08), transparent 55%)`;
    }
  };

  const onLeave = () => {
    const el = cardRef.current;
    if (!el) return;
    el.style.transform = "";
  };

  return (
    <div
      ref={cardRef}
      onMouseMove={onMove}
      onMouseLeave={onLeave}
      onClick={() => onOpen(product)}
      className="card-interactive group flex cursor-pointer flex-col p-5 animate-fade-up"
      style={{ animationDelay: `${Math.min(index, 12) * 30}ms`, willChange: "transform" }}
    >
      {/* Glare overlay for the tilt effect */}
      <span className="card-glare pointer-events-none absolute inset-0 rounded-[--radius-card]" />

      {/* Header: brand + store count + Add-to-Build */}
      <div className="relative flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          {product.brand && (
            <span className="chip !border-brand/30 !bg-brand-strong/10 !text-brand">
              {product.brand}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1.5 text-xs font-medium text-ink-3">
            <Store className="h-3.5 w-3.5" />
            {product.retailer_count}{" "}
            {product.retailer_count === 1 ? "store" : "stores"}
          </span>
        </div>
      </div>

      {/* Name */}
      <h3 className="relative mt-3 line-clamp-2 min-h-[2.6em] text-[15px] font-semibold leading-snug text-ink transition-colors group-hover:text-white">
        {product.name}
      </h3>

      {/* Spec chips */}
      {chips.length > 0 && (
        <div className="relative mt-3 flex flex-wrap gap-1.5">
          {chips.map((c) => (
            <span key={c.key} className="chip !py-0.5 !text-[11px]">
              {c.value}
            </span>
          ))}
        </div>
      )}

      {/* Price block */}
      <div className="relative mt-auto pt-5">
        {savings > 0 && (
          <div className="mb-1.5 inline-flex items-center gap-1 rounded-md bg-ok/10 px-1.5 py-0.5 text-[11px] font-semibold text-ok">
            <TrendingDown className="h-3 w-3" />
            Save up to {formatBDT(savings)}
          </div>
        )}
        <div className="flex items-end justify-between gap-2">
          <div>
            <div className="text-[11px] font-medium uppercase tracking-wide text-ink-4">from</div>
            <div className="text-2xl font-extrabold tracking-tight text-ink tabular-nums">
              {formatBDT(animatedPrice)}
            </div>
            {product.cheapest_retailer && (
              <div className="mt-1 flex items-center gap-1.5 text-xs text-ink-3">
                <span
                  className="h-2 w-2 rounded-full"
                  style={{ background: retailerColor(product.cheapest_retailer) }}
                />
                {product.cheapest_retailer}
              </div>
            )}
            {cheapestListing?.scraped_at && (() => {
              const { label, color } = staleness(cheapestListing.scraped_at);
              return (
                <div className="mt-0.5 flex items-center gap-1 text-[10px] font-semibold" style={{ color }}>
                  <span>●</span>
                  <span>Updated {label}</span>
                </div>
              );
            })()}
          </div>
          <span className="flex items-center gap-1 text-xs font-semibold text-brand opacity-0 transition-opacity group-hover:opacity-100">
            Compare
            <ArrowRight className="h-3.5 w-3.5" />
          </span>
        </div>

        {/* Price-spread rail */}
        <div className="mt-4">
          <PriceSpread listings={product.listings} variant="card" />
        </div>

        {/* Add to Build button — always visible when the product maps to a build slot */}
        {canAddToBuild && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onAddToBuild!(product);
            }}
            className="relative mt-4 flex w-full items-center justify-center gap-2 rounded-xl border border-brand/40 bg-brand-strong/10 py-2.5 text-sm font-semibold text-brand transition-all hover:border-brand/70 hover:bg-brand-strong/20 active:scale-[0.98]"
          >
            <Plus className="h-4 w-4" />
            Add to Build
          </button>
        )}
      </div>
    </div>
  );
}
