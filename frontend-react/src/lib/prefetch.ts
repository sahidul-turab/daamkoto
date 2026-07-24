/**
 * Speculative fetching for the browse view.
 *
 * The product list for a category is ~4 KB gzipped and the backend serves it
 * from a warm cache, so fetching a handful the user has not clicked yet is
 * cheap. Doing it while the browser is otherwise idle turns a category switch
 * from "request, wait, paint" into a pure render.
 */
import { api } from "../api";
import { CATEGORIES, PAGE_SIZE, type CategoryDef } from "../config";
import { DEFAULT_FILTERS } from "./filterDefaults";

/** The exact query the app issues for a freshly-selected category. */
function defaultParams(categoryDb: string): Record<string, unknown> {
  return {
    category: categoryDb,
    in_stock_only: DEFAULT_FILTERS.inStockOnly,
    sort: DEFAULT_FILTERS.sort,
    limit: PAGE_SIZE,
    offset: 0,
  };
}

export function prefetchCategory(category: CategoryDef): void {
  api.prefetchProducts(defaultParams(category.db));
}

function whenIdle(fn: () => void, timeout: number): void {
  const ric = (window as unknown as {
    requestIdleCallback?: (cb: () => void, opts?: { timeout: number }) => number;
  }).requestIdleCallback;
  if (ric) ric(fn, { timeout });
  else window.setTimeout(fn, timeout);
}

/**
 * Warm every category tab once the page has settled.
 *
 * Staggered rather than fired in one burst: 13 parallel requests would compete
 * with whatever the user actually asked for, and on a slow connection that
 * makes the visible page slower, not faster. Skips entirely when the browser
 * reports a slow or metered connection — speculative traffic is a bad trade
 * when bytes are scarce, which is a real constraint for a lot of this site's
 * users on mobile data.
 */
export function prefetchAllCategories(activeDb: string): () => void {
  const conn = (navigator as unknown as {
    connection?: { saveData?: boolean; effectiveType?: string };
  }).connection;
  if (conn?.saveData) return () => void 0;
  if (conn?.effectiveType && /(^|-)2g$/.test(conn.effectiveType)) return () => void 0;

  const queue = CATEGORIES.filter((c) => c.db !== activeDb);
  let i = 0;
  let cancelled = false;

  const step = () => {
    if (cancelled || i >= queue.length) return;
    prefetchCategory(queue[i++]);
    whenIdle(step, 400);
  };

  // Let the first real render and its data land before speculating.
  const start = window.setTimeout(() => whenIdle(step, 1000), 1200);

  return () => {
    cancelled = true;
    window.clearTimeout(start);
  };
}
