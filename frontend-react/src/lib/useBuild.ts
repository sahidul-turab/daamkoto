import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { ProductSummary } from "../types";
import { SLOTS, MAX_QTY, type BuildLine, type BuildState, type SlotId, isMulti, slotDef } from "./buildConfig";

const STORAGE_KEY = "pcbuild:v2";
const VALID_SLOTS = new Set<string>(SLOTS.map((s) => s.id));

function isLineArray(v: unknown): v is BuildLine[] {
  return (
    Array.isArray(v) &&
    v.every((x) => x && typeof x === "object" && "product" in x && "qty" in x)
  );
}

function load(): BuildState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    const result: BuildState = {};
    for (const [slot, val] of Object.entries(parsed)) {
      if (VALID_SLOTS.has(slot) && isLineArray(val)) {
        result[slot as SlotId] = val;
      }
    }
    return result;
  } catch {
    return {};
  }
}

function save(build: BuildState) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(build));
  } catch {
    /* ignore quota / private-mode errors */
  }
}

// Hash format v2: #build=b2.cpu-123_ram-77x2_ram-91x1
// Token: <slot>-<productId>  or  <slot>-<productId>x<qty>
// Retailer overrides are NOT encoded (listing order isn't stable; they're a local affordance).
function encodeHash(build: BuildState): string {
  const toks: string[] = [];
  for (const [slot, lines] of Object.entries(build) as [SlotId, BuildLine[]][]) {
    for (const l of lines ?? []) {
      toks.push(`${slot}-${l.product.id}${l.qty > 1 ? "x" + l.qty : ""}`);
    }
  }
  return toks.length ? `#build=b2.${toks.join("_")}` : "";
}

function parseHash(): { slot: SlotId; id: number; qty: number }[] {
  const m = window.location.hash.match(/build=([^&]+)/);
  if (!m || !m[1].startsWith("b2.")) return []; // ignore v1 or unknown versions
  return m[1]
    .slice(3)
    .split("_")
    .map((tok) => {
      const xIdx = tok.lastIndexOf("x");
      const dashIdx = tok.includes("x") ? tok.slice(0, xIdx).lastIndexOf("-") : tok.lastIndexOf("-");
      const head = tok.includes("x") ? tok.slice(0, xIdx) : tok;
      const qtyStr = tok.includes("x") ? tok.slice(xIdx + 1) : "1";
      const slot = head.slice(0, dashIdx) as SlotId;
      const id = Number(head.slice(dashIdx + 1));
      const qty = Math.max(1, Math.min(MAX_QTY, Number(qtyStr) || 1));
      return { slot, id, qty };
    })
    .filter((x) => VALID_SLOTS.has(x.slot) && Number.isFinite(x.id));
}

export function useBuild() {
  const [build, setBuild] = useState<BuildState>(() => load());
  const [hydratingShare, setHydratingShare] = useState(false);
  const didInitHash = useRef(false);

  // One-time: hydrate from a #build=b2.… share link (overrides localStorage).
  useEffect(() => {
    if (didInitHash.current) return;
    didInitHash.current = true;
    const shared = parseHash();
    if (shared.length === 0) return;
    setHydratingShare(true);

    // Dedupe: fetch each distinct product id once.
    const uniqueIds = [...new Set(shared.map((x) => x.id))];
    Promise.all(
      uniqueIds.map((id) =>
        api
          .product(id)
          .then((p) => ({ id, p }))
          .catch(() => null),
      ),
    )
      .then((results) => {
        const byId = new Map<number, ProductSummary>();
        for (const r of results) if (r && r.p) byId.set(r.id, r.p);

        const next: BuildState = {};
        for (const { slot, id, qty } of shared) {
          const product = byId.get(id);
          if (!product) continue;
          const def = SLOTS.find((s) => s.id === slot);
          const maxLines = (def as Record<string, unknown>).maxLines as number | undefined ?? 1;
          const existing = next[slot] ?? [];
          if (existing.length >= maxLines) continue; // clamp
          existing.push({ product, qty });
          next[slot] = existing;
        }
        if (Object.keys(next).length) {
          setBuild(next);
          save(next);
        }
      })
      .finally(() => setHydratingShare(false));
  }, []);

  // Replace-all: single slot sets exactly one line {product, qty:1}.
  const setPart = useCallback((slotId: SlotId, product: ProductSummary) => {
    setBuild((b) => {
      const next = { ...b, [slotId]: [{ product, qty: 1 }] };
      save(next);
      return next;
    });
  }, []);

  // Multi-line append. If the same product id already exists in this slot, bump its qty.
  const addLine = useCallback((slotId: SlotId, product: ProductSummary, qty = 1) => {
    setBuild((b) => {
      const existing = [...(b[slotId] ?? [])];
      const dup = existing.findIndex((l) => l.product.id === product.id);
      if (dup !== -1) {
        const updated = [...existing];
        updated[dup] = { ...updated[dup], qty: Math.min(MAX_QTY, updated[dup].qty + qty) };
        const next = { ...b, [slotId]: updated };
        save(next);
        return next;
      }
      const def = SLOTS.find((s) => s.id === slotId);
      const maxLines = (def as Record<string, unknown>).maxLines as number | undefined ?? 1;
      if (existing.length >= maxLines) return b; // slot full
      const next = { ...b, [slotId]: [...existing, { product, qty: Math.min(MAX_QTY, qty) }] };
      save(next);
      return next;
    });
  }, []);

  const setQty = useCallback((slotId: SlotId, index: number, qty: number) => {
    setBuild((b) => {
      const lines = [...(b[slotId] ?? [])];
      if (!lines[index]) return b;
      lines[index] = { ...lines[index], qty: Math.max(1, Math.min(MAX_QTY, qty)) };
      const next = { ...b, [slotId]: lines };
      save(next);
      return next;
    });
  }, []);

  const removeLine = useCallback((slotId: SlotId, index: number) => {
    setBuild((b) => {
      const lines = (b[slotId] ?? []).filter((_, i) => i !== index);
      const next = { ...b };
      if (lines.length === 0) {
        delete next[slotId];
      } else {
        next[slotId] = lines;
      }
      save(next);
      return next;
    });
  }, []);

  const setLineRetailer = useCallback((slotId: SlotId, index: number, retailer: string | undefined) => {
    setBuild((b) => {
      const lines = [...(b[slotId] ?? [])];
      if (!lines[index]) return b;
      lines[index] = { ...lines[index], retailer };
      const next = { ...b, [slotId]: lines };
      save(next);
      return next;
    });
  }, []);

  const removePart = useCallback((slotId: SlotId) => {
    setBuild((b) => {
      const next = { ...b };
      delete next[slotId];
      save(next);
      return next;
    });
  }, []);

  const clear = useCallback(() => {
    setBuild({});
    save({});
  }, []);

  const shareUrl = useCallback((): string => {
    const hash = encodeHash(build);
    const url = window.location.origin + window.location.pathname + hash;
    if (hash) {
      try {
        window.history.replaceState(null, "", hash);
      } catch {
        /* ignore */
      }
    }
    return url;
  }, [build]);

  // Number of slots with at least one line.
  const count = Object.values(build).filter((l) => l && l.length > 0).length;

  return {
    build,
    setPart,
    addLine,
    setQty,
    removeLine,
    setLineRetailer,
    removePart,
    clear,
    shareUrl,
    hydratingShare,
    count,
    isMulti,
    slotDef,
  };
}
