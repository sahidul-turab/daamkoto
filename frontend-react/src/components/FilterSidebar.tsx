import { useEffect, useState } from "react";
import { RotateCcw, SlidersHorizontal } from "lucide-react";
import { api } from "../api";
import { SORT_OPTIONS, type CategoryDef, type SelectFilter } from "../config";
import type { Filters } from "../types";

interface Props {
  category: CategoryDef;
  filters: Filters;
  onChange: (patch: Partial<Filters>) => void;
  onReset: () => void;
  resultCount: number;
}

// A single spec <select> that lazily loads its real options from the API.
function SpecSelect({
  category,
  filter,
  value,
  onChange,
}: {
  category: string;
  filter: SelectFilter;
  value: string | undefined;
  onChange: (v: string | undefined) => void;
}) {
  const [options, setOptions] = useState<string[]>(filter.fallback);

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

  return (
    <div>
      <label className="label">{filter.label}</label>
      <select
        className="field"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value || undefined)}
      >
        <option value="">All {filter.label}</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </div>
  );
}

export function FilterSidebar({
  category,
  filters,
  onChange,
  onReset,
  resultCount,
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

  const setSpec = (param: string, v: string | boolean | undefined) =>
    onChange({ specs: { ...filters.specs, [param]: v || undefined } });

  return (
    <aside className="glass flex flex-col gap-5 p-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-bold">
          <SlidersHorizontal className="h-4 w-4 text-brand" />
          Filters
        </div>
        <button
          onClick={onReset}
          className="flex items-center gap-1 text-xs font-medium text-ink-3 transition-colors hover:text-brand"
        >
          <RotateCcw className="h-3 w-3" />
          Reset
        </button>
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
      <label className="flex cursor-pointer items-center justify-between">
        <span className="text-sm font-medium text-ink-2">In Stock Only</span>
        <button
          type="button"
          role="switch"
          aria-checked={filters.inStockOnly}
          onClick={() => onChange({ inStockOnly: !filters.inStockOnly })}
          className={`relative h-6 w-11 rounded-full transition-colors duration-200 ${
            filters.inStockOnly ? "bg-brand-strong" : "bg-line-2"
          }`}
        >
          <span
            className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform duration-200 ${
              filters.inStockOnly ? "translate-x-5" : "translate-x-0.5"
            }`}
          />
        </button>
      </label>

      {/* Bundle-only toggle */}
      <label className="flex cursor-pointer items-center justify-between">
        <span className="text-sm font-medium text-ink-2">Bundle Only</span>
        <button
          type="button"
          role="switch"
          aria-checked={filters.bundleOnly}
          onClick={() => onChange({ bundleOnly: !filters.bundleOnly })}
          className={`relative h-6 w-11 rounded-full transition-colors duration-200 ${
            filters.bundleOnly ? "bg-brand-strong" : "bg-line-2"
          }`}
        >
          <span
            className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform duration-200 ${
              filters.bundleOnly ? "translate-x-5" : "translate-x-0.5"
            }`}
          />
        </button>
      </label>

      {/* Category-specific specs */}
      <div className="border-t border-line pt-4">
        <div className="label !mb-3">Specifications</div>
        <div className="flex flex-col gap-4">
          {category.filters.map((f) =>
            f.kind === "select" ? (
              <SpecSelect
                key={f.param}
                category={category.db}
                filter={f}
                value={filters.specs[f.param] as string | undefined}
                onChange={(v) => setSpec(f.param, v)}
              />
            ) : (
              <label
                key={f.param}
                className="flex cursor-pointer items-center justify-between"
              >
                <span className="text-sm font-medium text-ink-2">{f.label}</span>
                <button
                  type="button"
                  role="switch"
                  aria-checked={Boolean(filters.specs[f.param])}
                  onClick={() => setSpec(f.param, !filters.specs[f.param])}
                  className={`relative h-6 w-11 rounded-full transition-colors duration-200 ${
                    filters.specs[f.param] ? "bg-brand-strong" : "bg-line-2"
                  }`}
                >
                  <span
                    className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform duration-200 ${
                      filters.specs[f.param] ? "translate-x-5" : "translate-x-0.5"
                    }`}
                  />
                </button>
              </label>
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
