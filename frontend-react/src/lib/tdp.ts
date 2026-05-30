// Rough power-draw estimates. The catalogue does not store TDP, so we approximate
// from the GPU chipset family and CPU series. These are deliberately ballpark
// figures (real draw depends on board, clocks, load) — the UI labels the result
// as an estimate and sizes the PSU with generous headroom.

const GPU_TDP: { match: RegExp; watts: number }[] = [
  { match: /RTX\s*40?90/i, watts: 450 },
  { match: /RTX\s*40?80/i, watts: 320 },
  { match: /RTX\s*40?70\s*TI/i, watts: 285 },
  { match: /RTX\s*40?70/i, watts: 200 },
  { match: /RTX\s*40?60\s*TI/i, watts: 160 },
  { match: /RTX\s*40?60/i, watts: 115 },
  { match: /RTX\s*30?90/i, watts: 350 },
  { match: /RTX\s*30?80/i, watts: 320 },
  { match: /RTX\s*30?70/i, watts: 220 },
  { match: /RTX\s*30?60\s*TI/i, watts: 200 },
  { match: /RTX\s*30?60/i, watts: 170 },
  { match: /RTX\s*30?50/i, watts: 130 },
  { match: /RX\s*7900/i, watts: 320 },
  { match: /RX\s*7800/i, watts: 263 },
  { match: /RX\s*7700/i, watts: 245 },
  { match: /RX\s*7600/i, watts: 165 },
  { match: /RX\s*6\d00/i, watts: 200 },
  { match: /GTX\s*16\d0/i, watts: 125 },
  { match: /GTX\s*10\d0/i, watts: 120 },
  { match: /(GT\s*\d|ARC\s*A)/i, watts: 75 },
];

const CPU_TDP: { match: RegExp; watts: number }[] = [
  { match: /Core\s*(Ultra\s*)?(i9|9)/i, watts: 150 },
  { match: /Core\s*(Ultra\s*)?(i7|7)/i, watts: 125 },
  { match: /Core\s*(Ultra\s*)?(i5|5)/i, watts: 95 },
  { match: /Core\s*(Ultra\s*)?(i3|3)/i, watts: 65 },
  { match: /Threadripper/i, watts: 280 },
  { match: /Ryzen\s*9/i, watts: 130 },
  { match: /Ryzen\s*7/i, watts: 90 },
  { match: /Ryzen\s*5/i, watts: 75 },
  { match: /Ryzen\s*3/i, watts: 65 },
  { match: /(Pentium|Celeron|Athlon)/i, watts: 50 },
];

function lookup(table: { match: RegExp; watts: number }[], text: string | undefined): number {
  if (!text) return 0;
  for (const row of table) if (row.match.test(text)) return row.watts;
  return 0;
}

export function gpuWatts(chipset?: string): number {
  return lookup(GPU_TDP, chipset);
}

export function cpuWatts(series?: string, model?: string): number {
  return lookup(CPU_TDP, [series, model].filter(Boolean).join(" "));
}

// System base (board, fans, RAM, one SSD, USB) before CPU/GPU.
export const SYSTEM_BASE_WATTS = 90;

// Round a recommended PSU size up to a common retail wattage.
export function roundToPsuSize(watts: number): number {
  const sizes = [450, 500, 550, 650, 750, 850, 1000, 1200, 1300, 1600];
  return sizes.find((s) => s >= watts) ?? Math.ceil(watts / 100) * 100;
}
