// Mirrors the Pydantic response models in backend/main.py.

export interface Listing {
  retailer: string;
  price_bdt: number | null;
  in_stock: boolean;
  stock_status: "in_stock" | "out_of_stock" | "upcoming" | "bundle_only" | string;
  pc_bundle_only: boolean;
  product_url: string | null;
  image_url?: string | null;
  image_cutout?: string | null;
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

// ── Agent response ────────────────────────────────────────────────────────

export type BlockType =
  | "product_list"
  | "product_detail"
  | "build_sheet"
  | "compat_report"
  | "price_history"
  | "deal_list";

export interface ProductListBlock {
  type: "product_list";
  title: string;
  total: number;
  products: ProductSummary[];
}

export interface BuildSlot {
  slot: string;
  category: string;
  product_id: number;
  product_name: string;
  brand: string | null;
  cheapest_price: number | null;
  cheapest_retailer: string | null;
  retailer_count: number;
  budget_allocated: number;
}

export interface CompatIssue {
  level: "error" | "warn" | "ok";
  slots: string[];
  title: string;
  detail: string;
}

export interface CompatReport {
  issues: CompatIssue[];
  estimated_watts: number | null;
  recommended_psu: number | null;
  has_errors: boolean;
}

export interface BuildSheetBlock {
  type: "build_sheet";
  profile: string;
  budget_bdt: number | null;
  total_cost: number | null;
  within_budget: boolean;
  slots: BuildSlot[];
  compatibility: CompatReport;
}

export interface PriceHistoryBlock {
  type: "price_history";
  product_id: number;
  current_price: number | null;
  all_time_low: number | null;
  all_time_high: number | null;
  trend: "dropping" | "rising" | "stable";
  history: PricePoint[];
}

export interface CompatReportBlock {
  type: "compat_report";
  issues: CompatIssue[];
  estimated_watts: number | null;
  recommended_psu: number | null;
  has_errors: boolean;
}

export interface Deal {
  id: number;
  name: string;
  brand: string | null;
  category: string | null;
  specs: Record<string, unknown>;
  retailer: string;
  current_price: number;
  prev_price: number;
  drop_bdt: number;
  drop_pct: number;
}

export interface DealListBlock {
  type: "deal_list";
  deals: Deal[];
  count: number;
}

export interface ProductDetailBlock {
  type: "product_detail";
  product: ProductSummary;
}

export type AgentBlock =
  | ProductListBlock
  | ProductDetailBlock
  | BuildSheetBlock
  | PriceHistoryBlock
  | CompatReportBlock
  | DealListBlock;

// UI action directives emitted by the agent
export interface ApplyFiltersAction {
  type: "apply_filters";
  category?: string;
  specs?: Record<string, string>;
}
export interface AddToBuildAction {
  type: "add_to_build";
  product_id: number;
  slot: string;
}
export interface OpenProductAction {
  type: "open_product";
  product_id: number;
}
export interface OpenDealsAction {
  type: "open_deals";
}

export type AgentAction =
  | ApplyFiltersAction
  | AddToBuildAction
  | OpenProductAction
  | OpenDealsAction;

export interface ChatResponse {
  text: string;
  blocks: AgentBlock[];
  actions: AgentAction[];
  // Legacy fields (backward compat)
  params: Record<string, unknown>;
  products: ProductSummary[];
  total: number;
  explanation: string;
}

export interface ChatContext {
  category?: string | null;
  filters?: Record<string, unknown> | null;
  build_slots?: Record<string, number> | null;
}

// ── Alerts ────────────────────────────────────────────────────────────────

export interface Alert {
  id: number;
  product_id: number;
  product_name: string;
  product_category: string | null;
  target_price: number;
  current_price: number | null;
  cheapest_retailer: string | null;
  triggered: boolean;
  last_notified_at: string | null;
  created_at: string;
}

// Filter state managed by the UI and serialized into /products query params.
// A string[] is a multi-select group (several ticked options → OR match);
// a boolean is a single toggle.
export interface SpecParams {
  [key: string]: string | string[] | boolean | undefined;
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
