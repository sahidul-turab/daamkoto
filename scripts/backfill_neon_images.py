"""
Backfill product images into the Neon (production) DB — minimal storage.

Does NOT re-load or re-scrape (which would append 100k+ rows). Instead:
  1. Reads the (product_url -> image_url) map + image_cutouts from LOCAL Postgres.
  2. Stages the map in a Neon TEMP table and UPDATEs prices.image_url by product_url.
  3. Inserts image_cutouts into Neon with cutout_path rewritten to the R2 public URL.
  4. Refreshes mv_current_prices.
Measures DB size before/after and reports live-view coverage.

Reads local creds from .env, Neon from .env.neon, R2 base from .env.r2.
"""
import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()            # local DB
load_dotenv(".env.neon")
load_dotenv(".env.r2")

R2_BASE = os.environ["R2_PUBLIC_BASE"].rstrip("/")


def local_conn():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"), port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "pc_comparison"), user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )


def size(cur):
    cur.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
    return cur.fetchone()[0]


def main():
    # --- pull maps from local ---
    lc = local_conn(); lc.autocommit = True; lcur = lc.cursor()
    lcur.execute("SELECT DISTINCT product_url, image_url FROM prices WHERE image_url IS NOT NULL AND product_url IS NOT NULL")
    url_map = lcur.fetchall()
    print(f"local: {len(url_map)} distinct (product_url -> image_url) pairs")
    # image_cutouts: source_url + the sha1 hash embedded in the local cutout_path
    lcur.execute("SELECT source_url, cutout_path FROM image_cutouts")
    cutouts = []
    for src, path in lcur.fetchall():
        name = path.rsplit("/", 1)[-1]           # <hash>.png
        cutouts.append((src, f"{R2_BASE}/cutouts/{name}"))
    print(f"local: {len(cutouts)} cutouts to register on Neon")
    lc.close()

    # --- write to Neon ---
    nc = psycopg2.connect(os.environ["NEON_URL"]); nc.autocommit = False; ncur = nc.cursor()
    print("Neon size BEFORE:", size(ncur))

    # 1. stage product_url -> image_url and UPDATE prices
    ncur.execute("CREATE TEMP TABLE _img_map (product_url TEXT, image_url TEXT) ON COMMIT DROP")
    psycopg2.extras.execute_values(ncur, "INSERT INTO _img_map (product_url, image_url) VALUES %s", url_map, page_size=1000)
    ncur.execute("CREATE INDEX ON _img_map (product_url)")
    ncur.execute("""
        UPDATE prices p SET image_url = m.image_url
        FROM _img_map m
        WHERE p.product_url = m.product_url AND p.image_url IS DISTINCT FROM m.image_url
    """)
    updated = ncur.rowcount
    print(f"prices rows updated with image_url: {updated}")

    # 2. register cutouts (source_url -> R2 url)
    psycopg2.extras.execute_values(
        ncur,
        """INSERT INTO image_cutouts (source_url, cutout_path) VALUES %s
           ON CONFLICT (source_url) DO UPDATE SET cutout_path = EXCLUDED.cutout_path""",
        cutouts, page_size=1000,
    )
    print(f"image_cutouts registered: {len(cutouts)}")

    nc.commit()

    # 3. refresh the materialized view
    nc.autocommit = True
    ncur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_current_prices")
    print("mv refreshed")

    # --- report ---
    print("Neon size AFTER:", size(ncur))
    ncur.execute("SELECT count(*) FROM mv_current_prices WHERE image_url IS NOT NULL")
    with_img = ncur.fetchone()[0]
    ncur.execute("SELECT count(*) FROM mv_current_prices")
    total = ncur.fetchone()[0]
    ncur.execute("""SELECT count(*) FROM mv_current_prices m JOIN image_cutouts ic ON ic.source_url=m.image_url""")
    with_cut = ncur.fetchone()[0]
    print(f"live listings: {total} | with image_url: {with_img} | with cutout: {with_cut}")
    nc.close()


if __name__ == "__main__":
    import io, sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
