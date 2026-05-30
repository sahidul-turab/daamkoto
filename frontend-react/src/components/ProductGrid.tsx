import { PackageSearch } from "lucide-react";
import type { ProductSummary } from "../types";
import { ProductCard } from "./ProductCard";

interface Props {
  products: ProductSummary[];
  loading: boolean;
  onOpen: (p: ProductSummary) => void;
  onAddToBuild?: (p: ProductSummary) => void;
  showAddToBuild?: boolean;
}

function SkeletonCard() {
  return (
    <div className="glass flex flex-col gap-3 p-5">
      <div className="skeleton h-5 w-20 rounded-md" />
      <div className="skeleton h-4 w-full rounded-md" />
      <div className="skeleton h-4 w-2/3 rounded-md" />
      <div className="mt-4 flex gap-2">
        <div className="skeleton h-5 w-14 rounded-full" />
        <div className="skeleton h-5 w-14 rounded-full" />
      </div>
      <div className="skeleton mt-4 h-8 w-28 rounded-md" />
    </div>
  );
}

export function ProductGrid({ products, loading, onOpen, onAddToBuild, showAddToBuild = false }: Props) {
  if (loading) {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 9 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    );
  }

  if (products.length === 0) {
    return (
      <div className="glass flex flex-col items-center justify-center gap-3 px-6 py-20 text-center">
        <div className="grid h-14 w-14 place-items-center rounded-2xl bg-surface-2 text-ink-4">
          <PackageSearch className="h-7 w-7" />
        </div>
        <div className="text-lg font-bold">No products match</div>
        <div className="max-w-sm text-sm text-ink-3">
          Try removing a filter, widening the price range, or switching off
          “In Stock Only”.
        </div>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {products.map((p, i) => (
        <ProductCard key={p.id} product={p} index={i} onOpen={onOpen} onAddToBuild={onAddToBuild} showAddToBuild={showAddToBuild} />
      ))}
    </div>
  );
}
