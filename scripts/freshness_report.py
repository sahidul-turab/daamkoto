"""
Report how fresh the price data is, per retailer and per category.

Why this exists: a scraper that returns zero products still exits 0. The
pipeline then normalizes an empty list, loads nothing, and the previous prices
survive untouched - so the run looks green while the data silently ages. That is
exactly how Ryans and Skyland sat frozen for 54 days without a single failed run.

This turns that silence into a visible signal. Run it after a sweep.

Exit codes:
  0  every retailer refreshed within STALE_DAYS
  1  a majority of retailers are stale - looks systemic (IP block, site-wide
     change, DB not actually written), so the run should go red
Individually stale retailers are reported as warnings but do not fail the run,
because one broken scraper should not hide the other twelve working.

Usage:
  python scripts/freshness_report.py
  python scripts/freshness_report.py --stale-days 3
"""

import argparse
import os
import sys

import psycopg2
from dotenv import load_dotenv

load_dotenv()

STALE_DAYS = 2


def _connect():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "pc_comparison"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        connect_timeout=15,
    )


def _emit(lines: list[str]) -> None:
    """Print, and also append to the GitHub Actions run summary when present."""
    text = "\n".join(lines)
    print(text)
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        try:
            with open(summary_path, "a", encoding="utf-8") as fh:
                fh.write(text + "\n")
        except OSError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Report price data freshness")
    parser.add_argument("--stale-days", type=float, default=STALE_DAYS,
                        help=f"Age in days past which a retailer counts as stale (default: {STALE_DAYS})")
    args = parser.parse_args()

    conn = _connect()
    lines: list[str] = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT r.name,
                       max(p.scraped_at) AS newest,
                       EXTRACT(EPOCH FROM (NOW() - max(p.scraped_at))) / 86400 AS days_old
                FROM prices p
                JOIN retailers r ON r.id = p.retailer_id
                GROUP BY r.name
                ORDER BY days_old
                """
            )
            retailer_rows = cur.fetchall()

            cur.execute(
                """
                SELECT pr.category,
                       EXTRACT(EPOCH FROM (NOW() - max(p.scraped_at))) / 86400 AS days_old
                FROM prices p
                JOIN products pr ON pr.id = p.product_id
                GROUP BY pr.category
                ORDER BY days_old
                """
            )
            category_rows = cur.fetchall()
    finally:
        conn.close()

    stale = [r for r in retailer_rows if r[2] is not None and r[2] > args.stale_days]

    lines.append("## Data freshness")
    lines.append("")
    lines.append("| Retailer | Newest price | Age | Status |")
    lines.append("|---|---|---|---|")
    for name, newest, days_old in retailer_rows:
        days = float(days_old or 0)
        mark = "OK" if days <= args.stale_days else "STALE"
        lines.append(f"| {name} | {newest:%Y-%m-%d %H:%M} | {days:.1f}d | {mark} |")

    lines.append("")
    lines.append("| Category | Age |")
    lines.append("|---|---|")
    for category, days_old in category_rows:
        lines.append(f"| {category} | {float(days_old or 0):.1f}d |")

    lines.append("")
    if not stale:
        lines.append(f"All {len(retailer_rows)} retailers refreshed within {args.stale_days:g} day(s).")
        _emit(lines)
        return 0

    names = ", ".join(r[0] for r in stale)
    lines.append(f"**{len(stale)} of {len(retailer_rows)} retailers are stale:** {names}")

    if len(stale) > len(retailer_rows) / 2:
        lines.append("")
        lines.append("Most retailers went stale at once - this looks systemic "
                     "(IP block, or the database was never written). Failing the run.")
        _emit(lines)
        return 1

    lines.append("")
    lines.append("Treating as a per-scraper problem, not a run failure.")
    _emit(lines)
    return 0


if __name__ == "__main__":
    sys.exit(main())
