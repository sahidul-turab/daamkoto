import type { Listing, ProductSummary } from "../types";
import type { BuildState, SlotId } from "./buildConfig";

export interface BasketItem {
  slotId: SlotId;
  lineIndex: number;
  product: ProductSummary;
  qty: number;
  retailer: string;
  unitPrice: number;
  lineTotal: number;  // unitPrice * qty
  overridden: boolean;
  options: { retailer: string; price: number }[]; // in-stock priced listings asc — for the shop override <select>
}

export interface Basket {
  items: BasketItem[];
  total: number;                                    // Σ lineTotal
  perStore: { retailer: string; total: number }[];  // qty-weighted, sorted desc
  singleStore: { retailer: string; total: number } | null; // cheapest retailer stocking every line
  savingsVsSingleStore: number;                     // max(0, singleStore.total - total)
  missingPrice: { slotId: SlotId; lineIndex: number }[];
}

// All in-stock priced listings for a product, sorted cheapest first.
function pricedListings(p: ProductSummary): Listing[] {
  return p.listings
    .filter((l) => l.in_stock && l.price_bdt != null)
    .sort((a, b) => (a.price_bdt as number) - (b.price_bdt as number));
}

// Select the listing to use: prefer the override retailer if it has an in-stock price.
function pickListing(p: ProductSummary, override?: string): Listing | null {
  const priced = pricedListings(p);
  if (priced.length === 0) return null;
  if (override) {
    const hit = priced.find((l) => l.retailer === override);
    if (hit) return hit;
  }
  return priced[0]; // cheapest in-stock
}

export function computeBasket(build: BuildState): Basket {
  const items: BasketItem[] = [];
  const missingPrice: Basket["missingPrice"] = [];
  const perStoreMap = new Map<string, number>();

  for (const [slotId, lines] of Object.entries(build) as [SlotId, NonNullable<BuildState[SlotId]>][]) {
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const listing = pickListing(line.product, line.retailer);

      if (!listing || listing.price_bdt == null) {
        missingPrice.push({ slotId, lineIndex: i });
        continue;
      }

      const unitPrice = listing.price_bdt;
      const lineTotal = unitPrice * line.qty;
      const overridden = !!line.retailer && listing.retailer === line.retailer;

      const options = pricedListings(line.product).map((l) => ({
        retailer: l.retailer,
        price: l.price_bdt as number,
      }));

      items.push({
        slotId,
        lineIndex: i,
        product: line.product,
        qty: line.qty,
        retailer: listing.retailer,
        unitPrice,
        lineTotal,
        overridden,
        options,
      });

      perStoreMap.set(listing.retailer, (perStoreMap.get(listing.retailer) ?? 0) + lineTotal);
    }
  }

  const total = items.reduce((s, it) => s + it.lineTotal, 0);
  const perStore = [...perStoreMap.entries()]
    .map(([retailer, t]) => ({ retailer, total: t }))
    .sort((a, b) => b.total - a.total);

  // Single-store fulfilment: cheapest retailer that stocks EVERY priceable line.
  // Stock counts are unknown — we assume qty is available (documented assumption).
  let singleStore: Basket["singleStore"] = null;

  if (items.length > 0) {
    // For each item, build a map: retailer → price at that retailer (in-stock only).
    const retailerMaps = items.map((it) =>
      new Map(pricedListings(it.product).map((l) => [l.retailer, l.price_bdt as number])),
    );

    // Common retailers: appear in all item maps.
    const common = [...retailerMaps[0].keys()].filter((r) =>
      retailerMaps.every((m) => m.has(r)),
    );

    for (const r of common) {
      // Qty-weighted total at this single retailer.
      const t = items.reduce((s, it, idx) => s + (retailerMaps[idx].get(r) as number) * it.qty, 0);
      if (!singleStore || t < singleStore.total) singleStore = { retailer: r, total: t };
    }
  }

  const savingsVsSingleStore = singleStore ? Math.max(0, singleStore.total - total) : 0;

  return { items, total, perStore, singleStore, savingsVsSingleStore, missingPrice };
}
