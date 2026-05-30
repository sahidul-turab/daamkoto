import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { PAGE_SIZE } from "../config";
import type { Filters, ProductSummary } from "../types";

export function useProductSearch(
  categoryDb: string,
  filters: Filters,
  page: number,
): { products: ProductSummary[]; total: number; loading: boolean } {
  const [products, setProducts] = useState<ProductSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const reqId = useRef(0);

  const params = useMemo(() => {
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
  }, [categoryDb, filters, page]);

  const sig = JSON.stringify(params);

  useEffect(() => {
    const id = ++reqId.current;
    setLoading(true);
    const handle = setTimeout(() => {
      api
        .products(params)
        .then((res) => {
          if (id !== reqId.current) return;
          setProducts(res.products);
          setTotal(res.total);
        })
        .catch(() => {
          if (id !== reqId.current) return;
          setProducts([]);
          setTotal(0);
        })
        .finally(() => {
          if (id === reqId.current) setLoading(false);
        });
    }, 220);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sig]);

  return { products, total, loading };
}
