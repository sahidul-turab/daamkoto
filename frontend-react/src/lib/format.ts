// Small formatting helpers shared across components.

export function formatBDT(price: number | null | undefined): string {
  if (price === null || price === undefined) return "—";
  return "৳" + Math.round(price).toLocaleString("en-BD");
}

export function formatBDTShort(price: number | null | undefined): string {
  if (price === null || price === undefined) return "—";
  if (price >= 100000) return "৳" + (price / 1000).toFixed(0) + "k";
  return formatBDT(price);
}

// Turn a spec key like "memory_type" into "Memory Type".
export function humanizeKey(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .replace(/\bRgb\b/i, "RGB")
    .replace(/\bEcc\b/i, "ECC")
    .replace(/\bUsb\b/i, "USB")
    .replace(/\bGpu\b/i, "GPU")
    .replace(/\bRam\b/i, "RAM")
    .replace(/\bRpm\b/i, "RPM")
    .replace(/\bM2\b/i, "M.2");
}

export function formatSpecValue(value: unknown): string {
  if (value === true) return "Yes";
  if (value === false) return "No";
  if (value === null || value === undefined) return "—";
  return String(value);
}

export function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const diffMs = Date.now() - then;
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.round(hrs / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}
