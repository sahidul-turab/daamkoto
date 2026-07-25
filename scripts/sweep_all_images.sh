#!/usr/bin/env bash
# Re-scrape every category (patched scrapers now capture image_url) and remove
# backgrounds incrementally, so images appear on the site category-by-category
# rather than all at once. Ordered by catalogue size (highest value first).
# Logs to logs/sweep_images.log.
set -u
cd "$(dirname "$0")/.." || exit 1
PY="venv/Scripts/python.exe"
LOG="logs/sweep_images.log"
mkdir -p logs
echo "=== sweep started $(date) ===" | tee -a "$LOG"

# Catch anything already scraped but not yet cut out (e.g. GPU from the canary).
echo ">>> [$(date +%H:%M:%S)] initial bg-removal pass (GPU + leftovers)" | tee -a "$LOG"
"$PY" scripts/remove_backgrounds.py --workers 6 >> "$LOG" 2>&1

# ram + gpu already scraped; do the rest, biggest first.
CATS="casing cooler psu casing_cooler processor portable_ssd hdd laptop_ram ups portable_hdd mousepad monitor keyboard mouse headset speaker webcam gaming_chair printer gamepad odd"

for cat in $CATS; do
  echo ">>> [$(date +%H:%M:%S)] scraping: $cat" | tee -a "$LOG"
  if "$PY" run_pipeline.py --category "$cat" >> "$LOG" 2>&1; then
    echo "    scrape OK: $cat — removing backgrounds" | tee -a "$LOG"
    "$PY" scripts/remove_backgrounds.py --workers 6 >> "$LOG" 2>&1
    echo "    $cat DONE ($(date +%H:%M:%S))" | tee -a "$LOG"
  else
    echo "    scrape FAILED: $cat" | tee -a "$LOG"
  fi
done

echo "=== sweep finished $(date) ===" | tee -a "$LOG"
