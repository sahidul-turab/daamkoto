"""
Probe URLs for new/split categories across all retailers.
Uses requests (no JS needed — just checking HTTP status and product count).
"""

import io
import sys
import time
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

CANDIDATES = {
    "StarTech": [
        # Laptop RAM
        ("laptop_ram", "https://www.startech.com.bd/laptop-components/laptop-ram"),
        ("laptop_ram", "https://www.startech.com.bd/laptop-components/ram"),
        # Casing fan / case cooler
        ("casing_cooler", "https://www.startech.com.bd/component/casing-fan"),
        ("casing_cooler", "https://www.startech.com.bd/component/fan"),
        # ODD
        ("odd", "https://www.startech.com.bd/component/optical-drive"),
        ("odd", "https://www.startech.com.bd/laptop-components/optical-drive"),
        ("odd", "https://www.startech.com.bd/component/dvd"),
        # Portable HDD
        ("portable_hdd", "https://www.startech.com.bd/storage/portable-hdd"),
        ("portable_hdd", "https://www.startech.com.bd/component/external-hdd"),
        ("portable_hdd", "https://www.startech.com.bd/storage/external-hard-disk"),
        # Portable SSD
        ("portable_ssd", "https://www.startech.com.bd/storage/portable-ssd"),
        ("portable_ssd", "https://www.startech.com.bd/component/external-ssd"),
        ("portable_ssd", "https://www.startech.com.bd/storage/external-ssd"),
    ],
    "Ryans": [
        # Laptop RAM
        ("laptop_ram", "https://www.ryans.com/category/laptop-component-ram"),
        ("laptop_ram", "https://www.ryans.com/category/laptop-memory"),
        ("laptop_ram", "https://www.ryans.com/category/laptop-component-laptop-ram"),
        # Casing fan
        ("casing_cooler", "https://www.ryans.com/category/desktop-component-casing-fan"),
        ("casing_cooler", "https://www.ryans.com/category/casing-fan"),
        ("casing_cooler", "https://www.ryans.com/category/desktop-component-fan"),
        # ODD
        ("odd", "https://www.ryans.com/category/desktop-component-optical-drive"),
        ("odd", "https://www.ryans.com/category/laptop-component-optical-drive"),
        ("odd", "https://www.ryans.com/category/optical-drive"),
        # Portable HDD
        ("portable_hdd", "https://www.ryans.com/category/portable-hdd"),
        ("portable_hdd", "https://www.ryans.com/category/external-hdd"),
        ("portable_hdd", "https://www.ryans.com/category/storage-external-hard-disk"),
        # Portable SSD
        ("portable_ssd", "https://www.ryans.com/category/portable-ssd"),
        ("portable_ssd", "https://www.ryans.com/category/external-ssd"),
    ],
    "Techland": [
        # Laptop RAM
        ("laptop_ram", "https://www.techlandbd.com/laptop-components/laptop-ram"),
        ("laptop_ram", "https://www.techlandbd.com/laptop-components/ram"),
        ("laptop_ram", "https://www.techlandbd.com/pc-components/laptop-ram"),
        # Casing fan
        ("casing_cooler", "https://www.techlandbd.com/pc-components/casing-fan"),
        ("casing_cooler", "https://www.techlandbd.com/pc-components/fan"),
        ("casing_cooler", "https://www.techlandbd.com/pc-components/case-fan"),
        # ODD
        ("odd", "https://www.techlandbd.com/pc-components/optical-drive"),
        ("odd", "https://www.techlandbd.com/laptop-components/optical-drive"),
        # Portable HDD
        ("portable_hdd", "https://www.techlandbd.com/storage/portable-hdd"),
        ("portable_hdd", "https://www.techlandbd.com/pc-components/portable-hdd"),
        ("portable_hdd", "https://www.techlandbd.com/storage/external-hard-drive"),
        # Portable SSD
        ("portable_ssd", "https://www.techlandbd.com/storage/portable-ssd"),
        ("portable_ssd", "https://www.techlandbd.com/pc-components/portable-ssd"),
        ("portable_ssd", "https://www.techlandbd.com/storage/external-ssd"),
    ],
    "PotakaIT": [
        ("laptop_ram", "https://www.potakait.com/laptop-ram"),
        ("laptop_ram", "https://www.potakait.com/ram-laptop"),
        ("casing_cooler", "https://www.potakait.com/casing-fan"),
        ("casing_cooler", "https://www.potakait.com/case-fan"),
        ("odd", "https://www.potakait.com/optical-drive"),
        ("odd", "https://www.potakait.com/dvd-drive"),
        ("portable_hdd", "https://www.potakait.com/portable-hdd"),
        ("portable_hdd", "https://www.potakait.com/external-hdd"),
        ("portable_ssd", "https://www.potakait.com/portable-ssd"),
        ("portable_ssd", "https://www.potakait.com/external-ssd"),
    ],
    "UCC": [
        ("laptop_ram", "https://www.ucc.com.bd/laptop-ram"),
        ("laptop_ram", "https://www.ucc.com.bd/laptop-memory"),
        ("casing_cooler", "https://www.ucc.com.bd/casing-fan"),
        ("casing_cooler", "https://www.ucc.com.bd/case-fan"),
        ("odd", "https://www.ucc.com.bd/optical-drive"),
        ("portable_hdd", "https://www.ucc.com.bd/portable-hdd"),
        ("portable_hdd", "https://www.ucc.com.bd/external-hdd"),
        ("portable_ssd", "https://www.ucc.com.bd/portable-ssd"),
        ("portable_ssd", "https://www.ucc.com.bd/external-ssd"),
    ],
    "UltraTech": [
        ("laptop_ram", "https://www.ultratech.com.bd/laptop-ram"),
        ("laptop_ram", "https://www.ultratech.com.bd/laptop-memory"),
        ("casing_cooler", "https://www.ultratech.com.bd/casing-fan"),
        ("casing_cooler", "https://www.ultratech.com.bd/case-fan"),
        ("casing_cooler", "https://www.ultratech.com.bd/fan"),
        ("odd", "https://www.ultratech.com.bd/optical-drive"),
        ("odd", "https://www.ultratech.com.bd/dvd"),
        ("portable_hdd", "https://www.ultratech.com.bd/portable-hdd"),
        ("portable_hdd", "https://www.ultratech.com.bd/external-hdd"),
        ("portable_ssd", "https://www.ultratech.com.bd/portable-ssd"),
        ("portable_ssd", "https://www.ultratech.com.bd/external-ssd"),
    ],
    "BinaryLogic": [
        ("laptop_ram", "https://www.binarylogic.com.bd/laptop-ram"),
        ("laptop_ram", "https://www.binarylogic.com.bd/laptop-memory"),
        ("casing_cooler", "https://www.binarylogic.com.bd/casing-fan"),
        ("casing_cooler", "https://www.binarylogic.com.bd/case-fan"),
        ("odd", "https://www.binarylogic.com.bd/optical-drive"),
        ("portable_hdd", "https://www.binarylogic.com.bd/portable-hdd"),
        ("portable_hdd", "https://www.binarylogic.com.bd/external-hdd"),
        ("portable_ssd", "https://www.binarylogic.com.bd/portable-ssd"),
        ("portable_ssd", "https://www.binarylogic.com.bd/external-ssd"),
    ],
}

SEEN_WORKING = set()  # avoid re-checking same URL

def probe(retailer: str, category: str, url: str) -> tuple[bool, int]:
    if url in SEEN_WORKING:
        return False, 0
    try:
        r = requests.get(url, headers=HEADERS, timeout=12, allow_redirects=True)
        if r.status_code == 200:
            # Quick product count heuristic — look for product-related markup
            text = r.text
            # Count rough indicators
            count = 0
            for marker in [
                'p-item', 'product-item', 'products-list__item',
                'data-item', 'single-product', 'product-card',
                'product__name', 'price', 'BDT', '৳'
            ]:
                count += text.count(marker)
            return True, count
        return False, 0
    except Exception as e:
        return False, 0


results = {}  # retailer -> category -> best_url

for retailer, candidates in CANDIDATES.items():
    print(f"\n{'='*60}")
    print(f"  {retailer}")
    print(f"{'='*60}")
    retailer_results = {}

    for category, url in candidates:
        ok, score = probe(retailer, category, url)
        status = f"OK score={score:>6}" if ok else "NO"
        print(f"  [{status}]  {category:<15}  {url}")

        if ok and score > 50:  # reasonable product page
            if category not in retailer_results or score > retailer_results[category][1]:
                retailer_results[category] = (url, score)
        time.sleep(0.5)

    results[retailer] = retailer_results

print(f"\n\n{'='*60}")
print("  WINNERS — best URL per retailer per category")
print(f"{'='*60}")
for retailer, cats in results.items():
    if cats:
        print(f"\n  {retailer}:")
        for cat, (url, score) in cats.items():
            print(f"    {cat:<18}: {url}  (score={score})")
    else:
        print(f"\n  {retailer}: (none)")
