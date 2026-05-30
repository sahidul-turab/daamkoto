import type { ProductSummary } from "../types";
import type { BuildState, SlotId } from "./buildConfig";
import { repProduct } from "./buildConfig";
import { SYSTEM_BASE_WATTS, cpuWatts, gpuWatts, roundToPsuSize } from "./tdp";

export type IssueLevel = "error" | "warn" | "ok";

export interface Issue {
  level: IssueLevel;
  slots: SlotId[];
  title: string;
  detail: string;
}

export interface CompatResult {
  issues: Issue[];
  estimatedWatts: number;
  recommendedPsu: number;
  psuWatts: number | null;
  errorSlots: Set<SlotId>;
}

function spec(p: ProductSummary | undefined, key: string): string | undefined {
  if (!p) return undefined;
  const v = p.specs[key];
  return v == null || v === "" ? undefined : String(v);
}

const norm = (s: string) => s.toUpperCase().replace(/[^A-Z0-9]/g, "");
const wattsOf = (s?: string) => {
  if (!s) return null;
  const m = s.match(/(\d{3,4})\s*W/i);
  return m ? Number(m[1]) : null;
};

// Which motherboard form factors a given case can physically house.
const CASE_HOUSES: Record<string, string[]> = {
  FULLTOWER: ["EATX", "ATX", "MICROATX", "MINIITX"],
  MIDTOWER: ["ATX", "MICROATX", "MINIITX"],
  MICROATX: ["MICROATX", "MINIITX"],
  MINIITX: ["MINIITX"],
};

export function evaluateBuild(build: BuildState): CompatResult {
  const issues: Issue[] = [];
  const errorSlots = new Set<SlotId>();
  const add = (i: Issue) => {
    issues.push(i);
    if (i.level === "error") i.slots.forEach((s) => errorSlots.add(s));
  };

  const cpu = repProduct(build.cpu);
  const mobo = repProduct(build.mobo);
  const ram = repProduct(build.ram);
  const gpu = repProduct(build.gpu);
  const psu = repProduct(build.psu);
  const caseP = repProduct(build.case);
  const cooler = repProduct(build.cooler);

  // 1) CPU ↔ Motherboard socket
  const cpuSock = spec(cpu, "socket");
  const moboSock = spec(mobo, "socket");
  if (cpu && mobo && cpuSock && moboSock) {
    if (norm(cpuSock) === norm(moboSock)) {
      add({ level: "ok", slots: ["cpu", "mobo"], title: "Socket match", detail: `Both ${cpuSock}` });
    } else {
      add({
        level: "error",
        slots: ["cpu", "mobo"],
        title: "Socket mismatch",
        detail: `CPU is ${cpuSock} but board is ${moboSock}`,
      });
    }
  }

  // 2) RAM generation ↔ Motherboard supported RAM type
  const ramGen = spec(ram, "generation");
  const moboRam = spec(mobo, "ram_type");
  if (ram && mobo && ramGen && moboRam) {
    if (norm(ramGen) === norm(moboRam)) {
      add({ level: "ok", slots: ["ram", "mobo"], title: "Memory supported", detail: `Both ${ramGen}` });
    } else {
      add({
        level: "error",
        slots: ["ram", "mobo"],
        title: "Memory incompatible",
        detail: `RAM is ${ramGen} but board takes ${moboRam}`,
      });
    }
  }

  // Mixed RAM generations across multiple sticks
  const ramLines = build.ram ?? [];
  if (ramLines.length > 1 && ramGen) {
    const mixed = ramLines.slice(1).some((l) => {
      const gen = l.product.specs["generation"];
      return gen && norm(String(gen)) !== norm(ramGen);
    });
    if (mixed) {
      add({
        level: "warn",
        slots: ["ram"],
        title: "Mixed memory generations",
        detail: "Your RAM sticks use different generations — they may not work together",
      });
    }
  }

  // 3) Motherboard fits the case
  const moboFF = spec(mobo, "form_factor");
  const caseFF = spec(caseP, "form_factor");
  if (mobo && caseP && moboFF && caseFF) {
    const houses = CASE_HOUSES[norm(caseFF)];
    if (!houses) {
      // Unknown case size — can't be sure, flag softly.
      add({ level: "warn", slots: ["mobo", "case"], title: "Check board fit", detail: `Verify a ${moboFF} board fits a ${caseFF} case` });
    } else if (houses.includes(norm(moboFF))) {
      add({ level: "ok", slots: ["mobo", "case"], title: "Board fits case", detail: `${moboFF} in ${caseFF}` });
    } else {
      add({
        level: "error",
        slots: ["mobo", "case"],
        title: "Board too large for case",
        detail: `A ${moboFF} board won't fit a ${caseFF} case`,
      });
    }
  }

  // Power estimate
  const cpuW = cpuWatts(spec(cpu, "series"), spec(cpu, "model"));
  const gpuW = gpuWatts(spec(gpu, "chipset"));
  const estimatedWatts = SYSTEM_BASE_WATTS + cpuW + gpuW;
  const recommendedPsu = roundToPsuSize(Math.round(estimatedWatts * 1.4));
  const psuWatts = wattsOf(spec(psu, "wattage"));

  // 4) PSU headroom
  if (psu && psuWatts != null) {
    if (psuWatts < estimatedWatts) {
      add({
        level: "warn",
        slots: ["psu"],
        title: "PSU may be underpowered",
        detail: `~${estimatedWatts}W estimated draw vs ${psuWatts}W supply`,
      });
    } else if (psuWatts < recommendedPsu) {
      add({
        level: "warn",
        slots: ["psu"],
        title: "Low power headroom",
        detail: `${psuWatts}W works; ${recommendedPsu}W+ recommended`,
      });
    } else {
      add({ level: "ok", slots: ["psu"], title: "Ample power", detail: `${psuWatts}W supply` });
    }
  }

  // 5) AIO radiator vs small case (heuristic)
  const radiator = spec(cooler, "radiator_size");
  const radMm = radiator ? Number(radiator.match(/(\d+)/)?.[1] ?? 0) : 0;
  if (cooler && caseP && radMm >= 280 && ["MICROATX", "MINIITX"].includes(norm(caseFF ?? ""))) {
    add({
      level: "warn",
      slots: ["cooler", "case"],
      title: "Large radiator",
      detail: `A ${radiator} radiator may not fit a ${caseFF} case`,
    });
  }

  // Order: errors, then warnings, then ok
  const rank = { error: 0, warn: 1, ok: 2 };
  issues.sort((a, b) => rank[a.level] - rank[b.level]);

  return { issues, estimatedWatts, recommendedPsu, psuWatts, errorSlots };
}
