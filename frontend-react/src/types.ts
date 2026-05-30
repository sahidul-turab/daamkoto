// Mirrors the Pydantic response models in backend/main.py.

export interface Listing {
  retailer: string;
  price_bdt: number | null;
  in_stock: boolean;
  stock_status: "in_stock" | "out_of_stock" | "upcoming" | "bundle_only" | string;
  pc_bundle_only: boolean;
  product_url: string | null;
  scraped_at: string;
}

export interface ProductSummary {
  id: number;
  name: string;
  brand: string | null;
  match_key: string;
  model_number: string | null;
  category: string | null;
  specs: Record<string, unknown>;
  cheapest_price: number | null;
  cheapest_retailer: string | null;
  retailer_count: number;
  listings: Listing[];
}

export interface ProductList {
  total: number;
  limit: number;
  offset: number;
  products: ProductSummary[];
}

export interface PricePoint {
  retailer: string;
  price_bdt: number | null;
  in_stock: boolean;
  scraped_at: string;
}

export interface ProductHistory {
  product_id: number;
  product_name: string;
  history: PricePoint[];
}

export interface SellerSpecs {
  product_id: number;
  retailers: string[];
  shared: Record<string, string>;
  differing: Record<string, Record<string, string | null>>;
}

export interface ChatResponse {
  params: Record<string, unknown>;
  products: ProductSummary[];
  total: number;
  explanation: string;
}

// Filter state managed by the UI and serialized into /products query params.
export interface SpecParams {
  [key: string]: string | boolean | undefined;
}

// Scraper health dashboard types
export interface RetailerFreshness {
  retailer: string;
  last_scraped: string | null;
  product_count: number;
  price_rows: number;
}

export interface ScraperRun {
  id: number;
  category: string;
  retailers: string[];
  started_at: string;
  finished_at: string | null;
  status: "RUNNING" | "SUCCESS" | "FAILED";
  products_count: number;
  prices_count: number;
  error_message: string | null;
}

export interface ScraperStatus {
  active_runs: Record<string, number>;   // { category: run_id }
  recent_runs: ScraperRun[];
  freshness: RetailerFreshness[];
  log_tail: string;
}

export interface Filters {
  search: string;
  brand: string | null;
  minPrice: number | null;
  maxPrice: number | null;
  inStockOnly: boolean;
  bundleOnly: boolean;
  sort: string;
  specs: SpecParams;
}
