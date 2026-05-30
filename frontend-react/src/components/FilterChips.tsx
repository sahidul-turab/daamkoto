import { X } from "lucide-react";
import type { Filters } from "../types";
import { humanizeKey } from "../lib/format";

interface Props {
  filters: Filters;
  onChange: (patch: Partial<Filters>) => void;
  onReset: () => void;
}

/**
 * Horizontal row of removable chips showing every active filter.
 * Only renders when there's at least one non-default filter active.
 */
export function FilterChips({ filters, onChange, onReset }: Props) {
  const chips: { label: string; onRemove: () => void }[] = [];

  if (filters.search)
    chips.push({ label: `"${filters.search}"`, onRemove: () => onChange({ search: "" }) });
  if (filters.brand)
    chips.push({ label: filters.brand, onRemove: () => onChange({ brand: null }) });
  if (filters.minPrice != null)
    chips.push({ label: `min ৳${filters.minPrice.toLocaleString()}`, onRemove: () => onChange({ minPrice: null }) });
  if (filters.maxPrice != null)
    chips.push({ label: `max ৳${filters.maxPrice.toLocaleString()}`, onRemove: () => onChange({ maxPrice: null }) });
  if (!filters.inStockOnly)
    chips.push({ label: "Including out-of-stock", onRemove: () => onChange({ inStockOnly: true }) });
  if (filters.bundleOnly)
    chips.push({ label: "Bundle only", onRemove: () => onChange({ bundleOnly: false }) });
  if (filters.sort !== "store_count_desc") {
    const labels: Record<string, string> = {
      price_asc: "Price ↑", price_desc: "Price ↓", savings_desc: "Biggest savings", name: "Name A–Z",
    };
    chips.push({ label: labels[filters.sort] ?? filters.sort, onRemove: () => onChange({ sort: "store_count_desc" }) });
  }
  for (const [k, v] of Object.entries(filters.specs)) {
    if (v === undefined || v === null || v === "") continue;
    const label = v === true ? humanizeKey(k) : `${humanizeKey(k)}: ${v}`;
    chips.push({
      label,
      onRemove: () => onChange({ specs: { ...filters.specs, [k]: undefined } }),
    });
  }

  if (chips.length === 0) return null;

  return (
    <div className="no-scrollbar -mx-1 mb-4 flex flex-wrap gap-2 overflow-x-auto px-1">
      {chips.map((c, i) => (
        <span
          key={i}
          className="flex items-center gap-1.5 rounded-full border border-brand/30 bg-brand-strong/10 px-2.5 py-1 text-[11px] font-medium text-brand"
        >
          {c.label}
          <button
            onClick={c.onRemove}
            className="rounded-full p-0.5 hover:bg-brand-strong/20"
            aria-label={`Remove ${c.label} filter`}
          >
            <X className="h-3 w-3" />
          </button>
        </span>
      ))}
      {chips.length > 1 && (
        <button
          onClick={onReset}
          className="rounded-full border border-line px-2.5 py-1 text-[11px] font-medium text-ink-3 hover:text-brand"
        >
          Clear all
        </button>
      )}
    </div>
  );
}
