import type { Filters } from "../types";

export const DEFAULT_FILTERS: Filters = {
  search: "",
  brand: null,
  minPrice: null,
  maxPrice: null,
  inStockOnly: true,
  bundleOnly: false,
  sort: "store_count_desc",
  specs: {},
};
