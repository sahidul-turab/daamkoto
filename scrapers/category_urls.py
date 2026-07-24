"""
Verified listing URLs and card selectors per retailer, per category.

Each entry was confirmed with a real browser: the page must return HTTP 200 and
render at least five product cards. That bar exists because guessing slugs is
unreliable here - several shops answer any unknown path with a soft-404 that
still contains the full homepage navigation, so a naive "did it return 200 and
mention 'monitor'" check marks every guess as a hit.

Selectors differ per shop because only five of the thirteen run stock OpenCart.

Used by the scraper generator; keep it as the one place a category URL is
recorded, so adding a category is a data change rather than 13 edited files.
"""

# retailer -> (base_url, card_selector)
RETAILERS = {
    "startech":       ("https://www.startech.com.bd",    ".p-item"),
    "ryans":          ("https://www.ryans.com",          ".category-single-product"),
    "techland":       ("https://www.techlandbd.com",     "article.products-list__item"),
    "potakait":       ("https://potakait.com",           ".product-item"),
    "ucc":            ("https://www.ucc.com.bd",         ".product-thumb"),
    "ultratech":      ("https://www.ultratech.com.bd",   ".product-thumb"),
    "binarylogic":    ("https://www.binarylogic.com.bd", ".p-item"),
    "skyland":        ("https://www.skyland.com.bd",     ".product-thumb"),
    "creatus":        ("https://www.creatus.com.bd",     ".product-thumb"),
    "selltech":       ("https://www.selltech.com.bd",    ".product-thumb"),
    "computersource": ("https://computersource.com.bd",  ".product"),
    "trusttech":      ("https://www.trusttechbd.com",    ".product-card"),
    "pchouse":        ("https://www.pchouse.com.bd",     ".single-product-item"),
}

# category -> {retailer: path}. A retailer absent from a category either does
# not stock it or has no browsable listing page; that is a scraper we do not
# write rather than one that silently returns nothing.
CATEGORY_PATHS = {
    "monitor": {
        "startech":    "/monitor",
        "ryans":       "/category/monitor-all-monitor",
        "techland":    "/monitor-and-display/computer-monitor",
        "potakait":    "/monitors",
        "ucc":         "/monitors",
        "ultratech":   "/monitor",
        "binarylogic": "/monitor",
        "skyland":     "/monitor/monitor-and-displays",
        "creatus":     "/monitor",
        "selltech":    "/Monitor",
        "trusttech":   "/categories/monitor",
        "pchouse":     "/monitor",
        # computersource: no monitor listing found - /monitor, /monitors,
        # /desktop-monitor and /led-monitor all 404. Revisit.
    },
}
