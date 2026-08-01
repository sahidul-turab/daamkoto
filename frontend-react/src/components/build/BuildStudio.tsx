import { Suspense, lazy, useEffect, useMemo, useRef, useState, type Ref } from "react";
import {
  AlertTriangle,
  Check,
  ChevronRight,
  Eye,
  Maximize2,
  Minus,
  PackageCheck,
  Plus,
  RotateCcw,
  Share2,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  TrendingDown,
  X,
  Zap,
} from "lucide-react";
import { CategoryIcon } from "../Icon";
import { SlotPicker } from "./SlotPicker";
import { CompatReport } from "./CompatReport";
import { WattageGauge } from "./WattageGauge";
import {
  SLOTS,
  isMulti,
  slotDef,
  slotLines,
  type BuildLine,
  type BuildState,
  type SlotId,
} from "../../lib/buildConfig";
import { evaluateBuild } from "../../lib/compat";
import { computeBasket, type Basket, type BasketItem } from "../../lib/basket";
import { retailerColor } from "../../config";
import { formatBDT } from "../../lib/format";
import { useCountUp } from "../../lib/useCountUp";
import type { ProductSummary } from "../../types";

const Rig3D = lazy(() => import("./Rig3D"));

type DetailTab = "overview" | "compatibility" | "prices";
type SlotDefinition = (typeof SLOTS)[number];

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

interface BuildSlotCardProps {
  slot: SlotDefinition;
  step: number;
  lines: BuildLine[];
  basketItems: BasketItem[];
  hasError: boolean;
  onChoose: () => void;
  onOpenProduct: (p: ProductSummary) => void;
  onRemoveSlot: () => void;
  onRemoveLine: (index: number) => void;
  onSetQty: (index: number, qty: number) => void;
}

function BuildSlotCard({
  slot,
  step,
  lines,
  basketItems,
  hasError,
  onChoose,
  onOpenProduct,
  onRemoveSlot,
  onRemoveLine,
  onSetQty,
}: BuildSlotCardProps) {
  const multi = isMulti(slot.id);
  const maxLines = ((slot as Record<string, unknown>).maxLines as number | undefined) ?? 1;
  const selected = lines.length > 0;

  return (
    <article
      className={`min-w-0 rounded-2xl border p-3.5 transition-colors sm:p-4 ${
        hasError
          ? "border-brand/60 bg-brand-strong/[0.06]"
          : selected
            ? "border-line-2 bg-surface-2/75"
            : "border-line bg-surface-2/35 hover:border-line-2"
      }`}
    >
      <div className="flex min-w-0 items-center gap-3">
        <div
          className={`relative grid h-10 w-10 shrink-0 place-items-center rounded-xl border ${
            selected ? "border-brand/25 bg-brand-strong/10 text-brand" : "border-line bg-surface text-ink-3"
          }`}
        >
          <CategoryIcon name={slot.icon} className="h-[18px] w-[18px]" />
          <span className="absolute -right-1.5 -top-1.5 grid h-4 min-w-4 place-items-center rounded-full border border-line bg-surface px-1 text-[9px] font-bold text-ink-3">
            {step}
          </span>
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
            <h3 className="truncate text-sm font-bold text-ink">{slot.label}</h3>
            {hasError ? (
              <span className="inline-flex items-center gap-1 rounded-full bg-brand-strong/12 px-2 py-0.5 text-[10px] font-semibold text-brand">
                <AlertTriangle className="h-2.5 w-2.5" /> Check fit
              </span>
            ) : selected ? (
              <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-ok">
                <Check className="h-2.5 w-2.5" /> Selected
              </span>
            ) : null}
          </div>
          <p className="mt-0.5 text-[11px] text-ink-4">
            {selected
              ? multi
                ? `${lines.length} ${lines.length === 1 ? "product" : "products"} added`
                : "Ready to compare"
              : `Step ${step} of ${SLOTS.length}`}
          </p>
        </div>

        {selected && (
          <button
            type="button"
            onClick={onRemoveSlot}
            className="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-ink-4 transition-colors hover:bg-brand-strong/10 hover:text-brand"
            aria-label={`Remove ${slot.label}`}
            title={`Remove ${slot.label}`}
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {!selected ? (
        <button
          type="button"
          onClick={onChoose}
          className="mt-3 flex w-full items-center justify-between gap-3 rounded-xl border border-dashed border-line px-3.5 py-3 text-left text-[13px] font-semibold text-ink-2 transition-colors hover:border-brand/40 hover:bg-brand-strong/[0.05] hover:text-ink"
        >
          <span className="flex min-w-0 items-center gap-2">
            <Plus className="h-4 w-4 shrink-0 text-brand" />
            Choose {slot.label.toLowerCase()}
          </span>
          <ChevronRight className="h-4 w-4 shrink-0 text-ink-4" />
        </button>
      ) : multi ? (
        <div className="mt-3 min-w-0 space-y-2">
          {lines.map((line, index) => {
            const basketItem = basketItems.find((item) => item.lineIndex === index);
            const retailer = basketItem?.retailer ?? line.product.cheapest_retailer;
            const linePrice =
              basketItem?.lineTotal ??
              (line.product.cheapest_price != null ? line.product.cheapest_price * line.qty : null);

            return (
              <div key={`${line.product.id}-${index}`} className="min-w-0 rounded-xl border border-line bg-surface/65 p-3">
                <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-start gap-2">
                  <button
                    type="button"
                    onClick={() => onOpenProduct(line.product)}
                    className="min-w-0 text-left text-[12px] font-semibold leading-snug text-ink hover:text-brand"
                  >
                    <span className="line-clamp-2 break-words">{line.product.name}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => onRemoveLine(index)}
                    className="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-ink-4 hover:bg-brand-strong/10 hover:text-brand"
                    aria-label={`Remove ${line.product.name}`}
                  >
                    <X className="h-3 w-3" />
                  </button>
                </div>

                <div className="mt-2 flex min-w-0 flex-wrap items-center justify-between gap-2">
                  <div className="flex min-w-0 items-center gap-1.5 text-[11px] text-ink-4">
                    {retailer && (
                      <span
                        className="h-2 w-2 shrink-0 rounded-full"
                        style={{ background: retailerColor(retailer) }}
                      />
                    )}
                    <span className="max-w-[9rem] truncate">{retailer ?? "Price unavailable"}</span>
                  </div>
                  <span className="shrink-0 text-[12px] font-bold tabular-nums text-ink">
                    {formatBDT(linePrice)}
                  </span>
                </div>

                <div className="mt-2 flex items-center justify-between gap-3 border-t border-line/70 pt-2">
                  <span className="text-[10px] uppercase tracking-wide text-ink-4">Quantity</span>
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={() => onSetQty(index, line.qty - 1)}
                      disabled={line.qty <= 1}
                      className="grid h-8 w-8 place-items-center rounded-lg border border-line text-ink-3 hover:border-line-2 hover:text-brand disabled:opacity-30"
                      aria-label={`Decrease quantity of ${line.product.name}`}
                    >
                      <Minus className="h-3 w-3" />
                    </button>
                    <span className="w-5 text-center text-[12px] font-bold tabular-nums text-ink">
                      {line.qty}
                    </span>
                    <button
                      type="button"
                      onClick={() => onSetQty(index, line.qty + 1)}
                      disabled={line.qty >= 8}
                      className="grid h-8 w-8 place-items-center rounded-lg border border-line text-ink-3 hover:border-line-2 hover:text-brand disabled:opacity-30"
                      aria-label={`Increase quantity of ${line.product.name}`}
                    >
                      <Plus className="h-3 w-3" />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}

          {lines.length < maxLines && (
            <button
              type="button"
              onClick={onChoose}
              className="flex w-full items-center justify-center gap-1.5 rounded-xl border border-dashed border-line py-2 text-[11px] font-semibold text-ink-3 hover:border-brand/35 hover:text-brand"
            >
              <Plus className="h-3.5 w-3.5" /> Add another {slot.label.toLowerCase()}
            </button>
          )}
        </div>
      ) : (
        <div className="mt-3 min-w-0 rounded-xl border border-line bg-surface/65 p-3">
          <button
            type="button"
            onClick={() => onOpenProduct(lines[0].product)}
            className="line-clamp-2 min-w-0 break-words text-left text-[13px] font-semibold leading-snug text-ink hover:text-brand"
          >
            {lines[0].product.name}
          </button>
          <div className="mt-2 flex min-w-0 flex-wrap items-end justify-between gap-2">
            <div className="min-w-0">
              {(() => {
                const basketItem = basketItems[0];
                const retailer = basketItem?.retailer ?? lines[0].product.cheapest_retailer;
                return (
                  <>
                    <div className="text-base font-extrabold tabular-nums text-ink">
                      {formatBDT(basketItem?.lineTotal ?? lines[0].product.cheapest_price)}
                    </div>
                    <div className="flex min-w-0 items-center gap-1.5 text-[11px] text-ink-4">
                      {retailer && (
                        <span
                          className="h-2 w-2 shrink-0 rounded-full"
                          style={{ background: retailerColor(retailer) }}
                        />
                      )}
                      <span className="truncate">{retailer ?? "Price unavailable"}</span>
                    </div>
                  </>
                );
              })()}
            </div>
            <button
              type="button"
              onClick={onChoose}
              className="rounded-lg border border-line px-3 py-1.5 text-[11px] font-semibold text-ink-2 transition-colors hover:border-brand/40 hover:text-brand"
            >
              Change
            </button>
          </div>
        </div>
      )}
    </article>
  );
}

interface BuildSnapshotProps {
  build: BuildState;
  errorSlots: Set<SlotId>;
  basket: Basket;
  selectedLines: number;
  animatedBestTotal: number | null;
  rigReady: boolean;
  expanded: boolean;
  previewButtonRef: Ref<HTMLButtonElement>;
  onOpenPrices: () => void;
  onExpand: () => void;
}

function BuildSnapshot({
  build,
  errorSlots,
  basket,
  selectedLines,
  animatedBestTotal,
  rigReady,
  expanded,
  previewButtonRef,
  onOpenPrices,
  onExpand,
}: BuildSnapshotProps) {
  const hasPricedItems = basket.items.length > 0;
  const fullyPriced = selectedLines > 0 && basket.missingPrice.length === 0;
  const hasSavings = fullyPriced && basket.bestSavingsVsSingleStore > 0 && basket.singleStore;

  const priceNote =
    selectedLines === 0
      ? "Add parts to calculate your build"
      : !hasPricedItems
        ? "No current in-stock prices"
        : basket.missingPrice.length > 0
          ? `${basket.missingPrice.length} unavailable · priced parts only`
          : hasSavings
            ? `Save ${formatBDT(basket.bestSavingsVsSingleStore)} vs one store`
            : basket.singleStore
              ? "Lowest split and one-store totals match"
              : "Lowest available price selected for each part";

  return (
    <div
      className={`relative grid min-h-[104px] w-full min-w-0 max-w-full grid-cols-[minmax(0,1fr)_96px] overflow-hidden rounded-2xl border bg-gradient-to-br from-surface-2/95 to-surface/90 shadow-lg min-[420px]:grid-cols-[minmax(0,1fr)_108px] sm:max-w-[400px] lg:max-w-none ${
        hasSavings ? "border-ok/35 shadow-ok/5" : "border-brand/25 shadow-brand-strong/5"
      }`}
    >
      <button
        type="button"
        onClick={onOpenPrices}
        className="group min-w-0 p-3.5 text-left transition-colors hover:bg-white/[0.025] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand/70"
        aria-label="Open the build purchase plan"
      >
        <span className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-ink-4">
          <ShoppingBag className="h-3 w-3 text-brand" />
          {basket.missingPrice.length > 0 ? "Priced best total" : "Best-price total"}
        </span>
        <span className="mt-1 block truncate text-[25px] font-extrabold leading-none tabular-nums text-ink">
          {hasPricedItems ? formatBDT(animatedBestTotal) : "—"}
        </span>
        <span
          className={`mt-2 flex min-w-0 items-center gap-1.5 text-[10px] font-semibold ${
            hasSavings ? "text-ok" : basket.missingPrice.length > 0 ? "text-warn" : "text-ink-3"
          }`}
        >
          {hasSavings ? <TrendingDown className="h-3 w-3 shrink-0" /> : null}
          <span className="truncate">{priceNote}</span>
        </span>
        {basket.hasOverrides && hasPricedItems && (
          <span className="mt-1 block truncate text-[9px] text-ink-4">
            Your store choices: {formatBDT(basket.total)}
          </span>
        )}
      </button>

      <div className="relative min-h-[104px] overflow-hidden border-l border-line bg-black/10">
        <span className="pointer-events-none absolute left-2.5 top-2 z-10 rounded-full border border-line bg-surface/80 px-2 py-0.5 text-[8px] font-bold uppercase tracking-[0.12em] text-ink-3 backdrop-blur">
          Live 3D
        </span>

        <div className="pointer-events-none absolute inset-0">
          {rigReady && !expanded ? (
            <Suspense
              fallback={
                <div className="grid h-full place-items-center">
                  <div className="h-10 w-10 animate-pulse rounded-xl border border-brand/25 bg-brand-strong/10" />
                </div>
              }
            >
              <Rig3D build={build} errorSlots={errorSlots} mode="mini" />
            </Suspense>
          ) : (
            <div className="grid h-full place-items-center text-brand/70">
              <Eye className="h-7 w-7" />
            </div>
          )}
        </div>

        <button
          ref={previewButtonRef}
          type="button"
          onClick={onExpand}
          aria-expanded={expanded}
          aria-controls="build-3d-preview"
          aria-label={expanded ? "Scroll to expanded 3D build preview" : "Expand the 3D build preview"}
          className="absolute inset-0 z-20 rounded-r-2xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand/70"
        >
          <span className="absolute bottom-2 right-2 grid h-6 w-6 place-items-center rounded-lg border border-line bg-surface/80 text-ink-2 shadow-sm backdrop-blur transition-colors hover:text-brand">
            <Maximize2 className="h-3 w-3" />
          </span>
        </button>
      </div>
    </div>
  );
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
  const [activeTab, setActiveTab] = useState<DetailTab>("overview");
  const [showPreview, setShowPreview] = useState(false);
  const [liveRigReady, setLiveRigReady] = useState(false);
  const [shareState, setShareState] = useState<"idle" | "copied" | "failed">("idle");
  const [confirmClear, setConfirmClear] = useState(false);
  const summaryRef = useRef<HTMLElement>(null);
  const previewRef = useRef<HTMLElement>(null);
  const previewButtonRef = useRef<HTMLButtonElement>(null);

  const compat = useMemo(() => evaluateBuild(build), [build]);
  const basket = useMemo(() => computeBasket(build), [build]);
  const partCount = SLOTS.filter((slot) => slotLines(build, slot.id).length > 0).length;
  const selectedLines = SLOTS.reduce((sum, slot) => sum + slotLines(build, slot.id).length, 0);
  const nextSlot = SLOTS.find((slot) => slotLines(build, slot.id).length === 0) ?? null;
  const animatedTotal = useCountUp(basket.total, 600);
  const animatedBestTotal = useCountUp(basket.bestTotal, 600);
  const errors = compat.issues.filter((issue) => issue.level === "error").length;
  const warnings = compat.issues.filter((issue) => issue.level === "warn").length;
  const successfulChecks = compat.issues.filter((issue) => issue.level === "ok").length;
  const hasPowerParts = !!build.cpu?.length || !!build.gpu?.length;
  const hasPsu = !!build.psu?.length;
  const fullyPriced = selectedLines > 0 && basket.missingPrice.length === 0;
  const hasBestSavings = fullyPriced && basket.bestSavingsVsSingleStore > 0 && !!basket.singleStore;
  const displayedPlanTotal = basket.hasOverrides ? animatedTotal : animatedBestTotal;

  useEffect(() => {
    // The 3D renderer is intentionally idle-loaded: the useful builder UI paints
    // first, then the live rig appears without putting its large WebGL chunk on
    // the critical path.
    const idleWindow = window as unknown as {
      requestIdleCallback?: (callback: () => void, options?: { timeout: number }) => number;
      cancelIdleCallback?: (id: number) => void;
    };
    if (idleWindow.requestIdleCallback) {
      const idleId = idleWindow.requestIdleCallback(() => setLiveRigReady(true), { timeout: 900 });
      return () => idleWindow.cancelIdleCallback?.(idleId);
    }
    const timer = window.setTimeout(() => setLiveRigReady(true), 350);
    return () => window.clearTimeout(timer);
  }, []);

  const compatibilityLabel =
    partCount < 2
      ? "Checks start after 2 parts"
      : errors > 0
        ? `${errors} ${errors === 1 ? "conflict" : "conflicts"} found`
        : warnings > 0
          ? `No conflicts · ${warnings} to verify`
          : successfulChecks > 0
            ? "No conflicts found"
            : "No matching checks yet";

  const compatibilityTone =
    errors > 0
      ? "text-brand"
      : warnings > 0
        ? "text-warn"
        : partCount < 2 || successfulChecks === 0
          ? "text-ink-3"
          : "text-ok";

  const shareLabel =
    shareState === "copied" ? "Link copied" : shareState === "failed" ? "Copy failed" : "Share build";

  const share = async () => {
    const url = onShare();
    try {
      await navigator.clipboard.writeText(url);
      setShareState("copied");
    } catch {
      setShareState("failed");
    }
    window.setTimeout(() => setShareState("idle"), 2200);
  };

  const clearBuild = () => {
    if (!confirmClear) {
      setConfirmClear(true);
      window.setTimeout(() => setConfirmClear(false), 3000);
      return;
    }
    onClear();
    setConfirmClear(false);
    setActiveTab("overview");
  };

  const handlePick = (slotId: SlotId, product: ProductSummary) => {
    if (isMulti(slotId)) onAddLine(slotId, product);
    else onSetPart(slotId, product);
  };

  const chooseNext = () => {
    if (nextSlot) {
      setPickerSlot(nextSlot.id);
      return;
    }
    setActiveTab("prices");
    window.setTimeout(() => summaryRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
  };

  const openPreview = () => {
    setShowPreview(true);
    window.setTimeout(() => previewRef.current?.scrollIntoView({ behavior: "smooth", block: "center" }), 0);
  };

  const closePreview = () => {
    setShowPreview(false);
    window.setTimeout(() => previewButtonRef.current?.focus({ preventScroll: true }), 0);
  };

  const goToSummaryTab = (tab: DetailTab) => {
    setActiveTab(tab);
    if (window.matchMedia("(max-width: 1279px)").matches) {
      window.setTimeout(() => summaryRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
    }
  };

  return (
    <div className="min-w-0 space-y-5 pb-24 lg:pb-0">
      <div className="sr-only" role="status" aria-live="polite">
        {shareState === "copied" ? "Build link copied to clipboard" : shareState === "failed" ? "Build link could not be copied" : ""}
      </div>
      <header className="glass relative overflow-hidden p-5 sm:p-6">
        <div className="pointer-events-none absolute -right-20 -top-32 h-72 w-72 rounded-full bg-brand-strong/10 blur-3xl" />
        <div className="relative grid min-w-0 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(300px,340px)_auto] lg:items-center">
          <div className="order-1 min-w-0 max-w-2xl">
            <div className="mb-2 inline-flex items-center gap-1.5 rounded-full border border-brand/25 bg-brand-strong/10 px-2.5 py-1 text-[11px] font-semibold text-brand">
              <Sparkles className="h-3 w-3" /> Guided PC builder
            </div>
            <h1 className="text-2xl font-extrabold tracking-tight text-ink sm:text-3xl">Build your PC with confidence</h1>
            <p className="mt-2 text-sm leading-relaxed text-ink-3">
              Pick any part in any order. We will check compatibility and find the best store plan as you go.
            </p>
          </div>

          <div className="order-3 min-w-0 max-w-full lg:order-2">
            <BuildSnapshot
              build={build}
              errorSlots={compat.errorSlots}
              basket={basket}
              selectedLines={selectedLines}
              animatedBestTotal={animatedBestTotal}
              rigReady={liveRigReady}
              expanded={showPreview}
              previewButtonRef={previewButtonRef}
              onOpenPrices={() => goToSummaryTab("prices")}
              onExpand={openPreview}
            />
          </div>

          <div className="order-2 flex min-w-0 w-full flex-wrap items-center gap-2 lg:order-3 lg:w-auto lg:justify-end">
            {partCount > 0 && (
              <button
                type="button"
                onClick={clearBuild}
                onBlur={() => setConfirmClear(false)}
                aria-label={confirmClear ? "Confirm clearing this build" : "Clear this build"}
                className={`btn-ghost !px-3 !py-2 ${confirmClear ? "!border-brand/50 !text-brand" : ""}`}
              >
                <RotateCcw className="h-3.5 w-3.5" />
                <span className={confirmClear ? "" : "hidden sm:inline"}>
                  {confirmClear ? "Click again to clear" : "Clear"}
                </span>
              </button>
            )}
            <button
              type="button"
              onClick={share}
              disabled={partCount === 0}
              aria-label="Share this build"
              className="btn-ghost !px-3 !py-2"
            >
              {shareState === "copied" ? <Check className="h-3.5 w-3.5 text-ok" /> : <Share2 className="h-3.5 w-3.5" />}
              <span className="hidden sm:inline">
                {shareState === "copied" ? "Link copied" : shareState === "failed" ? "Copy failed" : "Share"}
              </span>
            </button>
            <button type="button" onClick={chooseNext} className="btn-brand min-w-0 flex-1 !py-2 sm:flex-none">
              {nextSlot ? `Choose ${nextSlot.label}` : "Review prices"}
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="relative mt-5 grid gap-3 border-t border-line pt-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
          <div className="min-w-0">
            <div className="mb-2 flex items-center justify-between gap-3 text-[11px]">
              <span className="font-semibold text-ink-2">{partCount} of {SLOTS.length} component types selected</span>
              <span className="text-ink-4">{Math.round((partCount / SLOTS.length) * 100)}%</span>
            </div>
            <div className="grid grid-cols-8 gap-1.5" aria-label={`${partCount} of ${SLOTS.length} component types selected`}>
              {SLOTS.map((slot) => {
                const filled = slotLines(build, slot.id).length > 0;
                return (
                  <button
                    type="button"
                    key={slot.id}
                    onClick={() => setPickerSlot(slot.id)}
                    className="group flex h-8 items-center rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/70"
                    title={`${filled ? "Change" : "Choose"} ${slot.label}`}
                    aria-label={`${filled ? "Change" : "Choose"} ${slot.label}`}
                  >
                    <span
                      className={`h-1.5 w-full rounded-full transition-all group-hover:h-2.5 ${
                        filled
                          ? compat.errorSlots.has(slot.id)
                            ? "bg-brand"
                            : "bg-ok"
                          : slot.id === nextSlot?.id
                            ? "bg-line-2"
                            : "bg-line"
                      }`}
                    />
                  </button>
                );
              })}
            </div>
          </div>

          <button
            type="button"
            onClick={() => goToSummaryTab("compatibility")}
            className="flex min-w-0 items-center gap-2 rounded-xl border border-line bg-surface-2/65 px-3 py-2 text-left hover:border-line-2"
          >
            <ShieldCheck className={`h-4 w-4 shrink-0 ${compatibilityTone}`} />
            <span className="min-w-0">
              <span className="block text-[10px] uppercase tracking-wide text-ink-4">Compatibility</span>
              <span className={`block truncate text-[11px] font-semibold ${compatibilityTone}`}>{compatibilityLabel}</span>
            </span>
          </button>

        </div>
      </header>

      <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(360px,410px)] xl:items-start">
        <section className="glass min-w-0 p-4 sm:p-5">
          <div className="mb-4 flex flex-col gap-3 border-b border-line pb-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-lg font-bold text-ink">Choose your parts</h2>
              <p className="mt-1 text-xs text-ink-4">Open any slot to compare matching products and prices.</p>
            </div>
            {nextSlot && (
              <button
                type="button"
                onClick={() => setPickerSlot(nextSlot.id)}
                className="inline-flex items-center gap-1.5 self-start text-xs font-semibold text-brand hover:text-ink sm:self-auto"
              >
                Next: {nextSlot.label} <ChevronRight className="h-3.5 w-3.5" />
              </button>
            )}
          </div>

          <div className="grid min-w-0 gap-3 md:grid-cols-2 md:items-start">
            {[SLOTS.slice(0, 4), SLOTS.slice(4)].map((group, groupIndex) => (
              <div key={groupIndex} className="min-w-0 space-y-3">
                {group.map((slot) => {
                  const index = SLOTS.findIndex((candidate) => candidate.id === slot.id);
                  return (
                    <BuildSlotCard
                      key={slot.id}
                      slot={slot}
                      step={index + 1}
                      lines={slotLines(build, slot.id)}
                      basketItems={basket.items.filter((item) => item.slotId === slot.id)}
                      hasError={compat.errorSlots.has(slot.id)}
                      onChoose={() => setPickerSlot(slot.id)}
                      onOpenProduct={onOpenProduct}
                      onRemoveSlot={() => onRemove(slot.id)}
                      onRemoveLine={(lineIndex) => onRemoveLine(slot.id, lineIndex)}
                      onSetQty={(lineIndex, qty) => onSetQty(slot.id, lineIndex, qty)}
                    />
                  );
                })}
              </div>
            ))}
          </div>
        </section>

        <aside ref={summaryRef} className="min-w-0 scroll-mt-24 xl:sticky xl:top-24">
          <div className="glass min-w-0 overflow-hidden">
            <div
              className="grid grid-cols-3 gap-1 border-b border-line bg-surface-2/45 p-1.5"
              role="tablist"
              aria-label="Build details"
            >
              {([
                ["overview", "Summary"],
                ["compatibility", errors > 0 ? `Checks · ${errors}` : "Checks"],
                ["prices", `Buy plan${selectedLines > 0 ? ` · ${selectedLines}` : ""}`],
              ] as [DetailTab, string][]).map(([tab, label]) => (
                <button
                  type="button"
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  id={`build-tab-${tab}`}
                  role="tab"
                  aria-selected={activeTab === tab}
                  aria-controls={`build-panel-${tab}`}
                  className={`min-w-0 rounded-lg px-2 py-2 text-[11px] font-semibold transition-colors ${
                    activeTab === tab ? "bg-elevated text-ink shadow-sm" : "text-ink-3 hover:text-ink"
                  }`}
                >
                  <span className="block truncate">{label}</span>
                </button>
              ))}
            </div>

            {activeTab === "overview" && (
              <div
                className="p-5"
                id="build-panel-overview"
                role="tabpanel"
                aria-labelledby="build-tab-overview"
              >
                <div
                  className={`overflow-hidden rounded-2xl border bg-gradient-to-br from-surface-2 to-surface/80 ${
                    hasBestSavings ? "border-ok/35 shadow-lg shadow-ok/5" : "border-brand/25"
                  }`}
                >
                  <button
                    type="button"
                    onClick={() => setActiveTab("prices")}
                    className="flex w-full items-start justify-between gap-4 p-4 text-left transition-colors hover:bg-white/[0.025]"
                  >
                    <span className="min-w-0">
                      <span className="block text-[10px] font-semibold uppercase tracking-[0.12em] text-ink-4">
                        {basket.hasOverrides
                          ? basket.missingPrice.length > 0
                            ? "Priced selected-store total"
                            : "Your selected-store total"
                          : basket.missingPrice.length > 0
                            ? "Priced best total"
                            : "Best-price total"}
                      </span>
                      <span className="mt-1 block text-3xl font-extrabold leading-none tabular-nums text-ink">
                        {basket.items.length > 0 ? formatBDT(displayedPlanTotal) : "—"}
                      </span>
                      <span className="mt-2 block text-[10px] text-ink-4">
                        {basket.items.length} priced {basket.items.length === 1 ? "product" : "products"}
                        {basket.missingPrice.length > 0 && (
                          <span className="ml-1 text-warn">· {basket.missingPrice.length} unavailable</span>
                        )}
                      </span>
                      {basket.hasOverrides && basket.items.length > 0 && (
                        <span className="mt-1.5 block text-[10px] font-semibold text-ok">
                          Best available: {formatBDT(animatedBestTotal)}
                        </span>
                      )}
                    </span>
                    <span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl border border-brand/20 bg-brand-strong/10 text-brand">
                      <ShoppingBag className="h-5 w-5" />
                    </span>
                  </button>

                  {hasBestSavings && basket.singleStore ? (
                    <button
                      type="button"
                      onClick={() => setActiveTab("prices")}
                      className="flex w-full items-center justify-between gap-3 border-t border-ok/25 bg-ok/[0.09] px-4 py-3.5 text-left transition-colors hover:bg-ok/[0.13]"
                    >
                      <span className="flex min-w-0 items-center gap-3">
                        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-ok/15 text-ok">
                          <TrendingDown className="h-4 w-4" />
                        </span>
                        <span className="min-w-0">
                          <span className="block text-[10px] font-semibold uppercase tracking-wide text-ok">You can save</span>
                          <span className="block text-lg font-extrabold leading-tight tabular-nums text-ok">
                            {formatBDT(basket.bestSavingsVsSingleStore)}
                          </span>
                          <span className="block truncate text-[9px] text-ink-4">
                            Buy parts separately instead of {basket.singleStore.retailer} at {formatBDT(basket.singleStore.total)}
                          </span>
                        </span>
                      </span>
                      <ChevronRight className="h-4 w-4 shrink-0 text-ok" />
                    </button>
                  ) : (
                    <div
                      className={`border-t px-4 py-3 text-[10px] ${
                        basket.missingPrice.length > 0
                          ? "border-warn/20 bg-warn/[0.05] text-warn"
                          : "border-line bg-white/[0.015] text-ink-4"
                      }`}
                    >
                      {selectedLines === 0
                        ? "Add products to calculate the total and possible savings."
                        : basket.missingPrice.length > 0
                          ? `${basket.missingPrice.length} unavailable ${basket.missingPrice.length === 1 ? "product is" : "products are"} not included in this total.`
                          : basket.singleStore
                            ? `One-store price at ${basket.singleStore.retailer} already matches the best split total.`
                            : "No single retailer currently stocks every selected product."}
                    </div>
                  )}
                </div>

                <div className="mt-4 divide-y divide-line rounded-xl border border-line bg-surface-2/45">
                  <button
                    type="button"
                    onClick={() => setActiveTab("compatibility")}
                    className="flex w-full items-center gap-3 px-3.5 py-3 text-left hover:bg-white/[0.02]"
                  >
                    <ShieldCheck className={`h-4 w-4 shrink-0 ${compatibilityTone}`} />
                    <span className="min-w-0 flex-1">
                      <span className="block text-[11px] font-semibold text-ink">Compatibility</span>
                      <span className={`block truncate text-[10px] ${compatibilityTone}`}>{compatibilityLabel}</span>
                    </span>
                    <ChevronRight className="h-4 w-4 shrink-0 text-ink-4" />
                  </button>

                  <button
                    type="button"
                    onClick={() => setActiveTab("compatibility")}
                    className="flex w-full items-center gap-3 px-3.5 py-3 text-left hover:bg-white/[0.02]"
                  >
                    <Zap className="h-4 w-4 shrink-0 text-warn" />
                    <span className="min-w-0 flex-1">
                      <span className="block text-[11px] font-semibold text-ink">Estimated power</span>
                      <span className="block truncate text-[10px] text-ink-4">
                        {hasPowerParts ? `About ${compat.estimatedWatts}W · ${compat.recommendedPsu}W+ PSU recommended` : "Add a processor or graphics card to estimate"}
                      </span>
                    </span>
                    <ChevronRight className="h-4 w-4 shrink-0 text-ink-4" />
                  </button>

                  <button
                    type="button"
                    onClick={() => setActiveTab("prices")}
                    className="flex w-full items-center gap-3 px-3.5 py-3 text-left hover:bg-white/[0.02]"
                  >
                    <PackageCheck className="h-4 w-4 shrink-0 text-info" />
                    <span className="min-w-0 flex-1">
                      <span className="block text-[11px] font-semibold text-ink">Where to buy</span>
                      <span className="block truncate text-[10px] text-ink-4">
                        {basket.items.length > 0 ? `${basket.perStore.length} ${basket.perStore.length === 1 ? "store" : "stores"} in the current plan` : "Store recommendations appear after you add a part"}
                      </span>
                    </span>
                    <ChevronRight className="h-4 w-4 shrink-0 text-ink-4" />
                  </button>
                </div>

                <button type="button" onClick={chooseNext} className="btn-brand mt-4 w-full">
                  {nextSlot ? `Choose ${nextSlot.label}` : "Review purchase plan"}
                  <ChevronRight className="h-4 w-4" />
                </button>

                <div className="mt-2 grid grid-cols-2 gap-2">
                  <button type="button" onClick={openPreview} className="btn-ghost !px-2.5 !py-2 text-xs">
                    <Eye className="h-3.5 w-3.5" /> 3D preview
                  </button>
                  <button type="button" onClick={share} disabled={partCount === 0} className="btn-ghost !px-2.5 !py-2 text-xs">
                    {shareState === "copied" ? <Check className="h-3.5 w-3.5 text-ok" /> : <Share2 className="h-3.5 w-3.5" />}
                    {shareState === "copied" ? "Copied" : shareState === "failed" ? "Copy failed" : "Share build"}
                  </button>
                </div>
              </div>
            )}

            {activeTab === "compatibility" && (
              <div
                className="space-y-5 p-5"
                id="build-panel-compatibility"
                role="tabpanel"
                aria-labelledby="build-tab-compatibility"
              >
                <div>
                  <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-ink-4">
                    <ShieldCheck className="h-4 w-4" /> Compatibility checks
                  </div>
                  <CompatReport issues={compat.issues} partCount={partCount} />
                </div>
                <div className="border-t border-line pt-5">
                  <WattageGauge
                    estimatedWatts={compat.estimatedWatts}
                    recommendedPsu={compat.recommendedPsu}
                    psuWatts={compat.psuWatts}
                    hasPowerParts={hasPowerParts}
                    hasPsu={hasPsu}
                  />
                </div>
                {compat.errorSlots.size > 0 && (
                  <p className="rounded-xl border border-brand/25 bg-brand-strong/[0.06] px-3 py-2.5 text-[11px] leading-relaxed text-ink-3">
                    Slots with conflicts are highlighted in the parts list. Change either highlighted component to re-check the build.
                  </p>
                )}
              </div>
            )}

            {activeTab === "prices" && (
              <div
                className="p-5"
                id="build-panel-prices"
                role="tabpanel"
                aria-labelledby="build-tab-prices"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-4">
                      {basket.hasOverrides
                        ? basket.missingPrice.length > 0
                          ? "Priced selected-store total"
                          : "Your selected-store total"
                        : basket.missingPrice.length > 0
                          ? "Priced best-price plan"
                          : "Best-price purchase plan"}
                    </div>
                    <div className="mt-1 text-2xl font-extrabold tabular-nums text-ink">
                      {basket.items.length > 0 ? formatBDT(displayedPlanTotal) : "—"}
                    </div>
                    {basket.hasOverrides && basket.items.length > 0 && (
                      <div className="mt-1 text-[10px] font-semibold text-ok">
                        Best available: {formatBDT(animatedBestTotal)}
                      </div>
                    )}
                  </div>
                  <ShoppingBag className="h-5 w-5 text-brand" />
                </div>

                {selectedLines === 0 ? (
                  <div className="mt-4 rounded-xl border border-dashed border-line px-4 py-8 text-center">
                    <ShoppingBag className="mx-auto h-6 w-6 text-ink-4" />
                    <p className="mt-2 text-xs font-semibold text-ink-2">Your store plan is empty</p>
                    <p className="mt-1 text-[11px] text-ink-4">Add a part and we will choose its lowest in-stock price.</p>
                    <button type="button" onClick={chooseNext} className="btn-brand mt-4 !py-2">Choose first part</button>
                  </div>
                ) : basket.items.length === 0 ? (
                  <div className="mt-4 rounded-xl border border-warn/25 bg-warn/[0.06] px-4 py-6 text-center">
                    <AlertTriangle className="mx-auto h-6 w-6 text-warn" />
                    <p className="mt-2 text-xs font-semibold text-ink-2">No current in-stock prices</p>
                    <p className="mt-1 text-[11px] leading-relaxed text-ink-4">
                      {basket.missingPrice.length} selected {basket.missingPrice.length === 1 ? "product is" : "products are"} currently unavailable, so the priced total is {formatBDT(0)}.
                    </p>
                    {basket.missingPrice[0] && (
                      <button
                        type="button"
                        onClick={() => setPickerSlot(basket.missingPrice[0].slotId)}
                        className="btn-brand mt-4 !py-2"
                      >
                        Change {slotDef(basket.missingPrice[0].slotId).label}
                      </button>
                    )}
                  </div>
                ) : (
                  <>
                    {basket.missingPrice.length > 0 && (
                      <div className="mt-4 flex gap-2 rounded-xl border border-warn/25 bg-warn/[0.07] px-3 py-2.5 text-[11px] text-warn">
                        <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                        {basket.missingPrice.length} selected {basket.missingPrice.length === 1 ? "product has" : "products have"} no in-stock price and is not included in the total.
                      </div>
                    )}

                    {hasBestSavings && basket.singleStore ? (
                      <div className="mt-4 rounded-xl border border-ok/35 bg-ok/[0.09] px-3.5 py-3 shadow-lg shadow-ok/5">
                        <div className="flex items-center gap-2 text-[13px] font-bold text-ok">
                          <TrendingDown className="h-4 w-4" /> Save {formatBDT(basket.bestSavingsVsSingleStore)} with the best-price split
                        </div>
                        <div className="mt-0.5 text-[10px] text-ink-4">
                          Compared with buying everything at {basket.singleStore.retailer} for {formatBDT(basket.singleStore.total)}.
                        </div>
                      </div>
                    ) : basket.singleStore && basket.missingPrice.length === 0 ? (
                      <div className="mt-4 rounded-xl border border-line bg-surface-2/55 px-3.5 py-2.5 text-[11px] text-ink-3">
                        One-store option: <span className="font-semibold text-ink">{basket.singleStore.retailer}</span> · {formatBDT(basket.singleStore.total)}
                      </div>
                    ) : null}

                    {basket.perStore.length > 0 && (
                      <div className="mt-5">
                        <div className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-ink-4">Spend by store</div>
                        <div className="space-y-1.5">
                          {basket.perStore.map((store) => (
                            <div key={store.retailer} className="flex items-center justify-between gap-3 text-[11px]">
                              <span className="flex min-w-0 items-center gap-1.5 text-ink-3">
                                <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: retailerColor(store.retailer) }} />
                                <span className="truncate">{store.retailer}</span>
                              </span>
                              <span className="shrink-0 font-semibold tabular-nums text-ink">{formatBDT(store.total)}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="mt-5 border-t border-line pt-4">
                      <div className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-ink-4">Products and retailers</div>
                      <div className="space-y-2">
                        {basket.items.map((item) => {
                          const cheapest = item.options[0];
                          const selectedRetailer = item.overridden && item.retailer !== cheapest?.retailer ? item.retailer : "__cheapest__";
                          return (
                            <div key={`${item.slotId}-${item.lineIndex}`} className="min-w-0 rounded-xl border border-line bg-surface-2/50 p-3">
                              <div className="flex min-w-0 items-start justify-between gap-3">
                                <div className="min-w-0">
                                  <div className="text-[9px] font-semibold uppercase tracking-wide text-ink-4">{slotDef(item.slotId).label}</div>
                                  <button
                                    type="button"
                                    onClick={() => onOpenProduct(item.product)}
                                    className="mt-0.5 line-clamp-2 break-words text-left text-[11px] font-semibold leading-snug text-ink hover:text-brand"
                                  >
                                    {item.product.name}{item.qty > 1 && <span className="ml-1 text-brand">×{item.qty}</span>}
                                  </button>
                                </div>
                                <span className="shrink-0 text-[12px] font-bold tabular-nums text-ink">{formatBDT(item.lineTotal)}</span>
                              </div>

                              <div className="mt-2 flex min-w-0 items-center gap-1.5">
                                <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: retailerColor(item.retailer) }} />
                                {item.options.length > 1 ? (
                                  <select
                                    value={selectedRetailer}
                                    onChange={(event) => {
                                      const value = event.target.value;
                                      onSetLineRetailer(item.slotId, item.lineIndex, value === "__cheapest__" ? undefined : value);
                                    }}
                                    className="min-w-0 flex-1 rounded-lg border border-line bg-surface px-2 py-1.5 text-[10px] text-ink-2 outline-none focus:border-brand/45"
                                    aria-label={`Retailer for ${item.product.name}`}
                                  >
                                    <option value="__cheapest__">{cheapest.retailer} · {formatBDT(cheapest.price)} (lowest)</option>
                                    {item.options.slice(1).map((option) => (
                                      <option key={option.retailer} value={option.retailer}>{option.retailer} · {formatBDT(option.price)}</option>
                                    ))}
                                  </select>
                                ) : (
                                  <span className="min-w-0 truncate text-[10px] text-ink-4">{item.retailer} · {formatBDT(item.unitPrice)}</span>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    <button type="button" onClick={share} className="btn-ghost mt-4 w-full">
                      {shareState === "copied" ? <Check className="h-4 w-4 text-ok" /> : <Share2 className="h-4 w-4" />}
                      {shareState === "idle" ? "Share this build" : shareLabel}
                    </button>
                  </>
                )}
              </div>
            )}
          </div>
        </aside>
      </div>

      {showPreview && (
        <section id="build-3d-preview" ref={previewRef} className="glass scroll-mt-24 overflow-hidden">
          <div className="flex items-center justify-between gap-4 border-b border-line px-4 py-3.5 sm:px-5">
            <div className="min-w-0">
              <div className="flex items-center gap-2 text-sm font-bold text-ink"><Eye className="h-4 w-4 text-brand" /> 3D build preview</div>
              <div className="mt-0.5 text-[10px] text-ink-4">Drag to rotate · scroll to zoom</div>
            </div>
            <button type="button" onClick={closePreview} className="btn-ghost !p-2" aria-label="Close 3D preview">
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="relative h-[320px] sm:h-[420px]">
            <Suspense fallback={<div className="grid h-full place-items-center text-sm text-ink-4">Loading 3D preview…</div>}>
              <Rig3D build={build} errorSlots={compat.errorSlots} mode="interactive" />
            </Suspense>
            {partCount === 0 && (
              <div className="pointer-events-none absolute inset-x-0 bottom-5 text-center text-xs text-ink-4">Add parts and watch your rig come together.</div>
            )}
          </div>
        </section>
      )}

      <div className="fixed inset-x-3 bottom-3 z-30 lg:hidden">
        <div className="mx-auto flex max-w-xl items-center gap-3 rounded-2xl border border-line-2 bg-surface/95 p-2.5 shadow-2xl backdrop-blur-xl">
          <div className="min-w-0 flex-1 pl-1">
            <div className="truncate text-base font-extrabold tabular-nums text-ink">
              {basket.items.length > 0 ? formatBDT(animatedBestTotal) : "—"}
            </div>
            <div className={`truncate text-[10px] ${hasBestSavings ? "font-semibold text-ok" : "text-ink-4"}`}>
              {hasBestSavings
                ? `Save ${formatBDT(basket.bestSavingsVsSingleStore)} vs one store`
                : basket.hasOverrides && basket.items.length > 0
                  ? `Best available · your choices ${formatBDT(basket.total)}`
                  : `${partCount}/${SLOTS.length} component types`}
              {!hasBestSavings && !basket.hasOverrides && basket.missingPrice.length > 0 && (
                <span className="text-warn"> · {basket.missingPrice.length} unavailable</span>
              )}
            </div>
          </div>
          <button type="button" onClick={chooseNext} className="btn-brand !px-3.5 !py-2.5">
            {nextSlot ? `Choose ${nextSlot.label}` : "Review prices"}
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>

      <SlotPicker
        slotId={pickerSlot}
        onClose={() => setPickerSlot(null)}
        onPick={handlePick}
        chosenLines={pickerSlot ? slotLines(build, pickerSlot) : []}
        onRemoveLine={pickerSlot ? (index) => onRemoveLine(pickerSlot, index) : undefined}
      />
    </div>
  );
}
