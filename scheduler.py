"""
Scheduler daemon for the scraping pipeline.

Cycles through all categories in round-robin order, pausing between each cycle.
Logs everything to logs/scheduler.log (same file the API tail reads).

Usage:
  python scheduler.py                             # all categories, 12-hour cycle
  python scheduler.py --interval-hours 6          # 6-hour cycle
  python scheduler.py --once                      # run every category once and exit
  python scheduler.py --categories ram gpu ssd    # only these categories
  python scheduler.py --retailers startech ryans  # only these retailers
  python scheduler.py --dry-run                   # pipeline dry-run (no DB writes)

The scheduler records every run in the scraper_runs table so the Streamlit
Health Dashboard and the API /scrapers/status endpoint can show history.
"""

import argparse
import logging
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv()

LOG_DIR  = Path("logs")
LOG_FILE = LOG_DIR / "scheduler.log"

CATEGORIES = [
    "ram", "laptop_ram", "gpu", "processor", "motherboard",
    "ssd", "portable_ssd", "hdd", "portable_hdd",
    "psu", "cooler", "casing_cooler", "casing",
    "monitor", "keyboard", "mouse", "headset", "ups",
    "speaker", "webcam", "gaming_chair", "printer", "mousepad", "gamepad",
]

ALL_RETAILERS = [
    "startech", "ryans", "techland", "potakait", "ucc",
    "ultratech", "binarylogic", "skyland", "creatus",
    "selltech", "computersource", "trusttech", "pchouse",
    "ezgadgets", "vibegaming",
]


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(exist_ok=True)
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger("scheduler")


log = _setup_logging()


# ---------------------------------------------------------------------------
# Database helpers (standalone connection — no FastAPI pool needed)
# ---------------------------------------------------------------------------

def _db_connect():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "pc_comparison"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )


def _create_run(conn, category: str, retailers: list[str]) -> int | None:
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO scraper_runs (category, retailers, status) "
                "VALUES (%s, %s, 'RUNNING') RETURNING id",
                (category, retailers),
            )
            run_id = cur.fetchone()[0]
        conn.commit()
        return run_id
    except Exception as exc:
        log.warning("Could not create scraper_run row: %s", exc)
        try:
            conn.rollback()
        except Exception:
            pass
        return None


_FINISH_SQL = """
    UPDATE scraper_runs
    SET status         = %s,
        finished_at    = NOW(),
        products_count = %s,
        prices_count   = %s,
        error_message  = %s
    WHERE id = %s
"""


def _finish_run(
    conn,
    run_id: int,
    status: str,
    products: int,
    prices: int,
    error: str | None,
) -> None:
    """Mark a run finished, reconnecting if the connection died meanwhile.

    A category takes 20-40 minutes and this connection is opened before the
    scrape starts, so it sits idle throughout. Neon's pooler drops idle
    connections well inside that window, which used to fail this update with
    "SSL connection has been closed unexpectedly" and leave the row stuck on
    RUNNING forever - the Scraper dashboard then showed finished categories as
    still in progress.
    """
    params = (status, products, prices, error, run_id)
    for attempt in (1, 2):
        try:
            with conn.cursor() as cur:
                cur.execute(_FINISH_SQL, params)
            conn.commit()
            return
        except Exception as exc:
            try:
                conn.rollback()
            except Exception:
                pass
            if attempt == 1:
                log.info("Run-tracking connection died (%s); reconnecting.", exc)
                try:
                    conn = _db_connect()
                    continue
                except Exception as reconnect_exc:
                    log.warning("Reconnect failed: %s", reconnect_exc)
                    return
            log.warning("Could not update scraper_run %d: %s", run_id, exc)
            return


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------

def run_category(category: str, retailers: list[str], dry_run: bool = False,
                 no_cutouts: bool = False) -> bool:
    """Run the pipeline for one category. Returns True on success."""
    log.info("▶  Starting: category=%s  retailers=%s", category, retailers)

    conn: psycopg2.connection | None = None
    run_id: int | None = None

    try:
        conn   = _db_connect()
        run_id = _create_run(conn, category, retailers)
    except Exception as exc:
        log.warning("DB unavailable for run tracking: %s", exc)

    cmd = [sys.executable, "run_pipeline.py", "--category", category,
           "--retailers"] + retailers
    if dry_run:
        cmd.append("--dry-run")
    if no_cutouts:
        cmd.append("--no-cutouts")

    products_count = 0
    prices_count   = 0
    error_msg: str | None = None
    success = False

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        out = proc.stdout
        if proc.stderr.strip():
            out += "\n" + proc.stderr

        # Append full output to log file
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(f"\n{'='*60}\n")
            ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
            fh.write(f"[{ts}] run_id={run_id}  category={category}\n")
            fh.write(out)
            fh.write("\n")

        if proc.returncode != 0:
            error_msg = f"Exited with code {proc.returncode}"
            log.error("✗  FAILED: category=%s — %s", category, error_msg)
        else:
            success = True
            m = re.search(r"Products\s+inserted\s*:\s*(\d+)", out)
            if m:
                products_count = int(m.group(1))
            m = re.search(r"Prices\s+inserted\s*:\s*(\d+)", out)
            if m:
                prices_count = int(m.group(1))
            log.info(
                "✓  Done:  category=%s  products=%d  prices=%d",
                category, products_count, prices_count,
            )

    except Exception as exc:
        error_msg = str(exc)
        log.error("✗  Exception: category=%s — %s", category, exc)

    if conn is not None and run_id is not None:
        _finish_run(
            conn, run_id,
            "SUCCESS" if success else "FAILED",
            products_count, prices_count, error_msg,
        )

    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass

    return success


# ---------------------------------------------------------------------------
# Alert evaluation — runs after each full sweep
# ---------------------------------------------------------------------------

def _evaluate_alerts(dry_run: bool = False) -> None:
    """
    Check all untriggered price-drop alerts against current prices.
    Marks triggered ones in the DB. The alerts table must exist
    (migration_v6_alerts.sql). Silently skips if the table doesn't exist yet.
    """
    if dry_run:
        log.info("Alerts: skipping (dry-run mode)")
        return
    try:
        conn = _db_connect()
        try:
            from backend import queries as _queries  # lazy import
            triggered = _queries.evaluate_alerts(conn)
            if triggered:
                log.info(
                    "Alerts: %d triggered — %s",
                    len(triggered),
                    [f"{t['product_name']} ≤ ৳{t['target_price']}" for t in triggered],
                )
            else:
                log.info("Alerts: none triggered this sweep")
        except Exception as exc:
            log.warning("Alerts evaluation error: %s", exc)
        finally:
            conn.close()
    except Exception as exc:
        log.warning("Could not connect for alert evaluation: %s", exc)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Scraper scheduler daemon")
    parser.add_argument(
        "--interval-hours", type=float, default=12.0,
        help="Hours to wait between full sweeps (default: 12)",
    )
    parser.add_argument(
        "--categories", nargs="+", choices=CATEGORIES, default=CATEGORIES,
        metavar="CATEGORY",
        help="Categories to schedule (default: all 24)",
    )
    parser.add_argument(
        "--retailers", nargs="+", choices=ALL_RETAILERS, default=ALL_RETAILERS,
        metavar="RETAILER",
        help="Retailers to include (default: all 15)",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Run all categories once then exit (no loop)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Pass --dry-run to run_pipeline.py (no DB writes to products/prices)",
    )
    parser.add_argument(
        "--no-cutouts", action="store_true",
        help="Skip per-category background removal. Used by CI, which runs the "
             "cutout pass once at the end instead — only that job holds the R2 "
             "credentials the uploads need.",
    )
    args = parser.parse_args()

    categories = args.categories
    retailers  = args.retailers
    interval_s = args.interval_hours * 3600

    log.info(
        "Scheduler started — %d categories, interval=%.1fh%s",
        len(categories), args.interval_hours,
        " [--once]" if args.once else "",
    )
    log.info("Categories : %s", categories)
    log.info("Retailers  : %s", retailers)

    if args.once:
        failed = [cat for cat in categories
                  if not run_category(cat, retailers, args.dry_run, args.no_cutouts)]
        _evaluate_alerts(args.dry_run)
        if failed:
            # Exit non-zero so a CI run goes red. Previously every category could
            # fail and the job still reported success, because the failure was
            # only ever written to the log - the same silent-green problem that
            # let Ryans and Skyland sit stale for 54 days.
            log.error("--once complete with %d failed categor%s: %s",
                      len(failed), "y" if len(failed) == 1 else "ies",
                      ", ".join(failed))
            sys.exit(1)
        log.info("--once complete, exiting.")
        return

    while True:
        sweep_start = time.monotonic()
        log.info("=== Sweep started ===")

        for cat in categories:
            run_category(cat, retailers, args.dry_run, args.no_cutouts)

        _evaluate_alerts(args.dry_run)

        elapsed = time.monotonic() - sweep_start
        wait    = max(0.0, interval_s - elapsed)
        log.info(
            "=== Sweep done in %.1f min. Next in %.1f h ===",
            elapsed / 60, wait / 3600,
        )
        if wait > 0:
            time.sleep(wait)


if __name__ == "__main__":
    main()
