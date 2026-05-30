import { useCallback, useState } from "react";
import type { ProductSummary } from "../types";

const KEY = "daamkoto:watchlist:v1";

function load(): ProductSummary[] {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as ProductSummary[]) : [];
  } catch {
    return [];
  }
}

function save(items: ProductSummary[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(items));
  } catch {
    /* ignore quota errors */
  }
}

export function useWatchlist() {
  const [items, setItems] = useState<ProductSummary[]>(() => load());

  const isWatched = useCallback(
    (id: number) => items.some((p) => p.id === id),
    [items],
  );

  const toggle = useCallback((product: ProductSummary) => {
    setItems((prev) => {
      const next = prev.some((p) => p.id === product.id)
        ? prev.filter((p) => p.id !== product.id)
        : [product, ...prev].slice(0, 50); // cap at 50 items
      save(next);
      return next;
    });
  }, []);

  const remove = useCallback((id: number) => {
    setItems((prev) => {
      const next = prev.filter((p) => p.id !== id);
      save(next);
      return next;
    });
  }, []);

  return { items, isWatched, toggle, remove, count: items.length };
}
