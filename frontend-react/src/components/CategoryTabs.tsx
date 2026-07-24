import { CATEGORIES, type CategoryDef } from "../config";
import { prefetchCategory } from "../lib/prefetch";
import { CategoryIcon } from "./Icon";

// The active pill used to be a framer-motion shared-layout animation. That made
// framer-motion (40 kB gzipped) a dependency of the very first screen, since the
// tabs render above the product grid — 40 kB the user had to download before any
// price appeared. Every other consumer of framer-motion is behind a lazy import,
// so expressing this one indicator in CSS keeps the whole library off the
// critical path. The pill now appears instead of sliding; on a slow connection
// that is a trade the user comes out well ahead on.

interface Props {
  active: CategoryDef;
  onSelect: (c: CategoryDef) => void;
}

export function CategoryTabs({ active, onSelect }: Props) {
  return (
    <div className="no-scrollbar -mx-4 flex gap-2 overflow-x-auto px-4 pb-1 md:mx-0 md:flex-wrap md:overflow-visible md:px-0">
      {CATEGORIES.map((c) => {
        const isActive = c.db === active.db;
        return (
          <button
            key={c.db}
            onClick={() => onSelect(c)}
            // Fetch on intent rather than on click. The gap between a pointer
            // landing on a tab and the click firing is usually enough to cover
            // the whole round trip, so the switch renders instantly.
            onPointerEnter={() => prefetchCategory(c)}
            onFocus={() => prefetchCategory(c)}
            className={`relative flex shrink-0 items-center gap-2 rounded-xl border px-3.5 py-2 text-sm font-semibold transition-colors duration-200 ${
              isActive
                ? "border-brand/40 text-white"
                : "border-line bg-surface-2 text-ink-2 hover:border-line-2 hover:text-ink"
            }`}
          >
            {isActive && (
              <span
                className="absolute inset-0 rounded-xl bg-brand-strong/15 animate-fade-in"
                style={{ boxShadow: "0 0 0 1px rgba(244,63,75,0.4) inset" }}
              />
            )}
            <CategoryIcon
              name={c.icon}
              className={`relative h-4 w-4 ${isActive ? "text-brand" : ""}`}
            />
            <span className="relative whitespace-nowrap">{c.label}</span>
          </button>
        );
      })}
    </div>
  );
}
