from backend.tools import _infer_cpu_socket, _valid_build_candidate


def product(name, **specs):
    return {"name": name, "specs": specs}


def test_gpu_accessories_are_rejected():
    assert not _valid_build_candidate("gpu", product("Deepcool GH-01 Graphics Card Holder"))
    assert not _valid_build_candidate("gpu", product("Vertical GPU Riser Kit"))
    assert _valid_build_candidate("gpu", product("RTX 4060 Graphics Card", chipset="RTX 4060"))


def test_storage_enclosures_are_rejected():
    assert not _valid_build_candidate("storage", product("M.2 NVMe SSD Enclosure", capacity="1TB"))
    assert _valid_build_candidate("storage", product("WD SN770 1TB NVMe SSD", capacity="1TB"))


def test_case_fans_are_rejected_from_case_slot():
    assert not _valid_build_candidate("case", product("ARGB Case Fan 120mm"))
    assert _valid_build_candidate("case", product("Antec NX200M Micro-ATX Casing"))


def test_case_fans_are_rejected_from_cpu_cooler_slot():
    assert not _valid_build_candidate("cooler", product("Thermalright ARGB Casing Fan"))
    assert _valid_build_candidate("cooler", product("DeepCool AK400 CPU Cooler"))


def test_planner_requires_a_sensible_psu_floor():
    assert not _valid_build_candidate("psu", product("Value Top 200W Power Supply", wattage="200W"))
    assert _valid_build_candidate("psu", product("Corsair CX550 Power Supply", wattage="550W"))


def test_cpu_socket_fallbacks_cover_common_current_platforms():
    assert _infer_cpu_socket(product("Intel 13th Gen Core i3-13100F Processor")) == "LGA1700"
    assert _infer_cpu_socket(product("AMD Ryzen 5 7600 Processor")) == "AM5"
    assert _infer_cpu_socket(product("AMD Ryzen 5 5600G Processor")) == "AM4"
