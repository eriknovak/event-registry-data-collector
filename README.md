# Event Registry Data Collector

A command line tool for collecting news articles and events via the
[Event Registry](https://eventregistry.org) service. The source code is stored within the
[collector](./collector) folder.

## Table of Contents

- [Setup](#setup)
- [Quick Start](#quick-start)
- [Usage](#usage)
  - [Common Flags](#common-flags)
  - [Action: articles](#action-articles)
  - [Action: events](#action-events)
  - [Action: event](#action-event)
  - [Action: event_articles](#action-event_articles)
  - [Action: event_articles_from_file](#action-event_articles_from_file)
  - [Action: suggest](#action-suggest)
- [Complex Queries](#complex-queries)
- [More Examples](#more-examples)
- [Periodic Collection](#periodic-collection)
- [Development](#development)

## Setup

### 1. Install the dependencies

Install [uv](https://docs.astral.sh/uv/) (recommended) or Python 3.9+, then install the
project dependencies:

- uv (recommended)

  ```bash
  # create the .venv folder and install the dependencies from uv.lock
  uv sync
  ```

- pip (fallback)

  ```bash
  # create and activate a new virtual environment
  python3 -m venv .venv
  . .venv/bin/activate
  # install the project in editable mode
  pip install -e .
  ```

### 2. Configure the API key

Create a `.env` file in the root of the project and insert the Event Registry API key:

```bash
# create the .env file with the API key as the content
echo "API_KEY={insert-er-api-key}" > .env
```

## Quick Start

The project installs a `collect` CLI. With uv there is no need to activate the virtual
environment — run the commands through `uv run`. With the pip fallback, activate the
virtual environment and drop the `uv run` prefix.

```bash
# collect up to 10 English or Slovenian articles mentioning the given keywords
uv run collect articles \
    --max_repeat_request=5 \
    --keywords="Barrack Obama,Donald Trump" \
    --languages=eng,slv \
    --date_start=2019-01-01 \
    --max_items=10 \
    --save_to_file=./data/barrack_trump_articles.json
```

## Usage

The CLI is invoked as `collect {action} [flags]`, where `{action}` is one of:

| Action                                                            | Description                                                            |
| ----------------------------------------------------------------- | ----------------------------------------------------------------------- |
| [articles](#action-articles)                                       | Collect news articles matching the query                                |
| [events](#action-events)                                           | Collect news events matching the query                                  |
| [event](#action-event)                                             | Collect specific events given their ids                                 |
| [event_articles](#action-event_articles)                           | Collect the articles clustered in a single event                        |
| [event_articles_from_file](#action-event_articles_from_file)       | Collect the articles of multiple events, with the event ids from a file |
| [suggest](#action-suggest)                                         | Look up concept/category/source URIs for use in queries                 |

### Common Flags

The `articles`, `events`, `event_articles` and `event_articles_from_file` actions share the
following flags. The `event` action supports only `--max_repeat_request`, `--save_to_file`
and `--save_format`.

| Name                   | Optional | Description                                                                                                                                                                                                                                                                                                                                       |
| ---------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--max_repeat_request` | True     | The maximum number of repeated requests. If the value is -1, it repeats indefinitely (Default: -1)                                                                                                                                                                                                                                                |
| `--query_file`         | True     | `articles` and `events` only. The path to a JSON file containing a complex query in the Event Registry [advanced query language](https://github.com/EventRegistry/event-registry-python/wiki/Searching-for-articles#advanced-query-language). Cannot be combined with the keywords, concepts, categories, sources, languages, date_start or date_end parameters (Default: None) |
| `--keywords`           | True     | The comma separated keywords the items should contain (Default: None)                                                                                                                                                                                                                                                                            |
| `--concepts`           | True     | The comma separated concepts the items should be associated with (Default: None)                                                                                                                                                                                                                                                                 |
| `--categories`         | True     | The comma separated categories of the collected items (Default: None)                                                                                                                                                                                                                                                                            |
| `--sources`            | True     | The comma separated media sources that published the items (Default: None)                                                                                                                                                                                                                                                                       |
| `--languages`          | True     | The comma separated languages of the items (Default: None)                                                                                                                                                                                                                                                                                       |
| `--date_start`         | True     | The start date of the items. Format: YYYY-MM-DD (Default: None)                                                                                                                                                                                                                                                                                  |
| `--date_end`           | True     | The end date of the items. Format: YYYY-MM-DD (Default: None)                                                                                                                                                                                                                                                                                    |
| `--sort_by`            | True     | The sort order of the items (Default: `'date'` for `articles` and `events`, `'rel'` for `event_articles` and `event_articles_from_file`)                                                                                                                                                                                                         |
| `--sort_by_asc`        | True     | The direction of the sort (Default: True)                                                                                                                                                                                                                                                                                                        |
| `--max_items`          | True     | The number of items to collect. If its -1, then there is no limit (Default: -1)                                                                                                                                                                                                                                                                  |
| `--save_to_file`       | True     | The path to the file to store the items. For `articles` and `events`, if the file already exists, the date of the last stored item replaces the date_start parameter, so repeated runs only collect new items. For `event_articles_from_file`, this is the path to a **folder** (Default: None)                                                  |
| `--save_format`        | True     | The format in which to store the items. If `'array'`, it stores the items into an array of objects. Otherwise, each line consists of one item object (Default: None)                                                                                                                                                                             |
| `--verbose`            | True     | If true, outputs the query parameters retrieved by Event Registry (Default: False)                                                                                                                                                                                                                                                               |

### Action: articles

Acquires news articles matching the query. Supports all [common flags](#common-flags).

```bash
uv run collect articles \
    --max_repeat_request=5 \
    --keywords="Barrack Obama,Donald Trump" \
    --languages=eng,slv \
    --date_start=2019-01-01 \
    --max_items=10 \
    --save_to_file=./data/barrack_trump_articles.json
```

### Action: events

Acquires news events matching the query. Supports all [common flags](#common-flags).

```bash
uv run collect events \
    --max_repeat_request=5 \
    --keywords="Barrack Obama,Donald Trump" \
    --languages=eng,slv \
    --date_start=2019-01-01 \
    --max_items=10 \
    --save_to_file=./data/barrack_trump_events.jsonl
```

### Action: event

Acquires the information of specific events given their ids.

| Name                   | Optional | Description                                                                                                                                                             |
| ---------------------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--max_repeat_request` | True     | The maximum number of repeated requests. If the value is -1, it repeats indefinitely (Default: -1)                                                                     |
| `--event_ids`          | False    | The comma separated ids of the events to collect                                                                                                                        |
| `--save_to_file`       | True     | The path to the file to store the events (Default: None)                                                                                                                |
| `--save_format`        | True     | The format in which to store the events. If `'array'`, it stores the events into an array of objects. Otherwise, each line consists of one event object (Default: None) |

```bash
uv run collect event \
    --event_ids=eng-2940883,eng-2940884 \
    --save_to_file=./data/events.jsonl
```

### Action: event_articles

Acquires the news articles clustered in a certain event. Supports the
[common flags](#common-flags) (except `--query_file`) plus:

| Name         | Optional | Description                                                   |
| ------------ | -------- | --------------------------------------------------------------- |
| `--event_id` | False    | The id of the event for which we wish to collect the articles |

```bash
uv run collect event_articles \
    --max_repeat_request=5 \
    --event_id=eng-2940883 \
    --max_items=10 \
    --save_to_file=./data/eng-2940883.json
```

### Action: event_articles_from_file

Acquires the news articles of multiple events, where the event ids are provided in a file.
Supports the [common flags](#common-flags) (except `--query_file`; note that
`--save_to_file` is a **folder** here) plus:

| Name                | Optional | Description                                                                                                                                                                                                      |
| ------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `--event_ids_file`  | False    | The path to the file containing the event ids                                                                                                                                                                   |
| `--event_file_type` | True     | The type of the file. Options: 'plain' (each line of the file contains a single event id), 'events' (each line contains an event object with its event id stored in the `'uri'` attribute) (Default: `'events'`) |

```bash
# first collect some events of a certain topic
uv run collect events \
    --max_repeat_request=5 \
    --keywords="Barrack Obama,Donald Trump" \
    --languages=eng,slv \
    --date_start=2019-01-01 \
    --max_items=10 \
    --save_to_file=./data/barrack_trump_events.jsonl

# afterwards leverage the collected events for acquiring the event articles
uv run collect event_articles_from_file \
    --max_repeat_request=5 \
    --event_ids_file=./data/barrack_trump_events.jsonl \
    --max_items=10 \
    --save_to_file=./data/barrack_trump_events
```

### Action: suggest

Queries the Event Registry suggest API and prints the ranked candidate URIs, so you can pick
the exact concept/category/source instead of relying on automatic resolution.

| Name       | Optional | Description                                                                                            |
| ---------- | -------- | -------------------------------------------------------------------------------------------------------- |
| `type`     | False    | The suggestion type (positional). Options: `concepts`, `categories`, `sources`                         |
| `prefix`   | False    | The text the suggestions should match (positional)                                                     |
| `--types`  | True     | The comma separated concept types (concepts only). Options: person, loc, org, wiki, entities, concepts |
| `--lang`   | True     | The language of the prefix (concepts only) (Default: `'eng'`)                                          |
| `--count`  | True     | The number of suggestions to return (Default: 20)                                                      |
| `--format` | True     | The output format. Options: `table`, `json` (Default: `'table'`)                                       |

```bash
uv run collect suggest concepts "luka doncic" --types=person
uv run collect suggest categories "basketball"
uv run collect suggest sources "delo"
```

When a query uses plain names instead of URIs, the collector resolves them automatically and
logs a warning showing the chosen URI. Use the URI directly (in the flags or in a query file)
to avoid the automatic selection.

## Complex Queries

For queries that need nested AND/OR/NOT logic, pass a JSON file in the Event Registry
advanced query language to the `articles` or `events` action via `--query_file`:

```bash
uv run collect events \
    --max_repeat_request=5 \
    --query_file=./examples/eu_presidency.json \
    --save_to_file=./data/eu_presidency_events.jsonl
```

The file contains a `$query` object built from `$and`/`$or`/`$not` operators (see
[examples/eu_presidency.json](./examples/eu_presidency.json) for an example). A bare query
object without the `$query` wrapper is also accepted. When `--save_to_file` points to an
existing file, the date of the last stored item is injected into the query automatically,
so repeated runs only collect new items.

## More Examples

Additional ready-to-use CLI walkthroughs are available in [QUERIES.md](./QUERIES.md), and a
collection of complex query files for `--query_file` is stored in the
[examples](./examples) folder (see [examples/README.md](./examples/README.md) for what each
one demonstrates).

## Periodic Collection

The [scripts/backfill.py](./scripts/backfill.py) script collects Slovenian news one weekly
window at a time, walking backward through history. Windows are **completed Mon–Sun ISO
weeks**, anchored at the most recent Sunday strictly before today, so window keys are
canonical regardless of which day the script runs on; a `--end-date` falling mid-week is
snapped down to the Sunday of the enclosing completed week (with a warning). The sources are
read from [scripts/sources.txt](./scripts/sources.txt) (one source URI per line; blank lines
and `#` comments are ignored), and each window is saved to
`/vault/data/SLM4IE/raw/slovenian_news/{start}_{end}.jsonl`.

Coverage is tracked in a manifest (`coverage.json`, alongside the data) that records which
sources were collected for which week. This means that after you add a new outlet to
`sources.txt`, re-running only collects the new `(source × week)` combinations instead of
re-downloading everything; new results for an already-covered week land in a fresh
`{start}_{end}.rN.jsonl` file so the existing data is never overwritten or truncated. An
exclusive lock file (`coverage.json.lock`) prevents concurrent runs from racing on the
manifest, partial output files left by a failed collector run are deleted so retries never
duplicate articles, and a missing `API_KEY` (environment or `.env`) is reported up front
before any window is attempted.

```bash
# backfill the last 12 weeks (default)
uv run scripts/backfill.py

# backfill until a specific date (or use --weeks N)
uv run scripts/backfill.py --start-date 2026-01-01

# anchor at a specific week; mid-week dates snap down to the enclosing completed week
uv run scripts/backfill.py --weeks 4 --end-date 2026-05-31

# preview the planned work without collecting anything
uv run scripts/backfill.py --weeks 4 --dry-run
```

The [scripts/cronjob.sh](./scripts/cronjob.sh) script is a thin wrapper around
`backfill.py --weeks 2`: it collects the two most recently completed weeks and updates the
same manifest, so periodic runs and historic backfills share one source of truth.
Already-covered windows are skipped at zero cost, so the extra week self-heals a missed cron
run. It uses uv when available and falls back to `python3` otherwise, so it can be registered
as a cron job directly:

```bash
# run every Monday at 02:30, appending output to a log file
30 2 * * 1 /path/to/event-registry-data-collector/scripts/cronjob.sh >> /path/to/cronjob.log 2>&1
```

## Development

Install the development dependencies and run the checks with uv:

```bash
# install the project with the dev extras
uv sync --extra dev

# run the tests
uv run pytest

# run the linter and type checker
uv run ruff check .
uv run mypy collector
```
