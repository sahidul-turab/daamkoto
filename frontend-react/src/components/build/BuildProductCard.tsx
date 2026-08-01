import { Check, ImageOff, Plus, Store } from "lucide-react";
import { useMemo, useState } from "react";
import { assetUrl } from "../../api";
import { retailerColor } from "../../config";
import { formatBDT, humanizeKey } from "../../lib/format";
import type { ProductSummary } from "../../types";

const HIGHLIGHT_SPECS = [
  "capacity",
  "generation",
  "speed",
  "vram",
  "chipset",
  "memory_type",
  "socket",
  "cores",
  "interface",
  "wattage",
  "efficiency",
  "radiator_size",
  "form_factor",
];

function pickSpecs(specs: Record<string, unknown>, max = 2) {
  const result: { key: string; value: string }[] = [];
  for (const key of HIGHLIGHT_SPECS) {
    const value = specs[key];
    if (value === undefined || value === null || value === "" || value === false) continue;
    result.push({ key, value: value === true ? humanizeKey(key) : String(value) });
    if (result.length >= max) break;
  }
  return result;
}

interface Props {
  product: ProductSummary;
  selected: boolean;
  multi: boolean;
  disabled: boolean;
  atMaxQuantity?: boolean;
  onOpen: () => void;
  onSelect: () => void;
}

export function BuildProductCard({
  product,
  selected,
  multi,
  disabled,
  atMaxQuantity = false,
  onOpen,
  onSelect,
}: Props) {
  const inStock = product.listings.filter((listing) => listing.in_stock && listing.price_bdt != null);
  const cheapestListing = inStock.length
    ? inStock.reduce((a, b) => (a.price_bdt! <= b.price_bdt! ? a : b))
    : null;
  const imageListing =
    product.listings.find((listing) => listing.image_cutout) ??
    (cheapestListing?.image_url ? cheapestListing : null) ??
    product.listings.find((listing) => listing.image_url) ??
    null;
  const cutoutUrl = imageListing?.image_cutout ? assetUrl(imageListing.image_cutout) : null;
  const photoUrl = imageListing?.image_url ?? null;
  const [cutoutFailed, setCutoutFailed] = useState(false);
  const [photoFailed, setPhotoFailed] = useState(false);
  const specs = useMemo(() => pickSpecs(product.specs), [product.specs]);
  const showCutout = !!cutoutUrl && !cutoutFailed;
  const showPhoto = !showCutout && !!photoUrl && !photoFailed;

  const buttonLabel = atMaxQuantity
    ? "Quantity max"
    : disabled
    ? "Slot full"
    : selected
      ? multi
        ? "Add one more"
        : "Selected"
      : "Select part";

  return (
    <article
      className={`min-w-0 rounded-2xl border bg-surface-2/55 p-3 transition-colors ${
        selected ? "border-ok/35" : "border-line hover:border-line-2"
      }`}
    >
      <div className="grid min-w-0 grid-cols-[76px_minmax(0,1fr)] gap-3">
        <button
          type="button"
          onClick={onOpen}
          className="relative flex h-[76px] w-[76px] items-center justify-center overflow-hidden rounded-xl bg-white/[0.03] ring-1 ring-inset ring-white/[0.05]"
          aria-label={`View ${product.name}`}
        >
          {showCutout ? (
            <img
              src={cutoutUrl!}
              alt=""
              loading="lazy"
              decoding="async"
              onError={() => setCutoutFailed(true)}
              className="h-full w-full object-contain p-2 drop-shadow-[0_8px_12px_rgba(0,0,0,0.5)]"
            />
          ) : showPhoto ? (
            <span className="flex h-full w-full items-center justify-center bg-gradient-to-b from-white to-slate-100">
              <img
                src={photoUrl!}
                alt=""
                loading="lazy"
                decoding="async"
                onError={() => setPhotoFailed(true)}
                className="h-full w-full object-contain p-2 mix-blend-multiply"
              />
            </span>
          ) : (
            <ImageOff className="h-5 w-5 text-ink-4" />
          )}
        </button>

        <div className="min-w-0">
          <div className="flex min-w-0 items-center justify-between gap-2">
            <span className="truncate text-[10px] font-semibold uppercase tracking-wide text-brand">
              {product.brand ?? "PC component"}
            </span>
            {selected && (
              <span className="inline-flex shrink-0 items-center gap-1 text-[9px] font-semibold text-ok">
                <Check className="h-2.5 w-2.5" /> In build
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={onOpen}
            className="mt-1 line-clamp-2 min-w-0 break-words text-left text-[12px] font-semibold leading-snug text-ink hover:text-brand"
          >
            {product.name}
          </button>
          {specs.length > 0 && (
            <div className="mt-2 flex min-w-0 flex-wrap gap-1">
              {specs.map((spec) => (
                <span key={spec.key} className="max-w-full truncate rounded-md border border-line bg-surface px-1.5 py-0.5 text-[9px] text-ink-3">
                  {spec.value}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="mt-3 flex min-w-0 items-center justify-between gap-3 border-t border-line pt-3">
        <div className="min-w-0">
          <div className="text-base font-extrabold leading-none tabular-nums text-ink">{formatBDT(product.cheapest_price)}</div>
          <div className="mt-1 flex min-w-0 items-center gap-1.5 text-[10px] text-ink-4">
            {product.cheapest_retailer && (
              <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: retailerColor(product.cheapest_retailer) }} />
            )}
            <span className="truncate">{product.cheapest_retailer ?? "Price unavailable"}</span>
            <span className="shrink-0">·</span>
            <Store className="h-2.5 w-2.5 shrink-0" />
            <span className="shrink-0">{product.retailer_count}</span>
          </div>
        </div>
        <button
          type="button"
          onClick={onSelect}
          disabled={disabled || atMaxQuantity || (selected && !multi)}
          className={`inline-flex min-h-9 shrink-0 items-center justify-center gap-1.5 rounded-xl px-3 text-[11px] font-semibold transition-colors ${
            selected && !multi
              ? "border border-ok/25 bg-ok/[0.08] text-ok"
              : "border border-brand/35 bg-brand-strong/10 text-brand hover:bg-brand-strong/20 disabled:border-line disabled:bg-surface disabled:text-ink-4"
          }`}
        >
          {selected && !multi ? <Check className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />}
          {buttonLabel}
        </button>
      </div>
    </article>
  );
}
