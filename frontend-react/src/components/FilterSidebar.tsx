import { useEffect, useState } from "react";
import { RotateCcw, SlidersHorizontal, X } from "lucide-react";
import { api } from "../api";
import { SORT_OPTIONS, type CategoryDef, type SelectFilter } from "../config";
import type { Filters } from "../types";

interface Props {
  category: CategoryDef;
  filters: Filters;
  onChange: (patch: Partial<Filters>) => void;
  onReset: () => void;
  resultCount: number;
  onClose?: () => void;
}

interface FilterToggleProps {
  label: string;
  enabled: boolean;
  onToggle: () => void;
}

function FilterToggle({ label, enabled, onToggle }: FilterToggleProps) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-sm font-medium text-ink-2">{label}</span>
      <button
        type="button"
        role="switch"
        aria-label={label}
        aria-checked={enabled}
        onClick={onToggle}
        className={`inline-flex h-6 w-11 shrink-0 items-center overflow-hidden rounded-full p-0.5 transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/70 ${
          enabled ? "bg-brand-strong" : "bg-line-2"
        }`}
      >
        <span
          aria-hidden="true"
          className={`block h-5 w-5 shrink-0 rounded-full bg-white shadow-sm transition-transform duration-200 ${
            enabled ? "translate-x-5" : "translate-x-0"
          }`}
        />
      </button>
    </div>
  );
}

// A multi-select spec filter: a scrollable group of checkboxes whose options are
// lazily loaded from the API (with a static fallback). Ticking several boxes ORs
// them, matching how StarTech's filter sidebar behaves.
function SpecMultiSelect({
  category,
  filter,
  value,
  onChange,
}: {
  category: string;
  filter: SelectFilter;
  value: string | string[] | undefined;
  onChange: (v: string[] | undefined) => void;
}) {
  const [options, setOptions] = useState<string[]>(filter.fallback);
  const [query, setQuery] = useState("");

  useEffect(() => {
    let alive = true;
    api
      .specValues(category, filter.specKey)
      .then((vals) => {
        if (alive && vals && vals.length) setOptions(vals);
      })
      .catch(() => void 0);
    return () => {
      alive = false;
    };
  }, [category, filter.specKey]);

  // Tolerate a stray string (e.g. set by the chatbot) by coercing to an array.
  const selected = Array.isArray(value) ? value : value ? [String(value)] : [];

  const toggle = (opt: string) => {
    const next = selected.includes(opt)
      ? selected.filter((v) => v !== opt)
      : [...selected, opt];
    onChange(next.length ? next : undefined);
  };

  const q = query.trim().toLowerCase();
  const shown = q ? options.filter((o) => o.toLowerCase().includes(q)) : options;
  const showSearch = options.length > 10;

  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between">
        <label className="label !mb-0">{filter.label}</label>
        {selected.length > 0 && (
          <button
            onClick={() => onChange(undefined)}
            className="text-[10px] font-medium text-ink-3 hover:text-brand"
          >
            Clear ({selected.length})
          </button>
        )}
      </div>
      {showSearch && (
        <input
          className="field !mb-1.5 !py-1 text-xs"
          placeholder={`Search ${filter.label.toLowerCase()}…`}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      )}
      <div className="max-h-44 overflow-y-auto overscroll-contain rounded-xl border border-line bg-surface-2 p-1">
        {shown.length === 0 ? (
          <div className="px-2 py-1.5 text-xs text-ink-4">No matches</div>
        ) : (
          shown.map((o) => {
            const on = selected.includes(o);
            return (
              <label
                key={o}
                className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1 text-sm hover:bg-line/40"
              >
                <input
                  type="checkbox"
                  checked={on}
                  onChange={() => toggle(o)}
                  className="h-3.5 w-3.5 shrink-0 accent-brand-strong"
                />
                <span className={on ? "font-medium text-ink" : "text-ink-2"}>{o}</span>
              </label>
            );
          })
        )}
      </div>
    </div>
  );
}

export function FilterSidebar({
  category,
  filters,
  onChange,
  onReset,
  resultCount,
  onClose,
}: Props) {
  const [brands, setBrands] = useState<string[]>([]);

  useEffect(() => {
    let alive = true;
    api
      .brands(category.db)
      .then((b) => alive && setBrands(b ?? []))
      .catch(() => alive && setBrands([]));
    return () => {
      alive = false;
    };
  }, [category.db]);

  const setSpec = (param: string, v: string | string[] | boolean | undefined) => {
    const val = Array.isArray(v) ? (v.length ? v : undefined) : v || undefined;
    onChange({ specs: { ...filters.specs, [param]: val } });
  };

  return (
    <aside className="glass flex flex-col gap-5 p-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-bold">
          <SlidersHorizontal className="h-4 w-4 text-brand" />
          Filters
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={onReset}
            className="flex items-center gap-1 px-1 text-xs font-medium text-ink-3 transition-colors hover:text-brand"
          >
            <RotateCcw className="h-3 w-3" />
            Reset
          </button>
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="grid h-8 w-8 place-items-center rounded-lg border border-line bg-surface-2 text-ink-3 hover:text-ink"
              aria-label="Close filters"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Sort */}
      <div>
        <label className="label">Sort By</label>
        <select
          className="field"
          value={filters.sort}
          onChange={(e) => onChange({ sort: e.target.value })}
        >
          {SORT_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>

      {/* Brand */}
      <div>
        <label className="label">Brand</label>
        <select
          className="field"
          value={filters.brand ?? ""}
          onChange={(e) => onChange({ brand: e.target.value || null })}
        >
          <option value="">All Brands</option>
          {brands.map((b) => (
            <option key={b} value={b}>
              {b}
            </option>
          ))}
        </select>
      </div>

      {/* Price range */}
      <div>
        <label className="label">Price Range ৳</label>
        <div className="flex items-center gap-2">
          <input
            type="number"
            min={0}
            placeholder="Min"
            className="field"
            value={filters.minPrice ?? ""}
            onChange={(e) =>
              onChange({ minPrice: e.target.value ? Number(e.target.value) : null })
            }
          />
          <span className="text-ink-4">–</span>
          <input
            type="number"
            min={0}
            placeholder="Max"
            className="field"
            value={filters.maxPrice ?? ""}
            onChange={(e) =>
              onChange({ maxPrice: e.target.value ? Number(e.target.value) : null })
            }
          />
        </div>
      </div>

      {/* In-stock toggle */}
      <FilterToggle
        label="In Stock Only"
        enabled={filters.inStockOnly}
        onToggle={() => onChange({ inStockOnly: !filters.inStockOnly })}
      />

      {/* Bundle-only toggle */}
      <FilterToggle
        label="Bundle Only"
        enabled={filters.bundleOnly}
        onToggle={() => onChange({ bundleOnly: !filters.bundleOnly })}
      />

      {/* Category-specific specs */}
      <div className="border-t border-line pt-4">
        <div className="label !mb-3">Specifications</div>
        <div className="flex flex-col gap-4">
          {category.filters.map((f) =>
            f.kind === "select" ? (
              <SpecMultiSelect
                key={f.param}
                category={category.db}
                filter={f}
                value={filters.specs[f.param] as string | string[] | undefined}
                onChange={(v) => setSpec(f.param, v)}
              />
            ) : (
              <FilterToggle
                key={f.param}
                label={f.label}
                enabled={Boolean(filters.specs[f.param])}
                onToggle={() => setSpec(f.param, !filters.specs[f.param])}
              />
            ),
          )}
        </div>
      </div>

      <div className="rounded-xl border border-line bg-surface-2 px-3 py-2.5 text-center text-xs text-ink-3">
        <span className="font-bold text-ink">{resultCount.toLocaleString()}</span>{" "}
        products match
      </div>
    </aside>
  );
}
