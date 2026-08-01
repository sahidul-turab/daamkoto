import { PAGE_SIZE } from "../config";
import type { HomeSnapshot, ProductList } from "../types";

/**
 * Database-generated first pages published after every daily scrape.
 *
 * Render may be asleep when a new visitor arrives. These small JSON files are
 * served from the existing Cloudflare Worker, so Browse can paint products
 * immediately while the live API wakes and replaces the snapshot underneath.
 */
export const SNAPSHOT_BASE = (
  (import.meta.env.VITE_SNAPSHOT_BASE as string | undefined) ||
  "https://daamkoto-img.sahidulturab81.workers.dev"
).replace(/\/$/, "");

const SNAPSHOT_SORTS = new Set(["store_count_desc", "price_asc"]);
const BASE_PARAMS = new Set([
  "category",
  "in_stock_only",
  "sort",
  "limit",
  "offset",
]);
const FETCH_TIMEOUT_MS = 5_000;
const CACHE_BUCKET_MS = 6 * 60 * 60 * 1000;

function hasValue(value: unknown): boolean {
  if (value === undefined || value === null || value === "") return false;
  if (Array.isArray(value)) return value.length > 0;
  return true;
}

function categorySlug(category: string): string {
  // Keep this identical to scripts/export_bootstrap_snapshots.py.
  return category.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
}

function snapshotUrl(params: Record<string, unknown>): string | null {
  const category = typeof params.category === "string" ? params.category : "";
  const sort = typeof params.sort === "string" ? params.sort : "";

  if (
    !category ||
    !SNAPSHOT_SORTS.has(sort) ||
    params.in_stock_only !== true ||
    params.limit !== PAGE_SIZE ||
    params.offset !== 0
  ) {
    return null;
  }

  // A snapshot represents only the default unfiltered page. Any meaningful
  // search, price, brand or spec value must go to the live API.
  for (const [key, value] of Object.entries(params)) {
    if (!BASE_PARAMS.has(key) && hasValue(value)) return null;
  }

  // The deployed image Worker historically marked every object immutable.
  // A six-hour URL bucket prevents an old snapshot sticking in a browser cache
  // even before the Worker's snapshot-specific cache rule is redeployed.
  const version = Math.floor(Date.now() / CACHE_BUCKET_MS);
  return `${SNAPSHOT_BASE}/snapshots/v1/${categorySlug(category)}/${sort}.json?v=${version}`;
}

function isProductList(value: unknown): value is ProductList {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<ProductList>;
  return (
    typeof candidate.total === "number" &&
    typeof candidate.limit === "number" &&
    typeof candidate.offset === "number" &&
    Array.isArray(candidate.products)
  );
}

function isHomeSnapshot(value: unknown): value is HomeSnapshot {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<HomeSnapshot>;
  return (
    candidate.version === 1 &&
    typeof candidate.generated_at === "string" &&
    Array.isArray(candidate.sections) &&
    candidate.sections.every(
      (section) =>
        !!section &&
        typeof section.category === "string" &&
        typeof section.total === "number" &&
        Array.isArray(section.products),
    )
  );
}

let homeRequest: Promise<HomeSnapshot | null> | null = null;
let homeRequestBucket = -1;

/** One edge-cached request powers every product section on the homepage. */
export function fetchHomeSnapshot(force = false): Promise<HomeSnapshot | null> {
  const version = Math.floor(Date.now() / CACHE_BUCKET_MS);
  if (!force && homeRequest && homeRequestBucket === version) return homeRequest;

  homeRequestBucket = version;
  homeRequest = (async () => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
    try {
      const response = await fetch(
        `${SNAPSHOT_BASE}/snapshots/v1/home.json?v=${version}`,
        { cache: force ? "reload" : "force-cache", signal: controller.signal },
      );
      if (!response.ok) return null;
      const payload: unknown = await response.json();
      return isHomeSnapshot(payload) ? payload : null;
    } catch {
      return null;
    } finally {
      window.clearTimeout(timer);
    }
  })();
  return homeRequest;
}

/** Return null when the query is not snapshot-compatible or the edge is down. */
export async function fetchBootstrapProducts(
  params: Record<string, unknown>,
): Promise<ProductList | null> {
  const url = snapshotUrl(params);
  if (!url) return null;

  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const response = await fetch(url, {
      cache: "force-cache",
      signal: controller.signal,
    });
    if (!response.ok) return null;
    const payload: unknown = await response.json();
    return isProductList(payload) ? payload : null;
  } catch {
    return null;
  } finally {
    window.clearTimeout(timer);
  }
}
