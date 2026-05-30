import type {
  ChatResponse,
  ProductHistory,
  ProductList,
  ProductSummary,
  ScraperStatus,
  SellerSpecs,
} from "./types";

// In dev, Vite proxies /api -> http://127.0.0.1:8000 (see vite.config.ts).
// Override with VITE_API_BASE for a deployed backend.
const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "/api";

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function get<T>(path: string, params?: Record<string, unknown>): Promise<T> {
  const url = new URL(BASE + path, window.location.origin);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v === undefined || v === null || v === "") continue;
      url.searchParams.set(k, String(v));
    }
  }
  const res = await fetch(url.toString());
  if (!res.ok) throw new ApiError(res.status, `${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  health: () => get<{ status: string }>("/health"),

  categories: () => get<string[]>("/categories"),

  brands: (category?: string) => get<string[]>("/brands", { category }),

  retailers: () => get<unknown[]>("/retailers"),

  specValues: (category: string, key: string) =>
    get<string[]>("/specs/values", { category, key }),

  products: (params: Record<string, unknown>) =>
    get<ProductList>("/products", params),

  product: (id: number) => get<ProductSummary>(`/products/${id}`),

  sellerSpecs: (id: number) => get<SellerSpecs>(`/products/${id}/seller-specs`),

  history: (id: number, retailer?: string) =>
    get<ProductHistory>(`/products/${id}/history`, { retailer, limit: 500 }),

  chat: async (
    message: string,
    history: { role: string; content: string }[],
  ): Promise<ChatResponse> => {
    const res = await fetch(new URL(BASE + "/chat", window.location.origin), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history }),
    });
    if (!res.ok) throw new ApiError(res.status, `/chat → ${res.status}`);
    return res.json() as Promise<ChatResponse>;
  },

  scraperStatus: () => get<ScraperStatus>("/scrapers/status"),

  triggerRun: async (
    category: string,
    retailers: string[],
  ): Promise<{ run_id: number; status: string }> => {
    const res = await fetch(new URL(BASE + "/scrapers/run", window.location.origin), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category, retailers }),
    });
    if (!res.ok) throw new ApiError(res.status, `/scrapers/run → ${res.status}`);
    return res.json() as Promise<{ run_id: number; status: string }>;
  },
};

export { ApiError };
