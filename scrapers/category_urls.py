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
    "ezgadgets":      ("https://ggezgadgets.com",        ".wd-product"),
    "vibegaming":     ("https://vibegaming.com.bd",      "section.product[data-product_id]"),
}

# EZ Gadgets and Vibe Gaming are deliberately absent from CATEGORY_PATHS below.
# Both are WooCommerce, so their paths are multi-segment
# (/product-category/pc-components/graphics-card/) and both cover core components
# as well as peripherals, so recording half of them here would leave two partial
# sources of truth. Vibe Gaming additionally needs *several* listing URLs for one
# category, which this file's category -> {retailer: path} shape cannot express.
# Their full category maps live in scrapers/gen_ezgadgets_scrapers.py and
# scrapers/gen_vibegaming_scrapers.py, which are also what generate their
# scrapers.

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

    # Ryans nests these under a section rather than the category name, and only
    # its "All Brands" link is the full listing - every other entry in the menu
    # is one brand. Hence desktop-component-* / audio-video-* here.
    "keyboard": {
        "startech":       "/accessories/keyboards",
        "ryans":          "/category/desktop-component-keyboard",
        "techland":       "/accessories/computer-keyboard",
        "potakait":       "/keyboards",
        "ucc":            "/keyboards",
        "ultratech":      "/keyboard",
        "binarylogic":    "/keyboard-mouse",
        "skyland":        "/accessories/keyboard",
        "creatus":        "/keyboard",
        "selltech":       "/Keyboard",
        "computersource": "/keyboard",
        "trusttech":      "/categories/keyboard",
        "pchouse":        "/keyboard",
    },

    "mouse": {
        "startech":       "/accessories/mouse",
        "ryans":          "/category/desktop-component-mouse",
        "techland":       "/accessories/shop-computer-mouse",
        "potakait":       "/gaming-mouse",
        "ucc":            "/mice",
        "ultratech":      "/mouse",
        "binarylogic":    "/keyboard-mouse",
        "skyland":        "/accessories/mouse",
        "creatus":        "/mouse",
        "selltech":       "/Mouse",
        "computersource": "/mouse",
        "trusttech":      "/categories/mouse",
        "pchouse":        "/mouse",
    },

    "headset": {
        "startech":       "/accessories/headphone",
        "ryans":          "/category/audio-video-headphone",
        "techland":       "/accessories/headphone-speaker/shop-headphones-headsets",
        "potakait":       "/headphones",
        "ucc":            "/headset",
        "ultratech":      "/headphone",
        "binarylogic":    "/headphone",
        "skyland":        "/sound-system/headphone",
        "creatus":        "/headphone",
        "selltech":       "/Headphone",
        "computersource": "/headphone",
        "trusttech":      "/categories/headphone",
        "pchouse":        "/headphones-headsets",
    },

    # ── Tier 2 ───────────────────────────────────────────────────────────────

    "speaker": {
        "ryans":          "/category/all-speaker",
        "techland":       "/tv-home-entertainment/multimedia-speakers",
        "potakait":       "/bluetooth-speaker",
        "ultratech":      "/speaker",
        "binarylogic":    "/speaker",
        "skyland":        "/sound-system/speaker-and-home-theater",
        "creatus":        "/speaker",
        "selltech":       "/Bluetooth-Speakers",
        "computersource": "/speaker",
        "trusttech":      "/categories/speaker",
        "pchouse":        "/speakers",
    },

    "webcam": {
        "startech":  "/accessories/webcam",
        "ryans":     "/category/camera-webcam",
        "techland":  "/accessories/brand-webcam",
        "potakait":  "/webcams",
        "ultratech": "/webcam",
        "skyland":   "/accessories/webcam",
        "creatus":   "/webcam",
        "selltech":  "/Webcam",
    },

    "gaming_chair": {
        "startech":  "/gaming-chair",
        "ryans":     "/category/gaming-component-gaming-chair",
        "potakait":  "/gaming-chair",
        "ucc":       "/gaming-chair",
        "ultratech": "/gaming-chair",
        "skyland":   "/gaming/gaming-chair",
        "creatus":   "/gaming-chair",
        "trusttech": "/categories/gaming-chair",
        "pchouse":   "/gaming-chair",
    },

    "printer": {
        "startech":    "/printer",
        "ryans":       "/category/document-printer-laser-printer",
        "techland":    "/office-solution/printer",
        "potakait":    "/printers",
        "ultratech":   "/printer",
        "binarylogic": "/printer",
        "skyland":     "/office-equipment/printer",
        "creatus":     "/printer",
        "selltech":    "/Printer",
        "trusttech":   "/categories/printer",
    },

    "mousepad": {
        "startech":  "/accessories/mouse-pad",
        "ryans":     "/category/desktop-component-mouse-pad",
        "ultratech": "/mouse-pad",
        "skyland":   "/accessories/mouse-pad",
        "creatus":   "/mouse-pad",
        "selltech":  "/Mouse-Pad",
        "pchouse":   "/mouse-pad",
    },

    # Thinnest of the six. StarTech's only match was /gaming-console, which
    # lists PlayStations and Xboxes rather than controllers - left out on
    # purpose, since a category polluted with consoles is worse than a category
    # with fewer shops. Ryans, Techland, UCC, SellTech, BinaryLogic and
    # TrustTech have no browsable gamepad listing at all.
    "gamepad": {
        "potakait":       "/gamepads",
        "ultratech":      "/gamepad",
        "skyland":        "/gaming/gamepad",
        "creatus":        "/gamepad",
        "computersource": "/gamepad",
        "pchouse":        "/gamepad",
    },

    # ucc, binarylogic and computersource have no browsable UPS listing.
    "ups": {
        "startech":    "/ups",
        "ryans":       "/category/desktop-component-ups",
        "techland":    "/ups",
        "potakait":    "/offline-ups",
        "ultratech":   "/ups",
        "skyland":     "/ups",
        "creatus":     "/ups",
        "selltech":    "/offline-ups",
        "trusttech":   "/categories/ups",
        "pchouse":     "/offline-ups",
    },
}
