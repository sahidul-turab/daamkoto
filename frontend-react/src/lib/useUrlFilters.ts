/**
 * Keeps the active category + filter state in the URL search params so that:
 *  - every filtered search is a shareable link
 *  - the browser back/forward buttons work correctly
 *  - page refresh restores the exact same view
 *
 * We use `history.replaceState` so filter effects never create duplicate
 * history entries. App.tsx owns view/category navigation and pushes one clean
 * entry for the action the user actually took.
 */
import { useCallback, useEffect, useState } from "react";
import { CATEGORIES, PAGE_SIZE, type CategoryDef } from "../config";
import type { Filters } from "../types";
import { DEFAULT_FILTERS } from "./filterDefaults";

const DEFAULTS = DEFAULT_FILTERS;

function categoryFromDb(db: string): CategoryDef {
  return CATEGORIES.find((c) => c.db === db) ?? CATEGORIES[0];
}

// Encode all active filter + category state into a URLSearchParams string.
function encode(cat: CategoryDef, filters: Filters, page: number): string {
  const p = new URLSearchParams();
  if (cat.db !== CATEGORIES[0].db) p.set("cat", cat.db);
  if (filters.search) p.set("q", filters.search);
  if (filters.brand) p.set("brand", filters.brand);
  if (filters.minPrice != null) p.set("min", String(filters.minPrice));
  if (filters.maxPrice != null) p.set("max", String(filters.maxPrice));
  if (!filters.inStockOnly) p.set("stock", "0");
  if (filters.bundleOnly) p.set("bundle", "1");
  if (filters.sort !== DEFAULTS.sort) p.set("sort", filters.sort);
  if (page > 1) p.set("page", String(page));
  for (const [k, v] of Object.entries(filters.specs)) {
    if (v === undefined || v === null || v === "") continue;
    if (Array.isArray(v)) {
      // Multi-select → one spec_ param per ticked value, so the URL round-trips.
      for (const item of v) if (item !== "" && item != null) p.append(`spec_${k}`, String(item));
    } else {
      p.set(`spec_${k}`, String(v));
    }
  }
  return p.toString();
}

// Decode URLSearchParams back to (category, filters, page).
function decode(raw: string): { cat: CategoryDef; filters: Filters; page: number } {
  const p = new URLSearchParams(raw);
  const cat = categoryFromDb(p.get("cat") ?? CATEGORIES[0].db);
  const specs: Record<string, string | string[] | boolean> = {};
  // A spec_ key may appear multiple times (multi-select). A lone "true"/"false"
  // is a boolean toggle; anything else is collected into a string[] group.
  const specKeys = new Set<string>();
  for (const k of p.keys()) if (k.startsWith("spec_")) specKeys.add(k.slice(5));
  for (const key of specKeys) {
    const vals = p.getAll(`spec_${key}`);
    if (vals.length === 1 && (vals[0] === "true" || vals[0] === "false")) {
      specs[key] = vals[0] === "true";
    } else {
      specs[key] = vals;
    }
  }
  const filters: Filters = {
    search: p.get("q") ?? "",
    brand: p.get("brand") ?? null,
    minPrice: p.has("min") ? Number(p.get("min")) : null,
    maxPrice: p.has("max") ? Number(p.get("max")) : null,
    inStockOnly: p.get("stock") !== "0",
    bundleOnly: p.get("bundle") === "1",
    sort: p.get("sort") ?? DEFAULTS.sort,
    specs,
  };
  const page = Math.max(1, Number(p.get("page") ?? 1));
  return { cat, filters, page };
}

export function useUrlFilters() {
  const initial = decode(window.location.search.slice(1));
  const [category, setCategory] = useState<CategoryDef>(initial.cat);
  const [filters, setFilters] = useState<Filters>(initial.filters);
  const [page, setPage] = useState(initial.page);

  // Keep URL in sync without adding a second entry after App navigation.
  useEffect(() => {
    const qs = encode(category, filters, page);
    const pathAndQuery = qs ? `${window.location.pathname}?${qs}` : window.location.pathname;
    const url = `${pathAndQuery}${window.location.hash}`;
    window.history.replaceState(null, "", url);
  }, [category, filters, page]);

  // Handle browser back/forward.
  useEffect(() => {
    const onPop = () => {
      const { cat, filters: f, page: pg } = decode(window.location.search.slice(1));
      setCategory(cat);
      setFilters(f);
      setPage(pg);
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const onSelectCategory = useCallback((c: CategoryDef) => {
    setCategory(c);
    setPage(1);
    setFilters((f) => ({ ...f, brand: null, specs: {} }));
  }, []);

  const patchFilters = useCallback((patch: Partial<Filters>) => {
    setFilters((f) => ({ ...f, ...patch }));
    setPage(1);
  }, []);

  const resetFilters = useCallback(() => {
    setFilters(DEFAULTS);
    setPage(1);
  }, []);

  const totalPages = useCallback(
    (total: number) => Math.max(1, Math.ceil(total / PAGE_SIZE)),
    [],
  );

  return {
    category, filters, page, setPage,
    onSelectCategory, patchFilters, resetFilters, totalPages,
  };
}
