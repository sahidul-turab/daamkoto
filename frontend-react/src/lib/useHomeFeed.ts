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
      const products = (result?.products ?? []).filter((product) => {
        const key = product.match_key || String(product.id);
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      }).slice(0, 4);
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
      const next = snapshot?.sections?.length
        ? snapshot.sections
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
