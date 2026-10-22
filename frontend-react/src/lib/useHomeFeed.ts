import { useCallback, useEffect, useState } from "react";
import { CATEGORIES, PAGE_SIZE } from "../config";
import type { HomeSection } from "../types";
import { fetchBootstrapProducts, fetchHomeSnapshot } from "./bootstrap";
import { DEFAULT_FILTERS } from "./filterDefaults";

const FEATURED_CATEGORY_DBS = [
  "GPU",
  "PROCESSOR",
  "MOTHERBOARD",
  "RAM DESKTOP",
  "SSD",
  "MONITOR",
  "KEYBOARD",
  "MOUSE",
];

let fallbackRequest: Promise<HomeSection[]> | null = null;

const FEATURED_PRICE_CEILING: Record<string, number> = {
  GPU: 150_000,
  PROCESSOR: 80_000,
  MOTHERBOARD: 60_000,
  "RAM DESKTOP": 45_000,
  SSD: 50_000,
  MONITOR: 100_000,
  KEYBOARD: 25_000,
  MOUSE: 20_000,
};

function isTrustworthyFeaturedProduct(product: HomeSection["products"][number], category: string) {
  if (product.cheapest_price == null || product.retailer_count < 2) return false;
  if (product.cheapest_price > (FEATURED_PRICE_CEILING[category] ?? 150_000)) return false;
  const current = product.listings.filter((listing) => listing.in_stock && listing.price_bdt != null);
  if (!current.length) return false;
  const prices = current.map((listing) => listing.price_bdt as number);
  const cheapest = Math.min(...prices);
  const dearest = Math.max(...prices);
  // Extreme spreads are commonly bad matches or placeholder prices. They can
  // remain searchable, but should never be a visitor's first impression.
  return cheapest > 0 && dearest / cheapest <= 2.5;
}

function curate(products: HomeSection["products"], category: string) {
  return products
    .filter((product) => isTrustworthyFeaturedProduct(product, category))
    .sort((a, b) => b.retailer_count - a.retailer_count || (a.cheapest_price ?? Infinity) - (b.cheapest_price ?? Infinity))
    .slice(0, 4);
}

function fallbackSections(): Promise<HomeSection[]> {
  if (fallbackRequest) return fallbackRequest;
  fallbackRequest = Promise.all(
    FEATURED_CATEGORY_DBS.map(async (category) => {
      const result = await fetchBootstrapProducts({
        category,
        in_stock_only: DEFAULT_FILTERS.inStockOnly,
        sort: DEFAULT_FILTERS.sort,
        limit: PAGE_SIZE,
        offset: 0,
      });
      const seen = new Set<string>();
      const unique = (result?.products ?? []).filter((product) => {
        const key = product.match_key || String(product.id);
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      });
      const products = curate(unique, category);
      return { category, total: result?.total ?? 0, products };
    }),
  ).then((sections) => sections.filter((section) => section.products.length > 0));
  return fallbackRequest;
}

export function useHomeFeed() {
  const [sections, setSections] = useState<HomeSection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);

  const retry = useCallback(() => {
    fallbackRequest = null;
    setAttempt((value) => value + 1);
  }, []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(false);

    (async () => {
      const snapshot = await fetchHomeSnapshot(attempt > 0);
      const curatedSnapshot = snapshot?.sections
        ?.map((section) => ({ ...section, products: curate(section.products, section.category) }))
        .filter((section) => section.products.length > 0);
      const next = curatedSnapshot?.length
        ? curatedSnapshot
        : await fallbackSections();
      if (!active) return;
      setSections(next);
      setError(next.length === 0);
      setLoading(false);
    })().catch(() => {
      if (!active) return;
      setSections([]);
      setError(true);
      setLoading(false);
    });

    return () => {
      active = false;
    };
  }, [attempt]);

  return {
    sections,
    loading,
    error,
    retry,
    categories: CATEGORIES,
  };
}
