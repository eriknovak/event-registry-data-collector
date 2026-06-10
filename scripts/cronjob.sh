#!/bin/bash

# go to the root of the project
cd "$(dirname "$0")/.." || exit 1

# activate the local virtual environment if present (fallback for non-uv setups)
if ! command -v uv &> /dev/null && [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

# run the collector module with uv if available, otherwise fall back to python3
run_collector() {
    if command -v uv &> /dev/null; then
        uv run python -m collector "$@"
    else
        python3 -m collector "$@"
    fi
}

# get current week (specify the interval of documents to collect)
CURRENT_WEEK="$(date -d "-7days" +"%Y-%m-%d")"
echo "$CURRENT_WEEK"

# get the events about the Slovenian EU presidency
run_collector \
    events \
    --max_repeat_request=5 \
    --concepts="Presidency of the Council of the European Union,Slovenia" \
    --date_start="$CURRENT_WEEK" \
    --save_to_file="./data/eu2021sl/$CURRENT_WEEK.jsonl"

# get the articles of the events acquired with the above command
run_collector \
    event_articles_from_file \
    --max_repeat_request=5 \
    --event_ids_file="./data/eu2021sl/$CURRENT_WEEK.jsonl" \
    --save_to_file="./data/eu2021sl/$CURRENT_WEEK"
