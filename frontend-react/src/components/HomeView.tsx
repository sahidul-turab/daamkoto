import {
  ArrowRight,
  BadgeCheck,
  Boxes,
  Search,
  ShieldCheck,
  Sparkles,
  Store,
  Tag,
} from "lucide-react";
import type { CategoryDef } from "../config";
import type { ProductSummary } from "../types";
import { useHomeFeed } from "../lib/useHomeFeed";
import { CategoryIcon } from "./Icon";
import { ProductCard } from "./ProductCard";

interface Props {
  retailerCount: number;
  isAdmin: boolean;
  onSearch: () => void;
  onBrowseCategory: (category: CategoryDef) => void;
  onOpenProduct: (product: ProductSummary) => void;
  onOpenBuild: () => void;
  onOpenDeals: () => void;
}

function SectionSkeleton() {
  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="skeleton h-7 w-44 rounded-lg" />
        <div className="skeleton h-8 w-24 rounded-lg" />
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="glass p-5">
            <div className="skeleton aspect-[4/3] rounded-xl" />
            <div className="skeleton mt-4 h-4 w-20 rounded" />
            <div className="skeleton mt-3 h-5 w-full rounded" />
            <div className="skeleton mt-2 h-5 w-3/4 rounded" />
            <div className="skeleton mt-6 h-8 w-28 rounded" />
          </div>
        ))}
      </div>
    </section>
  );
}
export function HomeView({
  retailerCount,
  isAdmin,
  onSearch,
  onBrowseCategory,
  onOpenProduct,
  onOpenBuild,
  onOpenDeals,
}: Props) {
  const { sections, loading, error, retry, categories } = useHomeFeed();

  return (
    <div className="space-y-12 pb-4">
      <section className="glass relative overflow-hidden px-5 py-10 sm:px-10 sm:py-14 lg:px-14 lg:py-16">
        <div className="pointer-events-none absolute -right-24 -top-40 h-96 w-96 rounded-full bg-brand/20 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-44 left-1/3 h-80 w-80 rounded-full bg-cyan-400/10 blur-3xl" />

        <div className="relative max-w-4xl">
          <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-brand/30 bg-brand-strong/10 px-3 py-1.5 text-xs font-semibold text-brand">
            <Sparkles className="h-3.5 w-3.5" />
            Compare before you buy
          </div>
          <h1 className="max-w-3xl text-4xl font-black leading-[1.05] tracking-tight text-ink sm:text-5xl lg:text-6xl">
            Find the right PC part at the
            <span className="text-brand"> right price.</span>
          </h1>
          <p className="mt-5 max-w-2xl text-base leading-relaxed text-ink-3 sm:text-lg">
            Search once and compare prices across Bangladesh’s trusted computer stores—without opening a dozen tabs.
          </p>

          <button
            type="button"
            onClick={onSearch}
            className="group mt-8 flex w-full max-w-2xl items-center gap-3 rounded-2xl border border-brand/50 bg-surface/90 p-2 text-left shadow-[0_18px_60px_-24px_rgba(239,35,42,0.75)] transition-all hover:border-brand hover:bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
          >
            <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-brand-strong text-white">
              <Search className="h-5 w-5" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-bold text-ink">Search any product</span>
              <span className="block truncate text-xs text-ink-4 sm:text-sm">RTX 4060, Ryzen 7, 16GB DDR5, 990 Pro…</span>
            </span>
            <span className="hidden items-center gap-1 rounded-xl bg-brand-strong px-4 py-2.5 text-sm font-bold text-white sm:flex">
              Search <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </span>
          </button>

          <div className="mt-6 flex flex-wrap gap-3">
            <button className="btn-ghost !rounded-xl" onClick={onOpenBuild}>
              <Boxes className="h-4 w-4" /> Build a PC
            </button>
            <button className="btn-ghost !rounded-xl" onClick={onOpenDeals}>
              <Tag className="h-4 w-4" /> View price drops
            </button>
          </div>
        </div>

        <div className="relative mt-10 grid gap-3 border-t border-line pt-6 sm:grid-cols-3 lg:max-w-3xl">
          <div className="flex items-center gap-3 text-sm text-ink-3">
            <Store className="h-5 w-5 text-brand" />
            <span><strong className="text-ink">{retailerCount || 13}</strong> retailers compared</span>
          </div>
          <div className="flex items-center gap-3 text-sm text-ink-3">
            <BadgeCheck className="h-5 w-5 text-ok" />
            <span>Best available price first</span>
          </div>
          <div className="flex items-center gap-3 text-sm text-ink-3">
            <ShieldCheck className="h-5 w-5 text-cyan-400" />
            <span>Direct links to each store</span>
          </div>
        </div>
      </section>

      <section>
        <div className="mb-4">
          <p className="label">Explore</p>
          <h2 className="mt-1 text-2xl font-bold tracking-tight">Shop by category</h2>
        </div>
        <div className="no-scrollbar -mx-4 flex gap-2 overflow-x-auto px-4 pb-2 md:mx-0 md:flex-wrap md:overflow-visible md:px-0">
          {categories.map((category) => (
            <button
              key={category.db}
              onClick={() => onBrowseCategory(category)}
              className="group flex shrink-0 items-center gap-2 rounded-xl border border-line bg-surface-2 px-3.5 py-2.5 text-sm font-semibold text-ink-2 transition-all hover:-translate-y-0.5 hover:border-brand/50 hover:bg-brand-strong/10 hover:text-ink"
            >
              <CategoryIcon name={category.icon} className="h-4 w-4 text-ink-4 transition-colors group-hover:text-brand" />
              {category.label}
            </button>
          ))}
        </div>
      </section>

      <section>
        <div className="mb-7 flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="label">Easy starting points</p>
            <h2 className="mt-1 text-2xl font-bold tracking-tight">Popular categories</h2>
            <p className="mt-1 text-sm text-ink-3">Products available from the most stores, grouped for quick browsing.</p>
          </div>
        </div>

        <div className="space-y-12">
          {loading && sections.length === 0 && (
            <>
              <SectionSkeleton />
              <SectionSkeleton />
            </>
          )}

          {error && sections.length === 0 && (
            <div className="glass px-6 py-12 text-center">
              <div className="text-lg font-bold">Featured products are refreshing</div>
              <p className="mt-2 text-sm text-ink-3">Categories are still available above, or try loading the highlights again.</p>
              <button className="btn-brand mt-5" onClick={retry}>Try again</button>
            </div>
          )}

          {sections.slice(0, 6).map((section) => {
            const category = categories.find((item) => item.db === section.category);
            if (!category) return null;
            return (
              <section key={section.category}>
                <div className="mb-4 flex items-center justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-3">
                    <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-brand/25 bg-brand-strong/10 text-brand">
                      <CategoryIcon name={category.icon} className="h-5 w-5" />
                    </span>
                    <div className="min-w-0">
                      <h3 className="text-xl font-bold">{category.label}</h3>
                      <p className="text-xs text-ink-4">{section.total.toLocaleString()} products</p>
                    </div>
                  </div>
                  <button
                    className="btn-ghost shrink-0 !rounded-xl !px-3 !py-2 text-sm"
                    onClick={() => onBrowseCategory(category)}
                  >
                    View all <ArrowRight className="h-4 w-4" />
                  </button>
                </div>
                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                  {section.products.map((product, index) => (
                    <ProductCard
                      key={product.id}
                      product={product}
                      index={index}
                      onOpen={onOpenProduct}
                      showOperationalMeta={isAdmin}
                    />
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      </section>
    </div>
  );
}
