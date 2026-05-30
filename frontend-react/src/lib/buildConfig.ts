import type { ProductSummary } from "../types";

export interface BuildLine {
  product: ProductSummary;
  qty: number;        // >= 1, capped by MAX_QTY
  retailer?: string;  // per-part shop override; undefined = auto-cheapest
}

export const MAX_QTY = 8;

// The eight build slots. ram and storage are multi-line (qty + multiple items).
export const SLOTS = [
  { id: "cpu",     label: "Processor",     category: "PROCESSOR",   icon: "Cpu" },
  { id: "mobo",    label: "Motherboard",   category: "MOTHERBOARD", icon: "CircuitBoard" },
  { id: "ram",     label: "Memory",        category: "RAM DESKTOP", icon: "MemoryStick", multi: true, maxLines: 4 },
  { id: "gpu",     label: "Graphics Card", category: "GPU",         icon: "MonitorPlay" },
  { id: "storage", label: "Storage",       category: "SSD",         icon: "HardDrive",   multi: true, maxLines: 4 },
  { id: "psu",     label: "Power Supply",  category: "PSU",         icon: "Power" },
  { id: "cooler",  label: "CPU Cooler",    category: "CPU COOLER",  icon: "Fan" },
  { id: "case",    label: "Case",          category: "CASING",      icon: "Box" },
] as const;

export type SlotId = (typeof SLOTS)[number]["id"];

// Every slot maps to 0..n BuildLines. Single slots hold at most 1 line.
export type BuildState = Partial<Record<SlotId, BuildLine[]>>;

// Map a catalogue category (uppercase DB value) back to a slot id.
export function slotForCategory(category: string | null | undefined): SlotId | null {
  if (!category) return null;
  const up = category.toUpperCase();
  const hit = SLOTS.find((s) => s.category === up);
  return hit ? hit.id : null;
}

export function slotDef(id: SlotId) {
  return SLOTS.find((s) => s.id === id)!;
}

export function isMulti(id: SlotId): boolean {
  return !!(slotDef(id) as Record<string, unknown>).multi;
}

// The representative product for a slot (first line). Used by compat + 3D.
export function repProduct(lines: BuildLine[] | undefined): ProductSummary | undefined {
  return lines && lines.length > 0 ? lines[0].product : undefined;
}

export function slotLines(build: BuildState, id: SlotId): BuildLine[] {
  return build[id] ?? [];
}
