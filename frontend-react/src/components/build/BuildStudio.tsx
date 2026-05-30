import { Suspense, lazy, useMemo, useState } from "react";
import { Check, Minus, Plus, RotateCcw, Share2, X } from "lucide-react";
import { CategoryIcon } from "../Icon";
import { SlotPicker } from "./SlotPicker";
import { CompatReport } from "./CompatReport";
import { WattageGauge } from "./WattageGauge";
import { SLOTS, isMulti, slotLines, type BuildState, type SlotId } from "../../lib/buildConfig";
import { evaluateBuild } from "../../lib/compat";
import { computeBasket } from "../../lib/basket";
import { retailerColor } from "../../config";
import { formatBDT } from "../../lib/format";
import { useCountUp } from "../../lib/useCountUp";
import type { ProductSummary } from "../../types";

const Rig3D = lazy(() => import("./Rig3D"));

interface Props {
  build: BuildState;
  onSetPart: (slot: SlotId, p: ProductSummary) => void;
  onAddLine: (slot: SlotId, p: ProductSummary) => void;
  onRemoveLine: (slot: SlotId, index: number) => void;
  onSetQty: (slot: SlotId, index: number, qty: number) => void;
  onSetLineRetailer: (slot: SlotId, index: number, retailer: string | undefined) => void;
  onRemove: (slot: SlotId) => void;
  onClear: () => void;
  onShare: () => string;
  onOpenProduct: (p: ProductSummary) => void;
}

export function BuildStudio({
  build,
  onSetPart,
  onAddLine,
  onRemoveLine,
  onSetQty,
  onSetLineRetailer,
  onRemove,
  onClear,
  onShare,
  onOpenProduct,
}: Props) {
  const [pickerSlot, setPickerSlot] = useState<SlotId | null>(null);
  const [copied, setCopied] = useState(false);

  const compat = useMemo(() => evaluateBuild(build), [build]);
  const basket = useMemo(() => computeBasket(build), [build]);
  const partCount = Object.values(build).filter((l) => l && l.length > 0).length;
  const animatedTotal = useCountUp(basket.total, 600);

  const share = async () => {
    const url = onShare();
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      /* clipboard blocked */
    }
  };

  const handlePick = (slotId: SlotId, product: ProductSummary) => {
    if (isMulti(slotId)) {
      onAddLine(slotId, product);
    } else {
      onSetPart(slotId, product);
    }
  };

  return (
    <div className="grid gap-4 lg:grid-cols-[460px_1fr_400px]">
      {/* ── Left: slot list ── */}
      <div className="glass flex flex-col gap-2 p-4">
        <div className="mb-1 flex items-center justify-between">
          <h2 className="text-sm font-bold">Your Build</h2>
          {partCount > 0 && (
            <button
              onClick={onClear}
              className="flex items-center gap-1 text-xs text-ink-3 hover:text-brand"
            >
              <RotateCcw className="h-3 w-3" /> Clear
            </button>
          )}
        </div>

        {SLOTS.map((s) => {
          const lines = slotLines(build, s.id);
          const err = compat.errorSlots.has(s.id);
          const multi = isMulti(s.id);
          const maxLines = (s as Record<string, unknown>).maxLines as number | undefined ?? 1;
          const repProduct = lines[0]?.product;

          return (
            <div key={s.id} className="flex flex-col gap-1">
              {/* Slot header row */}
              <button
                onClick={() => setPickerSlot(s.id)}
                className={`group flex items-center gap-3 rounded-xl border px-3 py-2.5 text-left transition-all ${
                  err
                    ? "border-brand/50 bg-brand-strong/5"
                    : lines.length > 0
                      ? "border-line-2 bg-surface-2"
                      : "border-dashed border-line bg-surface-2/40 hover:border-line-2"
                }`}
              >
                <span
                  className="grid h-9 w-9 shrink-0 place-items-center rounded-lg"
                  style={{
                    background: repProduct
                      ? `${retailerColor(repProduct.cheapest_retailer ?? "")}22`
                      : "#16161f",
                    color: repProduct ? retailerColor(repProduct.cheapest_retailer ?? "") : "#5f5f6e",
                  }}
                >
                  <CategoryIcon name={s.icon} className="h-4 w-4" />
                </span>

                <div className="min-w-0 flex-1">
                  <div className="text-[11px] uppercase tracking-wide text-ink-4">{s.label}</div>
                  {lines.length === 0 ? (
                    <div className="flex items-center gap-1 text-[13px] font-medium text-ink-3">
                      <Plus className="h-3.5 w-3.5" /> Add {s.label.toLowerCase()}
                    </div>
                  ) : multi ? (
                    <div className="text-[13px] font-medium text-ink">
                      {lines.length} item{lines.length !== 1 ? "s" : ""}
                      {lines.length < maxLines && (
                        <span className="ml-1 text-[11px] text-ink-4">+ add more</span>
                      )}
                    </div>
                  ) : (
                    <span
                      role="button"
                      tabIndex={0}
                      onClick={(e) => {
                        e.stopPropagation();
                        onOpenProduct(repProduct!);
                      }}
                      className="line-clamp-1 block text-[13px] font-medium text-ink hover:text-brand"
                    >
                      {repProduct!.name}
                    </span>
                  )}
                </div>

                {/* Single-slot price + remove */}
                {!multi && lines.length > 0 && (
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold tabular-nums text-ink">
                      {formatBDT(repProduct!.cheapest_price)}
                    </span>
                    <span
                      role="button"
                      tabIndex={0}
                      onClick={(e) => {
                        e.stopPropagation();
                        onRemove(s.id);
                      }}
                      className="rounded p-1 text-ink-4 hover:text-brand"
                    >
                      <X className="h-3.5 w-3.5" />
                    </span>
                  </div>
                )}

                {/* Multi-slot clear all */}
                {multi && lines.length > 0 && (
                  <span
                    role="button"
                    tabIndex={0}
                    onClick={(e) => {
                      e.stopPropagation();
                      onRemove(s.id);
                    }}
                    className="rounded p-1 text-ink-4 hover:text-brand"
                  >
                    <X className="h-3.5 w-3.5" />
                  </span>
                )}
              </button>

              {/* Multi-slot line items */}
              {multi && lines.map((line, idx) => (
                <div
                  key={idx}
                  className="ml-12 flex items-center gap-2 rounded-lg border border-line bg-surface-2/60 px-3 py-2"
                >
                  <span
                    className="h-2 w-2 shrink-0 rounded-full"
                    style={{ background: retailerColor(line.product.cheapest_retailer ?? "") }}
                  />
                  <span
                    role="button"
                    tabIndex={0}
                    onClick={() => onOpenProduct(line.product)}
                    className="min-w-0 flex-1 cursor-pointer truncate text-[12px] text-ink hover:text-brand"
                  >
                    {line.product.name}
                  </span>
                  {/* Qty stepper */}
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => onSetQty(s.id, idx, line.qty - 1)}
                      disabled={line.qty <= 1}
                      className="flex h-5 w-5 items-center justify-center rounded border border-line text-ink-3 hover:text-brand disabled:opacity-30"
                    >
                      <Minus className="h-2.5 w-2.5" />
                    </button>
                    <span className="w-4 text-center text-[12px] font-bold tabular-nums text-ink">
                      {line.qty}
                    </span>
                    <button
                      onClick={() => onSetQty(s.id, idx, line.qty + 1)}
                      disabled={line.qty >= 8}
                      className="flex h-5 w-5 items-center justify-center rounded border border-line text-ink-3 hover:text-brand disabled:opacity-30"
                    >
                      <Plus className="h-2.5 w-2.5" />
                    </button>
                  </div>
                  <span className="shrink-0 text-[12px] font-bold tabular-nums text-ink">
                    {line.product.cheapest_price != null
                      ? formatBDT(line.product.cheapest_price * line.qty)
                      : "—"}
                  </span>
                  <button
                    onClick={() => onRemoveLine(s.id, idx)}
                    className="shrink-0 rounded p-0.5 text-ink-4 hover:text-brand"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </div>
              ))}
            </div>
          );
        })}
      </div>

      {/* ── Center: 3D rig ── */}
      <div className="glass relative min-h-[440px] overflow-hidden p-0">
        <div className="absolute left-4 top-4 z-10">
          <div className="text-sm font-bold">Build Studio</div>
          <div className="text-[11px] text-ink-4">Drag to rotate · scroll to zoom</div>
        </div>
        <Suspense
          fallback={
            <div className="grid h-full min-h-[440px] place-items-center text-sm text-ink-4">
              Loading 3D rig…
            </div>
          }
        >
          <Rig3D build={build} errorSlots={compat.errorSlots} />
        </Suspense>
        {partCount === 0 && (
          <div className="pointer-events-none absolute inset-x-0 bottom-6 text-center text-xs text-ink-4">
            Add parts on the left and watch your rig come together.
          </div>
        )}
      </div>

      {/* ── Right: gauge + report + basket ── */}
      <div className="flex flex-col gap-4 lg:sticky lg:top-24 lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto lg:pr-1">
        <div className="glass p-4">
          <WattageGauge
            estimatedWatts={compat.estimatedWatts}
            recommendedPsu={compat.recommendedPsu}
            psuWatts={compat.psuWatts}
          />
        </div>

        <div className="glass p-4">
          <CompatReport issues={compat.issues} partCount={partCount} />
        </div>

        <div className="glass p-4">
          {/* ── Header: total + item count ── */}
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-[11px] uppercase tracking-wide text-ink-4">Build total</div>
              <div className="text-3xl font-extrabold tabular-nums text-ink leading-tight">
                {formatBDT(animatedTotal)}
              </div>
              <div className="mt-0.5 text-[11px] text-ink-4">
                {basket.items.length} priced {basket.items.length === 1 ? "item" : "items"}
                {basket.missingPrice.length > 0 && (
                  <span className="ml-1.5 text-warn">· {basket.missingPrice.length} unavailable</span>
                )}
              </div>
            </div>
          </div>

          {/* ── Split-shop savings banner ── */}
          {basket.savingsVsSingleStore > 0 && basket.singleStore ? (
            <div className="mt-3 rounded-lg border border-ok/30 bg-ok/8 px-3 py-2.5">
              <div className="text-[12px] font-semibold text-ok">
                Split-shop saves you {formatBDT(basket.savingsVsSingleStore)}
              </div>
              <div className="mt-0.5 text-[11px] text-ink-4">
                vs one-stop at{" "}
                <span className="font-medium text-ink">{basket.singleStore.retailer}</span>
                {" "}({formatBDT(basket.singleStore.total)})
                <span className="ml-1 text-ink-5">— only shop with all items in stock</span>
              </div>
            </div>
          ) : basket.singleStore ? (
            <div className="mt-3 rounded-lg border border-line bg-surface-2/60 px-3 py-2 text-[11px] text-ink-4">
              One-stop option:{" "}
              <span className="font-medium text-ink">{basket.singleStore.retailer}</span>{" "}
              ({formatBDT(basket.singleStore.total)})
            </div>
          ) : null}

          {/* ── Per-store spending breakdown ── */}
          {basket.perStore.length > 1 && (
            <div className="mt-3 border-t border-line pt-3">
              <div className="mb-1.5 text-[11px] uppercase tracking-wide text-ink-4">By store</div>
              <div className="space-y-1">
                {basket.perStore.map((s) => (
                  <div key={s.retailer} className="flex items-center justify-between text-[12px]">
                    <span className="flex items-center gap-1.5 text-ink-3">
                      <span
                        className="h-2 w-2 rounded-full"
                        style={{ background: retailerColor(s.retailer) }}
                      />
                      {s.retailer}
                    </span>
                    <span className="font-semibold tabular-nums text-ink">{formatBDT(s.total)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── Purchase plan: per-item retailer + override ── */}
          {basket.items.length > 0 && (
            <div className="mt-3 border-t border-line pt-3">
              <div className="mb-2 text-[11px] uppercase tracking-wide text-ink-4">Purchase plan</div>
              <div className="space-y-2">
                {basket.items.map((item) => (
                  <div
                    key={`${item.slotId}-${item.lineIndex}`}
                    className="rounded-lg border border-line/60 bg-surface-2/50 px-3 py-2"
                  >
                    {/* Product name + total */}
                    <div className="flex items-start justify-between gap-2">
                      <span className="line-clamp-2 flex-1 text-[12px] font-medium leading-snug text-ink">
                        {item.product.name}
                        {item.qty > 1 && (
                          <span className="ml-1 font-bold text-brand"> ×{item.qty}</span>
                        )}
                      </span>
                      <span className="shrink-0 text-[12px] font-bold tabular-nums text-ink">
                        {formatBDT(item.lineTotal)}
                      </span>
                    </div>

                    {/* Shop row: color dot + dropdown or plain label */}
                    <div className="mt-1.5 flex items-center gap-1.5">
                      <span
                        className="h-2 w-2 shrink-0 rounded-full"
                        style={{ background: retailerColor(item.retailer) }}
                      />
                      {item.options.length > 1 ? (
                        <select
                          value={item.overridden ? item.retailer : "__cheapest__"}
                          onChange={(e) => {
                            const val = e.target.value;
                            onSetLineRetailer(
                              item.slotId,
                              item.lineIndex,
                              val === "__cheapest__" ? undefined : val,
                            );
                          }}
                          className="flex-1 rounded border border-line/60 bg-surface px-1.5 py-0.5 text-[11px] text-ink-3 focus:border-brand/40 focus:outline-none"
                        >
                          {/* "Auto-cheapest" as the default unoverridden option */}
                          <option value="__cheapest__">
                            {item.options[0].retailer} — {formatBDT(item.options[0].price)} (cheapest)
                          </option>
                          {/* All other retailers */}
                          {item.options.slice(1).map((o) => (
                            <option key={o.retailer} value={o.retailer}>
                              {o.retailer} — {formatBDT(o.price)}
                            </option>
                          ))}
                          {/* If currently overridden to a non-cheapest, keep that option */}
                          {item.overridden &&
                            item.retailer !== item.options[0].retailer && (
                              <option value={item.retailer}>
                                {item.retailer} — {formatBDT(item.unitPrice)} (selected)
                              </option>
                            )}
                        </select>
                      ) : (
                        <span className="text-[11px] text-ink-4">
                          {item.retailer} — {formatBDT(item.unitPrice)}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <button
            onClick={share}
            disabled={partCount === 0}
            className="btn-brand mt-4 w-full"
          >
            {copied ? (
              <>
                <Check className="h-4 w-4" /> Link copied
              </>
            ) : (
              <>
                <Share2 className="h-4 w-4" /> Share build
              </>
            )}
          </button>
        </div>
      </div>

      <SlotPicker
        slotId={pickerSlot}
        onClose={() => setPickerSlot(null)}
        onPick={handlePick}
        chosenLines={pickerSlot ? slotLines(build, pickerSlot) : []}
        onRemoveLine={pickerSlot ? (idx) => onRemoveLine(pickerSlot, idx) : undefined}
      />
    </div>
  );
}
