import type {
  Alert,
  AdminLoginResponse,
  ChatContext,
  ChatResponse,
  Deal,
  ProductHistory,
  ProductList,
  ProductSummary,
  ScraperStatus,
  SellerSpecs,
} from "./types";
import { prefetch as swrPrefetch, swr } from "./lib/swr";

// In dev, Vite proxies /api -> http://127.0.0.1:8000 (see vite.config.ts).
// Override with VITE_API_BASE for a deployed backend.
const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "/api";

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

/**
 * Build the request URL for a GET endpoint.
 *
 * Exported because it doubles as the cache key: two calls that produce the same
 * URL are the same request, which is exactly the identity the SWR layer needs.
 * Params are sorted so key order in the caller can never split the cache.
 */
export function buildUrl(path: string, params?: Record<string, unknown>): string {
  const url = new URL(BASE + path, window.location.origin);
  if (params) {
    for (const [k, v] of Object.entries(params).sort(([a], [b]) => a.localeCompare(b))) {
      if (v === undefined || v === null || v === "") continue;
      if (Array.isArray(v)) {
        // Multi-select → repeated params (?k=a&k=b). Sorted so the selection
        // order can never split the cache: this URL doubles as the cache key.
        for (const item of [...v].filter((x) => x !== "" && x != null).sort())
          url.searchParams.append(k, String(item));
      } else {
        url.searchParams.set(k, String(v));
      }
    }
  }
  return url.toString();
}

/**
 * Resolve a backend-relative asset path (e.g. a "/media/..." cutout) against the
 * same origin the API uses — the "/api" dev proxy or VITE_API_BASE in prod.
 * Absolute URLs are returned unchanged.
 */
export function assetUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  return BASE + path;
}

async function fetchJson<T>(url: string, label: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new ApiError(res.status, `${label} → ${res.status}`);
  return res.json() as Promise<T>;
}

async function get<T>(path: string, params?: Record<string, unknown>): Promise<T> {
  return fetchJson<T>(buildUrl(path, params), path);
}

async function adminRequest<T>(
  path: string,
  token: string,
  method: "GET" | "POST" | "DELETE" = "GET",
  body?: unknown,
): Promise<T> {
  const res = await fetch(new URL(BASE + path, window.location.origin), {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
  if (!res.ok) throw new ApiError(res.status, `${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

/** Same as `get`, but served through the client cache (see lib/swr.ts). */
function cachedGet<T>(
  path: string,
  params?: Record<string, unknown>,
  onData?: (data: T, isStale: boolean) => void,
): Promise<T> {
  const url = buildUrl(path, params);
  return swr<T>(url, () => fetchJson<T>(url, path), onData);
}

export const api = {
  health: () => get<{ status: string }>("/health"),

  adminLogin: async (password: string) => {
    const res = await fetch(new URL(BASE + "/admin/login", window.location.origin), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
      cache: "no-store",
    });
    if (!res.ok) throw new ApiError(res.status, `/admin/login → ${res.status}`);
    return res.json() as Promise<AdminLoginResponse>;
  },

  adminSession: (token: string) =>
    adminRequest<{ authenticated: boolean }>("/admin/session", token),

  adminLogout: (token: string) =>
    adminRequest<{ authenticated: boolean }>("/admin/session", token, "DELETE"),

  categories: () => cachedGet<string[]>("/categories"),

  brands: (category?: string) => cachedGet<string[]>("/brands", { category }),

  retailers: () => cachedGet<unknown[]>("/retailers"),

  specValues: (category: string, key: string) =>
    cachedGet<string[]>("/specs/values", { category, key }),

  /**
   * Product search. `onData` fires up to twice: once with cached data (possibly
   * stale) so the grid can paint immediately, then once more when the network
   * response lands. Callers that just want the final value can await instead.
   */
  products: (
    params: Record<string, unknown>,
    onData?: (data: ProductList, isStale: boolean) => void,
  ) => cachedGet<ProductList>("/products", params, onData),

  /** Warm the cache for a product query the user has not asked for yet. */
  prefetchProducts: (params: Record<string, unknown>) => {
    const url = buildUrl("/products", params);
    swrPrefetch(url, () => fetchJson<ProductList>(url, "/products"));
  },

  product: (id: number) => cachedGet<ProductSummary>(`/products/${id}`),

  sellerSpecs: (id: number) => cachedGet<SellerSpecs>(`/products/${id}/seller-specs`),

  history: (id: number, retailer?: string) =>
    cachedGet<ProductHistory>(`/products/${id}/history`, { retailer, limit: 500 }),

  chat: async (
    message: string,
    history: { role: string; content: string }[],
    context?: ChatContext,
  ): Promise<ChatResponse> => {
    const res = await fetch(new URL(BASE + "/chat", window.location.origin), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history, context }),
    });
    if (!res.ok) throw new ApiError(res.status, `/chat → ${res.status}`);
    return res.json() as Promise<ChatResponse>;
  },

  // ── Deals ────────────────────────────────────────────────────────────────

  deals: (params?: { category?: string; limit?: number }) =>
    cachedGet<{ deals: Deal[]; count: number }>("/deals", params),

  // ── Build plan / check ───────────────────────────────────────────────────

  planBuild: async (params: {
    budget_bdt: number;
    use_case?: string;
    socket_preference?: string;
    include_gpu?: boolean;
  }) => {
    const res = await fetch(new URL(BASE + "/build/plan", window.location.origin), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    });
    if (!res.ok) throw new ApiError(res.status, `/build/plan → ${res.status}`);
    return res.json();
  },

  checkBuild: async (slots: {
    cpu_id?: number; mobo_id?: number; ram_id?: number;
    gpu_id?: number; psu_id?: number; case_id?: number;
    cooler_id?: number; storage_id?: number;
  }) => {
    const res = await fetch(new URL(BASE + "/build/check", window.location.origin), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(slots),
    });
    if (!res.ok) throw new ApiError(res.status, `/build/check → ${res.status}`);
    return res.json();
  },

  // ── Alerts ───────────────────────────────────────────────────────────────

  createAlert: async (deviceId: string, productId: number, targetPrice: number) => {
    const res = await fetch(new URL(BASE + "/alerts", window.location.origin), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_id: deviceId, product_id: productId, target_price: targetPrice }),
    });
    if (!res.ok) throw new ApiError(res.status, `/alerts → ${res.status}`);
    return res.json() as Promise<Alert>;
  },

  listAlerts: (deviceId: string) =>
    get<Alert[]>("/alerts", { device_id: deviceId }),

  deleteAlert: async (deviceId: string, alertId: number) => {
    const res = await fetch(
      new URL(BASE + `/alerts/${alertId}?device_id=${encodeURIComponent(deviceId)}`, window.location.origin),
      { method: "DELETE" },
    );
    if (!res.ok) throw new ApiError(res.status, `/alerts/${alertId} → ${res.status}`);
    return res.json();
  },

  triggeredAlerts: (deviceId: string) =>
    get<Alert[]>("/alerts/triggered", { device_id: deviceId }),

  // ── Scraper ──────────────────────────────────────────────────────────────

  scraperStatus: (token: string) =>
    adminRequest<ScraperStatus>("/scrapers/status", token),

  triggerRun: async (
    token: string,
    category: string,
    retailers: string[],
  ): Promise<{ run_id: number; status: string }> => {
    return adminRequest<{ run_id: number; status: string }>(
      "/scrapers/run",
      token,
      "POST",
      { category, retailers },
    );
  },
};

export { ApiError };
