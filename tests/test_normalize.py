"""Tests for cleaning/normalize.py — the first automated tests in this project.

Why this file first: ARCHITECTURE.md calls normalize.py "the most breakage-prone
file in the repo", and every incident recorded in IMPROVEMENTS.md shares one
shape — *wrong data that reports success*. A regex here that stops matching a
vendor's new naming scheme raises nothing. It quietly changes `match_key`, which
splits one product into several or merges several into one, and the only symptom
is a product page that looks slightly off.

So these tests concentrate on three things rather than covering all 135
functions:

  1. **Identity.** `match_key` decides which listings are the same product.
  2. **Historical bugs.** Anything IMPROVEMENTS.md records as having broken once
     gets a regression test, so it cannot break the same way twice.
  3. **Contracts.** Every category dispatches to a real cleaner, and every
     cleaner emits the keys the loader reads. A cleaner that silently drops a
     field is the "scraper field loss" trap one stage later.

Known gaps are recorded as `xfail` rather than deleted: they document real
behaviour that is wrong but not yet safe to change, because changing a
`match_key` rewrites product identity and needs a data migration, not a patch.

Run:  python -m pytest tests/ -q
"""

import inspect
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cleaning import normalize as n


# ---------------------------------------------------------------------------
# 1. Identity — match_key
# ---------------------------------------------------------------------------

class TestMatchKey:
    """`match_key` is product identity. Changes here re-shape the catalogue."""

    def test_composes_all_parts_lowercased(self):
        assert n.build_match_key("Kingston", "16GB", "DDR5", "5600MHz") == \
            "kingston_16gb_ddr5_5600mhz"

    def test_omits_missing_parts_without_leaving_gaps(self):
        # A None must not become an empty segment ("kingston__ddr4").
        assert n.build_match_key("Kingston", None, "DDR4", None) == "kingston_ddr4"
        assert n.build_match_key("Team", "8GB", None, None) == "team_8gb"

    def test_is_stable_across_calls(self):
        args = ("Corsair", "32GB", "DDR5", "6000MHz")
        assert n.build_match_key(*args) == n.build_match_key(*args)

    def test_spacing_variants_reach_the_same_key(self):
        """"16 GB" and "16GB" are the same product at different retailers.

        This is the whole reason normalize_name exists — if these diverged, the
        same stick would appear as two products with two prices.
        """
        spaced = "Kingston Fury 16 GB DDR5 5600 MHz"
        tight = "Kingston Fury 16GB DDR5 5600MHz"
        assert n.normalize_name(spaced) == tight

        def key(name):
            return n.build_match_key(
                n.extract_brand(name), n.extract_capacity(name),
                n.extract_generation(name), n.extract_speed(name),
            )

        assert key(spaced) == key(tight)

    def test_brand_aliases_collapse(self):
        """Retailers spell the same brand differently; identity must not fork."""
        assert n.extract_brand("G.Skill Trident Z5") == "G.Skill"
        assert n.extract_brand("gskill ripjaws v") == "G.Skill"
        assert n.extract_brand("TeamGroup T-Force Vulcan") == "Team"
        assert n.extract_brand("Twinmos 8GB DDR4") == "TwinMOS"


# ---------------------------------------------------------------------------
# 2. Shared extractors
# ---------------------------------------------------------------------------

class TestCapacity:
    @pytest.mark.parametrize("name,expected", [
        ("Kingston Fury 16GB DDR5", "16GB"),
        ("Samsung 990 PRO 1TB NVMe", "1TB"),
        ("WD Blue 2 TB HDD", "2TB"),          # space before unit
        ("no capacity mentioned", None),
    ])
    def test_basic(self, name, expected):
        assert n.extract_capacity(name) == expected

    def test_prefers_tb_over_an_incidental_gb(self):
        """A drive's cache size must not be mistaken for its capacity."""
        assert n.extract_capacity("Seagate BarraCuda 1TB HDD 256MB Cache") == "1TB"

    def test_total_wins_over_kit_notation(self):
        """"32GB (2x16GB)" is a 32GB product, not a 16GB one."""
        assert n.extract_capacity("G.Skill 32GB (2x16GB) DDR5 6400MHz") == "32GB"


class TestGenerationSpeedLatency:
    @pytest.mark.parametrize("name,expected", [
        ("Corsair 16GB DDR5 6000MHz", "DDR5"),
        ("ddr4 lowercase kit", "DDR4"),
        ("GDDR6 graphics card", None),   # GDDR6 is VRAM, not system RAM
    ])
    def test_generation(self, name, expected):
        assert n.extract_generation(name) == expected

    def test_generation_ignores_gddr(self):
        """A GPU's GDDR6 must never be read as a DDR6 system-memory generation."""
        assert n.extract_generation("RTX 4060 8GB GDDR6") is None

    @pytest.mark.parametrize("name,expected", [
        ("16GB DDR5 6000MHz", "6000MHz"),
        ("16GB DDR4 3200 MHz", "3200MHz"),
        ("no speed at all", None),
    ])
    def test_speed(self, name, expected):
        assert n.extract_speed(name) == expected

    @pytest.mark.parametrize("name,expected", [
        # MT/s — how DDR5 is actually marketed
        ("CORSAIR VENGEANCE 32GB DDR5 6000MT/s CL36", "6000MHz"),
        ("Kingston FURY Beast DDR5 5200 MT/s", "5200MHz"),
        ("Team T-Force 32GB DDR5 6000 MT/S", "6000MHz"),
        # JEDEC-style speed grade
        ("G.Skill Trident Z5 DDR5-6000 CL30", "6000MHz"),
        ("ADATA XPG DDR4 3200 BUS Gaming RAM", "3200MHz"),
    ])
    def test_speed_alternate_notations(self, name, expected):
        """All three notations describe the same stick and must share a bucket."""
        assert n.extract_speed(name) == expected

    def test_mhz_wins_when_both_appear(self):
        assert n.extract_speed("DDR5-6000 rated 6000MHz kit") == "6000MHz"

    @pytest.mark.parametrize("name", [
        "Corsair DDR4 16GB 2x8GB kit",          # no speed anywhere
        "Cooler Master MWE 750 Bronze PSU",      # 750 is watts, not a DDR speed
        "G.Skill F5-6000J3036F48GX2 Ripjaws",    # speed lives in the part number
    ])
    def test_speed_does_not_invent_a_number(self, name):
        """The DDR-anchored branch must not grab an unrelated 3-5 digit number."""
        assert n.extract_speed(name) is None

    def test_latency_is_uppercased(self):
        assert n.extract_latency("DDR5 cl30 kit") == "CL30"


class TestFormFactor:
    @pytest.mark.parametrize("name", [
        "Crucial 8GB DDR4 SODIMM", "Crucial 8GB DDR4 SO-DIMM",
        "Kingston Laptop Memory 8GB",
    ])
    def test_laptop_variants(self, name):
        assert n.extract_form_factor(name) == "Laptop"

    def test_defaults_to_desktop(self):
        assert n.extract_form_factor("Kingston Fury Beast 16GB DDR5") == "Desktop"


# ---------------------------------------------------------------------------
# 3. Regression tests for bugs this project has actually had
# ---------------------------------------------------------------------------

class TestGpuChipsetRegression:
    """IMPROVEMENTS.md §2: AMD RX 500-series three-digit chipsets were
    mis-parsed, splitting one card across several products. These pin the
    boundary cases so a future regex tweak cannot reintroduce it."""

    @pytest.mark.parametrize("name,expected", [
        # three digits — the case that broke
        ("Sapphire Pulse AMD Radeon RX 580 8GB GDDR5", "RX 580"),
        ("AMD Radeon RX 6500 GRE", "RX 6500 GRE"),
        # four digits and suffixes
        ("XFX Radeon RX 6600 XT 8GB", "RX 6600 XT"),
        ("ASUS TUF Radeon RX 7900 XTX 24GB", "RX 7900 XTX"),
        ("XFX RX 9070 XT Gaming Edition", "RX 9070 XT"),
    ])
    def test_amd(self, name, expected):
        assert n.extract_chipset(name) == expected

    @pytest.mark.parametrize("name,expected", [
        ("Gigabyte AORUS GeForce RTX 5070 Ti MASTER 16G GDDR7", "RTX 5070 TI"),
        ("MSI GeForce RTX 4080 SUPER 16G GAMING X", "RTX 4080 SUPER"),
        ("Colorful GeForce RTX 3050 6GB V4-V", "RTX 3050"),
        ("ASUS GeForce GT 730 2GB", "GT 730"),
    ])
    def test_nvidia(self, name, expected):
        assert n.extract_chipset(name) == expected

    def test_intel_arc_keeps_its_casing(self):
        assert n.extract_chipset("Intel Arc A770 16GB") == "Arc A770"

    @pytest.mark.parametrize("chipset,brand", [
        ("RTX 5070 TI", "NVIDIA"), ("GT 730", "NVIDIA"),
        ("RX 580", "AMD"), ("RX 9070 XT", "AMD"),
        ("Arc A770", "Intel"),
        (None, None),
    ])
    def test_chipset_brand_mapping(self, chipset, brand):
        assert n.extract_chipset_brand(chipset) == brand


class TestHtmlEntities:
    """IMPROVEMENTS.md §13: EZ Gadgets' API returns HTML-encoded titles
    ("27&#8243;"). Scrapers decode before normalize sees them, so a name
    reaching here should never contain an entity — but if one slips through it
    must not silently become part of a match_key."""

    def test_decoded_names_parse_normally(self):
        assert n.extract_capacity('Samsung 27" Monitor 1TB bundle') == "1TB"

    def test_entity_in_name_is_visible_not_silent(self):
        # Documents current behaviour: normalize does not decode entities. The
        # scraper is responsible. If that ever changes, this test should change
        # with it deliberately.
        name = "AOC Q27G4P 27&#8243; QHD Gaming Monitor"
        assert "&#8243;" in n.normalize_name(name)


# ---------------------------------------------------------------------------
# 4. Contracts — dispatcher and cleaner output shape
# ---------------------------------------------------------------------------

# Categories run_pipeline.py accepts. Kept literal on purpose: importing it from
# run_pipeline would make the test agree with the code by construction and catch
# nothing.
PIPELINE_CATEGORIES = [
    "ram", "laptop_ram", "gpu", "processor", "motherboard",
    "ssd", "portable_ssd", "hdd", "portable_hdd",
    "psu", "cooler", "casing_cooler", "casing", "odd", "monitor",
    "keyboard", "mouse", "headset", "ups",
    "speaker", "webcam", "gaming_chair", "printer", "mousepad", "gamepad",
]

# Keys database/load.py and the matcher read off every cleaned record.
REQUIRED_KEYS = {"name", "price_bdt", "in_stock", "product_url",
                 "source", "scraped_at", "match_key", "specs"}


def _minimal_raw(name="Generic Product 16GB 1TB 650W 27 inch"):
    return {
        "name": name,
        "price_bdt": 1234.0,
        "in_stock": True,
        "product_url": "https://example.test/p/1",
        "source": "StarTech",
        "scraped_at": "2026-08-03T00:00:00+00:00",
        "inline_specs": {},
    }


class TestDispatcher:
    def test_every_pipeline_category_resolves_to_a_cleaner(self):
        """A category missing from CLEANERS falls back to the RAM cleaner and
        produces RAM-shaped specs for, say, a printer. Nothing raises."""
        unmapped = [c for c in PIPELINE_CATEGORIES
                    if c != "ram" and c not in n.CLEANERS]
        assert unmapped == [], f"categories with no cleaner: {unmapped}"

    def test_ram_intentionally_uses_the_default_cleaner(self):
        assert "ram" not in n.CLEANERS
        assert callable(n.clean_record)

    def test_no_cleaner_registered_for_an_unknown_category(self):
        assert n.CLEANERS.get("definitely_not_a_category") is None

    @pytest.mark.parametrize("category", sorted(n.CLEANERS))
    def test_each_cleaner_is_a_single_argument_callable(self, category):
        fn = n.CLEANERS[category]
        assert callable(fn)
        params = inspect.signature(fn).parameters
        assert len(params) == 1, f"{fn.__name__} should take one raw record"


class TestCleanerOutputShape:
    """Every cleaner must emit the keys downstream stages read. A cleaner that
    drops one produces records the loader stores with NULLs — the same class of
    silent field loss as the Ryans product_url incident."""

    @pytest.mark.parametrize("category", sorted(n.CLEANERS))
    def test_cleaner_emits_required_keys(self, category):
        out = n.CLEANERS[category](_minimal_raw())
        missing = REQUIRED_KEYS - set(out)
        assert missing == set(), f"{category} cleaner omits {sorted(missing)}"

    @pytest.mark.parametrize("category", sorted(n.CLEANERS))
    def test_specs_is_a_dict(self, category):
        """specs lands in a JSONB column and is filtered on. A list or None
        there breaks the spec filters rather than the insert."""
        assert isinstance(n.CLEANERS[category](_minimal_raw())["specs"], dict)

    @pytest.mark.parametrize("category", sorted(n.CLEANERS))
    def test_passthrough_fields_survive(self, category):
        """Price, URL and source must arrive unchanged — cleaners normalise
        names and specs, never the commercial facts."""
        raw = _minimal_raw()
        out = n.CLEANERS[category](raw)
        assert out["price_bdt"] == raw["price_bdt"]
        assert out["product_url"] == raw["product_url"]
        assert out["source"] == raw["source"]
        assert out["scraped_at"] == raw["scraped_at"]

    def test_default_cleaner_too(self):
        out = n.clean_record(_minimal_raw("Kingston Fury Beast 16GB DDR5 5600MHz"))
        assert REQUIRED_KEYS - set(out) == set()
        assert out["match_key"] == "kingston_16gb_ddr5_5600mhz"

    @pytest.mark.parametrize("category", sorted(n.CLEANERS))
    def test_cleaner_survives_a_missing_price(self, category):
        """Out-of-stock listings routinely have no price. That must clean, not
        crash — the pipeline would lose the whole retailer for that category."""
        raw = _minimal_raw()
        raw["price_bdt"] = None
        raw["in_stock"] = False
        out = n.CLEANERS[category](raw)
        assert out["price_bdt"] is None


# ---------------------------------------------------------------------------
# 5. Known gaps — real behaviour that is wrong but not yet safe to change
# ---------------------------------------------------------------------------

class TestKnownGaps:
    """These fail on purpose. Fixing any of them changes `match_key`, which
    moves products between buckets and needs a considered migration rather than
    a quiet patch. They are here so the gap is executable and measured, not
    folklore. Measured 2026-08-03 against production: 194 of 2,950 RAM products
    (6.6%) have no parsed speed; 47 of those say "MT/s" in the name."""

    @pytest.mark.xfail(reason="extract_capacity misses bare kit notation: the "
                              "\\b before \\d+ cannot match inside '2x16GB'.",
                       strict=True)
    def test_capacity_should_read_bare_kit_notation(self):
        # Total is absent from the name, so 2x16GB should yield 32GB.
        assert n.extract_capacity("Kingston FURY Beast 2x16GB DDR5 5200MT/s") == "32GB"
