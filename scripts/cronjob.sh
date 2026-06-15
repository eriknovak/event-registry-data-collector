#!/bin/bash

# Periodic collection of recently completed weeks of Slovenian news.
#
# This is a thin wrapper around scripts/backfill.py with --weeks 2. It collects
# the two most recently completed Mon-Sun weeks and records coverage in the
# manifest (coverage.json), so periodic runs and historic backfills share one
# source of truth and never re-collect the same (source x week) combination.
# Already-covered windows are skipped at zero cost, so the extra week
# self-heals holes left by a missed cron run.
#
# Any extra flags are passed through to backfill.py, e.g. --output-dir, --lang.
#
# Register with cron, e.g. run every Monday at 02:30 and append to a log file:
#   30 2 * * 1 /path/to/scripts/cronjob.sh >> /path/to/cronjob.log 2>&1

# go to the root of the project
cd "$(dirname "$0")/.." || exit 1

echo "[$(date --iso-8601=seconds)] starting periodic collection"

# run the backfill driver with uv if available, otherwise fall back to python3
if command -v uv &> /dev/null; then
    uv run scripts/backfill.py --weeks 2 "$@"
else
    python3 scripts/backfill.py --weeks 2 "$@"
fi
