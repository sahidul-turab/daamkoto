import { useEffect, useMemo, useRef, useState } from "react";
import { api, buildUrl } from "../api";
import { peek } from "./swr";
import { PAGE_SIZE } from "../config";
import type { Filters, ProductSummary } from "../types";

/**
 * Debounce only exists to stop a request firing on every keystroke in the search
 * box. Applying it to everything — as this hook used to — meant clicking a
 * category tab sat on its hands for a fifth of a second before it even asked the
 * server, on top of the round trip. Structural changes go out immediately;
 * only free-text typing waits.
 */
const TYPING_DEBOUNCE_MS = 200;

function toParams(
  categoryDb: string,
  filters: Filters,
  page: number,
): Record<string, unknown> {
  const p: Record<string, unknown> = {
    category: categoryDb,
    search: filters.search || undefined,
    brand: filters.brand || undefined,
    min_price: filters.minPrice ?? undefined,
    max_price: filters.maxPrice ?? undefined,
    in_stock_only: filters.inStockOnly,
    sort: filters.sort,
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
  };
  for (const [k, v] of Object.entries(filters.specs)) {
    if (v !== undefined && v !== null && v !== "") p[k] = v;
  }
  return p;
}

export function useProductSearch(
  categoryDb: string,
  filters: Filters,
  page: number,
): { products: ProductSummary[]; total: number; loading: boolean } {
  const params = useMemo(
    () => toParams(categoryDb, filters, page),
    [categoryDb, filters, page],
  );
  const sig = buildUrl("/products", params);

  // Seed from cache during render, so a revisited category paints with real
  // products on the first frame instead of a skeleton that resolves 200ms later.
  const cached = peek<{ products: ProductSummary[]; total: number }>(sig);
  const [products, setProducts] = useState<ProductSummary[]>(cached?.products ?? []);
  const [total, setTotal] = useState(cached?.total ?? 0);
  const [loading, setLoading] = useState(cached === null);

  const reqId = useRef(0);
  const prevSearch = useRef(filters.search);

  useEffect(() => {
    const id = ++reqId.current;

    // A cache hit means we already have something worth showing. Render it now
    // and let the revalidation swap in quietly — no loading state at all.
    const hit = peek<{ products: ProductSummary[]; total: number }>(sig);
    if (hit) {
      setProducts(hit.products);
      setTotal(hit.total);
      setLoading(false);
    } else {
      setLoading(true);
    }

    const typing = filters.search !== prevSearch.current;
    prevSearch.current = filters.search;

    const fire = () => {
      api
        .products(params, (res, isStale) => {
          if (id !== reqId.current) return;
          setProducts(res.products);
          setTotal(res.total);
          if (!isStale) setLoading(false);
          // Paging is the most predictable move a browsing user makes, so the
          // next page is fetched while they are still reading this one.
          if (!isStale && page * PAGE_SIZE < res.total) {
            api.prefetchProducts(toParams(categoryDb, filters, page + 1));
          }
        })
        .catch(() => {
          if (id !== reqId.current) return;
          // Keep whatever is on screen if we had a cached copy; a failed
          // revalidation should not blank out a working page.
          if (!hit) {
            setProducts([]);
            setTotal(0);
          }
        })
        .finally(() => {
          if (id === reqId.current) setLoading(false);
        });
    };

    if (!typing || hit) {
      fire();
      return;
    }
    const handle = setTimeout(fire, TYPING_DEBOUNCE_MS);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sig]);

  return { products, total, loading };
}
