// Declarative port of the category + filter logic from frontend/app.py.
// Each category lists its spec filters. A filter is either:
//   - a "select" whose options are fetched live from /specs/values (with a
//     static fallback list), or
//   - a "bool" toggle that sets a spec param to `true` when on.

export interface SelectFilter {
  kind: "select";
  param: string; // query param name sent to /products
  label: string;
  specKey: string; // key passed to /specs/values
  fallback: string[];
}

export interface BoolFilter {
  kind: "bool";
  param: string;
  label: string;
}

export type SpecFilter = SelectFilter | BoolFilter;

export interface CategoryDef {
  label: string; // UI label
  db: string; // value sent as ?category=
  icon: string; // lucide icon name
  filters: SpecFilter[];
}

const sel = (
  param: string,
  label: string,
  specKey: string,
  fallback: string[],
): SelectFilter => ({ kind: "select", param, label, specKey, fallback });

const bool = (param: string, label: string): BoolFilter => ({
  kind: "bool",
  param,
  label,
});

const RAM_FILTERS: SpecFilter[] = [
  sel("generation", "DDR Generation", "generation", ["DDR3", "DDR4", "DDR5"]),
  sel("capacity", "Capacity", "capacity", ["4GB", "8GB", "16GB", "32GB", "64GB", "96GB", "128GB"]),
  sel("speed", "Bus Speed", "speed", [
    "1333MHz", "1600MHz", "2400MHz", "2666MHz", "3200MHz",
    "3600MHz", "4800MHz", "5200MHz", "5600MHz", "6000MHz",
  ]),
  sel("latency", "CAS Latency", "latency", ["CL9", "CL11", "CL14", "CL16", "CL18", "CL32", "CL36", "CL38", "CL40"]),
  bool("heatsink", "Heatsink"),
  bool("rgb", "RGB / ARGB"),
  bool("ecc", "ECC Memory"),
];

export const CATEGORIES: CategoryDef[] = [
  { label: "RAM Desktop", db: "RAM DESKTOP", icon: "MemoryStick", filters: RAM_FILTERS },
  { label: "RAM Laptop", db: "RAM LAPTOP", icon: "MemoryStick", filters: RAM_FILTERS },
  {
    label: "GPU", db: "GPU", icon: "Cpu", filters: [
      sel("chipset_brand", "GPU Maker", "chipset_brand", ["NVIDIA", "AMD", "Intel Arc"]),
      sel("vram", "VRAM", "vram", ["2GB", "4GB", "6GB", "8GB", "10GB", "12GB", "16GB", "20GB", "24GB"]),
      sel("chipset", "Chipset", "chipset", [
        "RTX 4090", "RTX 4080 SUPER", "RTX 4080", "RTX 4070 TI SUPER", "RTX 4070 TI",
        "RTX 4070 SUPER", "RTX 4070", "RTX 4060 TI", "RTX 4060", "RTX 3060", "RTX 3050",
        "RX 7900 XTX", "RX 7800 XT", "RX 7600", "GTX 1660 SUPER", "GTX 1650",
      ]),
      sel("memory_type", "Memory Type", "memory_type", ["GDDR5", "GDDR6", "GDDR6X", "GDDR7"]),
    ],
  },
  {
    label: "Processor", db: "PROCESSOR", icon: "Cpu", filters: [
      sel("socket", "CPU Socket", "socket", ["LGA1200", "LGA1700", "LGA1851", "AM4", "AM5", "TR4", "sTR5"]),
      sel("series", "Series", "series", [
        "Core Ultra 9", "Core Ultra 7", "Core Ultra 5", "Core i9", "Core i7", "Core i5", "Core i3",
        "Ryzen 9", "Ryzen 7", "Ryzen 5", "Ryzen 3", "Threadripper", "Pentium", "Celeron",
      ]),
      sel("cores", "Cores", "cores", ["2", "4", "6", "8", "10", "12", "14", "16", "18", "20", "24"]),
      sel("architecture", "Architecture", "architecture", [
        "Arrow Lake", "Raptor Lake", "Alder Lake", "Zen 5", "Zen 4", "Zen 3", "Zen 2",
      ]),
      sel("cache", "L3 Cache", "cache", ["6MB", "8MB", "12MB", "16MB", "24MB", "32MB", "36MB", "64MB"]),
    ],
  },
  {
    label: "Motherboard", db: "MOTHERBOARD", icon: "CircuitBoard", filters: [
      sel("socket", "CPU Socket", "socket", ["LGA1200", "LGA1700", "LGA1851", "AM4", "AM5", "sTR5"]),
      sel("chipset", "Chipset", "chipset", [
        "Z890", "Z790", "Z690", "B760", "B660", "H770", "H610",
        "X670E", "X670", "B650E", "B650", "X570", "B550", "B450", "A520",
      ]),
      sel("form_factor", "Form Factor", "form_factor", ["ATX", "Micro-ATX", "Mini-ITX", "E-ATX"]),
      sel("ram_type", "RAM Type", "ram_type", ["DDR3", "DDR4", "DDR5"]),
      bool("wifi", "Wi-Fi Built-in"),
    ],
  },
  {
    label: "SSD", db: "SSD", icon: "HardDrive", filters: [
      sel("capacity", "Capacity", "capacity", ["120GB", "128GB", "240GB", "256GB", "480GB", "512GB", "1TB", "2TB", "4TB", "8TB"]),
      sel("interface", "Interface", "interface", ["SATA", "NVMe Gen3", "NVMe Gen4", "NVMe Gen5", "NVMe"]),
      sel("nand_type", "Flash Type", "nand_type", ["TLC", "QLC", "MLC", "SLC"]),
    ],
  },
  {
    label: "Portable SSD", db: "PORTABLE SSD", icon: "HardDrive", filters: [
      sel("capacity", "Capacity", "capacity", ["128GB", "256GB", "500GB", "512GB", "1TB", "2TB", "4TB"]),
      sel("interface", "Interface", "interface", ["USB 3.2 Gen2", "USB 3.2", "USB-C", "USB 3.0"]),
    ],
  },
  {
    label: "HDD", db: "HDD", icon: "HardDrive", filters: [
      sel("capacity", "Capacity", "capacity", ["500GB", "1TB", "2TB", "4TB", "6TB", "8TB", "10TB", "12TB", "14TB", "16TB", "18TB", "20TB"]),
      sel("rpm", "RPM", "rpm", ["5400RPM", "5900RPM", "7200RPM"]),
      sel("cache", "Cache", "cache", ["64MB", "128MB", "256MB", "512MB"]),
    ],
  },
  {
    label: "Portable HDD", db: "PORTABLE HDD", icon: "HardDrive", filters: [
      sel("capacity", "Capacity", "capacity", ["500GB", "1TB", "2TB", "4TB", "5TB"]),
    ],
  },
  {
    label: "PSU", db: "PSU", icon: "Power", filters: [
      sel("wattage", "Wattage", "wattage", ["350W", "450W", "500W", "550W", "650W", "750W", "850W", "1000W", "1200W", "1600W"]),
      sel("efficiency", "80+ Certification", "efficiency", ["80+", "80+ Bronze", "80+ Silver", "80+ Gold", "80+ Platinum", "80+ Titanium"]),
      sel("modularity", "Modularity", "modularity", ["Non-Modular", "Semi-Modular", "Fully Modular"]),
      bool("atx30", "ATX 3.0 / PCIe 5.0"),
    ],
  },
  {
    label: "CPU Cooler", db: "CPU COOLER", icon: "Fan", filters: [
      sel("type", "Type", "type", ["Air", "AIO 120mm", "AIO 240mm", "AIO 280mm", "AIO 360mm", "AIO 420mm"]),
      sel("radiator_size", "Radiator Size", "radiator_size", ["120mm", "240mm", "280mm", "360mm", "420mm"]),
    ],
  },
  {
    label: "Casing Cooler", db: "CASING COOLER", icon: "Fan", filters: [
      sel("fan_size", "Fan Size", "fan_size", ["80mm", "92mm", "120mm", "140mm", "200mm"]),
    ],
  },
  {
    label: "Casing", db: "CASING", icon: "Box", filters: [
      sel("form_factor", "Case Type", "form_factor", ["Full Tower", "Mid Tower", "Micro-ATX", "Mini-ITX"]),
      sel("side_panel", "Side Panel", "side_panel", ["Tempered Glass", "Mesh", "Acrylic", "Solid"]),
      sel("color", "Color", "color", ["Black", "White", "Silver", "Red", "Blue", "Green"]),
      bool("front_usb_c", "Front USB Type-C"),
    ],
  },
];

export const SORT_OPTIONS: { label: string; value: string }[] = [
  { label: "Most Compared", value: "store_count_desc" },
  { label: "Biggest Savings", value: "savings_desc" },
  { label: "Price: Low → High", value: "price_asc" },
  { label: "Price: High → Low", value: "price_desc" },
  { label: "Name A–Z", value: "name" },
];

export const PAGE_SIZE = 20;

// Per-retailer accent colors for the price-history chart & badges.
export const RETAILER_COLORS: Record<string, string> = {
  StarTech: "#f43f4b",
  Ryans: "#22c55e",
  Techland: "#3b82f6",
  "Techland BD": "#3b82f6",
  UltraTech: "#a855f7",
  UCC: "#eab308",
  BinaryLogic: "#06b6d4",
  PotakaIT: "#f97316",
  Skyland: "#14b8a6",
  Creatus: "#ec4899",
  SellTech: "#8b5cf6",
  ComputerSource: "#0ea5e9",
  TrustTech: "#84cc16",
  PCHouse: "#f59e0b",
};

export function retailerColor(name: string): string {
  return RETAILER_COLORS[name] ?? "#8a8a99";
}
