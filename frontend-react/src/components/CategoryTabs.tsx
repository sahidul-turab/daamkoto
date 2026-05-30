import { motion } from "framer-motion";
import { CATEGORIES, type CategoryDef } from "../config";
import { CategoryIcon } from "./Icon";

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
            className={`relative flex shrink-0 items-center gap-2 rounded-xl border px-3.5 py-2 text-sm font-semibold transition-colors duration-200 ${
              isActive
                ? "border-brand/40 text-white"
                : "border-line bg-surface-2 text-ink-2 hover:border-line-2 hover:text-ink"
            }`}
          >
            {isActive && (
              <motion.span
                layoutId="cat-active"
                className="absolute inset-0 rounded-xl bg-brand-strong/15"
                style={{ boxShadow: "0 0 0 1px rgba(244,63,75,0.4) inset" }}
                transition={{ type: "spring", stiffness: 400, damping: 32 }}
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
