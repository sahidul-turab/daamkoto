"""
Server-side compatibility checker — mirrors frontend-react/src/lib/compat.ts.

This is the single source of truth for the AI agent's compatibility checks and
build planning. The existing compat.ts stays for live UI feedback — treat these
as a known dual-maintenance pair (the rules are small and stable).

Usage:
    from backend import compat, queries, database

    with database.get_db() as conn:
        products = {slot: queries.get_product(conn, pid) for slot, pid in slots.items()}

    result = compat.evaluate_build(products)
    # result.issues, result.estimated_watts, result.recommended_psu
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# TDP estimates (ported from tdp.ts)
# ---------------------------------------------------------------------------

_GPU_TDP: list[tuple[re.Pattern, int]] = [
    (re.compile(r"RTX\s*40?90", re.I), 450),
    (re.compile(r"RTX\s*40?80", re.I), 320),
    (re.compile(r"RTX\s*40?70\s*TI", re.I), 285),
    (re.compile(r"RTX\s*40?70", re.I), 200),
    (re.compile(r"RTX\s*40?60\s*TI", re.I), 160),
    (re.compile(r"RTX\s*40?60", re.I), 115),
    (re.compile(r"RTX\s*30?90", re.I), 350),
    (re.compile(r"RTX\s*30?80", re.I), 320),
    (re.compile(r"RTX\s*30?70", re.I), 220),
    (re.compile(r"RTX\s*30?60\s*TI", re.I), 200),
    (re.compile(r"RTX\s*30?60", re.I), 170),
    (re.compile(r"RTX\s*30?50", re.I), 130),
    (re.compile(r"RX\s*7900", re.I), 320),
    (re.compile(r"RX\s*7800", re.I), 263),
    (re.compile(r"RX\s*7700", re.I), 245),
    (re.compile(r"RX\s*7600", re.I), 165),
    (re.compile(r"RX\s*6\d00", re.I), 200),
    (re.compile(r"GTX\s*16\d0", re.I), 125),
    (re.compile(r"GTX\s*10\d0", re.I), 120),
    (re.compile(r"(GT\s*\d|ARC\s*A)", re.I), 75),
]

_CPU_TDP: list[tuple[re.Pattern, int]] = [
    (re.compile(r"Core\s*(Ultra\s*)?(i9|9)", re.I), 150),
    (re.compile(r"Core\s*(Ultra\s*)?(i7|7)", re.I), 125),
    (re.compile(r"Core\s*(Ultra\s*)?(i5|5)", re.I), 95),
    (re.compile(r"Core\s*(Ultra\s*)?(i3|3)", re.I), 65),
    (re.compile(r"Threadripper", re.I), 280),
    (re.compile(r"Ryzen\s*9", re.I), 130),
    (re.compile(r"Ryzen\s*7", re.I), 90),
    (re.compile(r"Ryzen\s*5", re.I), 75),
    (re.compile(r"Ryzen\s*3", re.I), 65),
    (re.compile(r"(Pentium|Celeron|Athlon)", re.I), 50),
]

SYSTEM_BASE_WATTS = 90
_PSU_SIZES = [450, 500, 550, 650, 750, 850, 1000, 1200, 1300, 1600]


def _lookup_tdp(table: list[tuple[re.Pattern, int]], text: str | None) -> int:
    if not text:
        return 0
    for pattern, watts in table:
        if pattern.search(text):
            return watts
    return 0


def gpu_watts(chipset: str | None) -> int:
    return _lookup_tdp(_GPU_TDP, chipset)


def cpu_watts(series: str | None, model: str | None = None) -> int:
    combined = " ".join(p for p in [series, model] if p)
    return _lookup_tdp(_CPU_TDP, combined)


def round_to_psu_size(watts: int) -> int:
    for size in _PSU_SIZES:
        if size >= watts:
            return size
    return ((watts + 99) // 100) * 100


# ---------------------------------------------------------------------------
# Case form-factor compatibility table (ported from compat.ts)
# ---------------------------------------------------------------------------

_CASE_HOUSES: dict[str, list[str]] = {
    "FULLTOWER":  ["EATX", "ATX", "MICROATX", "MINIITX"],
    "MIDTOWER":   ["ATX", "MICROATX", "MINIITX"],
    "MICROATX":   ["MICROATX", "MINIITX"],
    "MINIITX":    ["MINIITX"],
}


def _norm(s: str | None) -> str:
    if not s:
        return ""
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def _spec(product: dict | None, key: str) -> str | None:
    if not product:
        return None
    specs = product.get("specs") or {}
    v = specs.get(key)
    if v is None or v == "":
        return None
    return str(v)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class CompatIssue:
    level: str          # "error" | "warn" | "ok"
    slots: list[str]
    title: str
    detail: str


@dataclass
class CompatResult:
    issues: list[CompatIssue]
    estimated_watts: int
    recommended_psu: int
    psu_watts: int | None
    error_slots: set[str] = field(default_factory=set)

    def has_errors(self) -> bool:
        return bool(self.error_slots)

    def to_dict(self) -> dict:
        return {
            "issues": [
                {"level": i.level, "slots": i.slots, "title": i.title, "detail": i.detail}
                for i in self.issues
            ],
            "estimated_watts": self.estimated_watts,
            "recommended_psu": self.recommended_psu,
            "psu_watts": self.psu_watts,
            "has_errors": self.has_errors(),
        }


# ---------------------------------------------------------------------------
# Main evaluation function
# ---------------------------------------------------------------------------

def evaluate_build(products: dict[str, dict | None]) -> CompatResult:
    """
    Evaluate a set of build slots for compatibility.

    Args:
        products: mapping of slot → product dict (from queries.get_product).
                  Recognised slot names: cpu, mobo, ram, gpu, psu, case, cooler, storage.
                  Missing or None values are simply skipped.

    Returns:
        CompatResult with issues, wattage estimates, and PSU recommendation.
    """
    issues: list[CompatIssue] = []
    error_slots: set[str] = set()

    def add(issue: CompatIssue) -> None:
        issues.append(issue)
        if issue.level == "error":
            for s in issue.slots:
                error_slots.add(s)

    cpu   = products.get("cpu")
    mobo  = products.get("mobo")
    ram   = products.get("ram")
    gpu   = products.get("gpu")
    psu   = products.get("psu")
    case  = products.get("case")
    cooler = products.get("cooler")

    # 1) CPU ↔ Motherboard socket
    cpu_sock  = _spec(cpu, "socket")
    mobo_sock = _spec(mobo, "socket")
    if cpu and mobo and cpu_sock and mobo_sock:
        if _norm(cpu_sock) == _norm(mobo_sock):
            add(CompatIssue("ok", ["cpu", "mobo"], "Socket match", f"Both {cpu_sock}"))
        else:
            add(CompatIssue(
                "error", ["cpu", "mobo"], "Socket mismatch",
                f"CPU is {cpu_sock} but board is {mobo_sock}",
            ))

    # 2) RAM generation ↔ Motherboard RAM type
    ram_gen  = _spec(ram, "generation")
    mobo_ram = _spec(mobo, "ram_type")
    if ram and mobo and ram_gen and mobo_ram:
        if _norm(ram_gen) == _norm(mobo_ram):
            add(CompatIssue("ok", ["ram", "mobo"], "Memory supported", f"Both {ram_gen}"))
        else:
            add(CompatIssue(
                "error", ["ram", "mobo"], "Memory incompatible",
                f"RAM is {ram_gen} but board takes {mobo_ram}",
            ))

    # 3) Motherboard fits the case
    mobo_ff = _spec(mobo, "form_factor")
    case_ff = _spec(case, "form_factor")
    if mobo and case and mobo_ff and case_ff:
        houses = _CASE_HOUSES.get(_norm(case_ff))
        if houses is None:
            add(CompatIssue("warn", ["mobo", "case"], "Check board fit",
                            f"Verify a {mobo_ff} board fits a {case_ff} case"))
        elif _norm(mobo_ff) in houses:
            add(CompatIssue("ok", ["mobo", "case"], "Board fits case",
                            f"{mobo_ff} in {case_ff}"))
        else:
            add(CompatIssue("error", ["mobo", "case"], "Board too large for case",
                            f"A {mobo_ff} board won't fit a {case_ff} case"))

    # 4) Power estimate & PSU headroom
    cpu_w = cpu_watts(_spec(cpu, "series"), _spec(cpu, "model_number"))
    gpu_w = gpu_watts(_spec(gpu, "chipset"))
    estimated_watts = SYSTEM_BASE_WATTS + cpu_w + gpu_w
    recommended_psu = round_to_psu_size(round(estimated_watts * 1.4))

    psu_watts_val: int | None = None
    psu_wattage_str = _spec(psu, "wattage")
    if psu_wattage_str:
        m = re.search(r"(\d{3,4})\s*W", psu_wattage_str, re.I)
        if m:
            psu_watts_val = int(m.group(1))

    if psu and psu_watts_val is not None:
        if psu_watts_val < estimated_watts:
            add(CompatIssue("warn", ["psu"], "PSU may be underpowered",
                            f"~{estimated_watts}W estimated draw vs {psu_watts_val}W supply"))
        elif psu_watts_val < recommended_psu:
            add(CompatIssue("warn", ["psu"], "Low power headroom",
                            f"{psu_watts_val}W works; {recommended_psu}W+ recommended"))
        else:
            add(CompatIssue("ok", ["psu"], "Ample power", f"{psu_watts_val}W supply"))

    # 5) AIO radiator size vs small cases
    radiator = _spec(cooler, "radiator_size")
    rad_mm = 0
    if radiator:
        m2 = re.search(r"(\d+)", radiator)
        if m2:
            rad_mm = int(m2.group(1))
    if cooler and case and rad_mm >= 280 and _norm(case_ff or "") in {"MICROATX", "MINIITX"}:
        add(CompatIssue("warn", ["cooler", "case"], "Large radiator",
                        f"A {radiator} radiator may not fit a {case_ff} case"))

    # Sort: errors → warnings → ok
    _rank = {"error": 0, "warn": 1, "ok": 2}
    issues.sort(key=lambda i: _rank.get(i.level, 3))

    return CompatResult(
        issues=issues,
        estimated_watts=estimated_watts,
        recommended_psu=recommended_psu,
        psu_watts=psu_watts_val,
        error_slots=error_slots,
    )


# ---------------------------------------------------------------------------
# Budget allocation helper (used by plan_build tool)
# ---------------------------------------------------------------------------

# Rough percentage allocation for a "balanced" PC build.
# gaming: emphasise GPU; workstation: emphasise CPU + RAM; office: low-end balanced.
BUDGET_PROFILES: dict[str, dict[str, float]] = {
    "gaming": {
        "gpu":     0.30,
        "cpu":     0.18,
        "mobo":    0.10,
        "ram":     0.09,
        "storage": 0.08,
        "psu":     0.09,
        "case":    0.08,
        "cooler":  0.08,
    },
    "workstation": {
        "cpu":     0.25,
        "ram":     0.20,
        "mobo":    0.12,
        "gpu":     0.15,
        "storage": 0.10,
        "psu":     0.08,
        "case":    0.06,
        "cooler":  0.04,
    },
    "office": {
        "cpu":     0.28,
        "mobo":    0.15,
        "ram":     0.15,
        "storage": 0.15,
        "psu":     0.10,
        "case":    0.10,
        "cooler":  0.07,
        "gpu":     0.00,  # iGPU
    },
    "balanced": {
        "gpu":     0.25,
        "cpu":     0.20,
        "mobo":    0.12,
        "ram":     0.10,
        "storage": 0.09,
        "psu":     0.09,
        "case":    0.08,
        "cooler":  0.07,
    },
}

# Map build slot → DB category
SLOT_CATEGORY: dict[str, str] = {
    "cpu":     "PROCESSOR",
    "mobo":    "MOTHERBOARD",
    "ram":     "RAM DESKTOP",
    "gpu":     "GPU",
    "storage": "SSD",
    "psu":     "PSU",
    "cooler":  "CPU COOLER",
    "case":    "CASING",
}


def classify_use_case(text: str) -> str:
    """Heuristic: classify a use-case description into a budget profile."""
    t = text.lower()
    if any(w in t for w in ["gaming", "game", "fps", "esport"]):
        return "gaming"
    if any(w in t for w in ["workstation", "3d", "render", "video edit", "vfx", "cad"]):
        return "workstation"
    if any(w in t for w in ["office", "work", "browsing", "basic", "budget"]):
        return "office"
    return "balanced"
