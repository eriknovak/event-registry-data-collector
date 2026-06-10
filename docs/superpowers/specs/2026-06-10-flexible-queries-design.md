# Flexible Queries + Manual Concept Selection — Design

Date: 2026-06-10
Status: Approved

## Problem

The collector is rigid in two ways:

1. **Query structure is hardcoded.** `client.py` always combines keywords/concepts/categories
   with `QueryItems.AND` and sources/languages with `OR`. No NOT, no mixing of operators,
   no nesting. Complex queries like `(A AND B) OR (C NOT D)` are impossible.
2. **Concepts are auto-resolved.** `getConceptUri(name)` silently takes Event Registry's top
   suggestion. The user cannot see the candidates or pick the correct concept URI, which can
   lead to collecting data for the wrong concept.

## SDK Facts (eventregistry 9.1, verified in installed source)

- `QueryArticlesIter.initWithComplexQuery()` and `QueryEventsIter.initWithComplexQuery()`
  accept a JSON string or plain Python dict using ER's advanced query language
  (`$query`, `$and`, `$or`, `$not`, `$filter`). No SDK object building required.
- `suggestConcepts(prefix, sources=...)` returns a ranked candidate list (URI, label, type,
  score), filterable by type (`person`, `loc`, `org`, `wiki`, `entities`, `concepts`).
  Equivalent methods exist for categories (`suggestCategories`) and news sources
  (`suggestNewsSources`).
- **Limitation:** `QueryEventArticlesIter` has no `initWithComplexQuery` — only flat
  per-field AND/OR filters. Complex queries therefore apply to the `articles` and `events`
  actions only.

## Design

### 1. New `suggest` subcommand

```bash
collect suggest concepts "luka doncic" [--types=person,wiki] [--count=20] [--lang=eng] [--format=table|json]
collect suggest categories "basketball" [--count=20] [--format=table|json]
collect suggest sources "delo" [--count=20] [--format=table|json]
```

- Prints a ranked table: index, type, label, URI.
- `--format=json` dumps the raw API response for scripting.
- `--types` (concepts only) maps to the `sources` parameter of `suggestConcepts`.
- Read-only; requires only the API key.

### 2. `--query_file` on `articles` and `events`

- Path to a raw ER advanced-query JSON file, passed to `initWithComplexQuery()`.
- Accepts either the full form `{"$query": {...}, "$filter": {...}}` or a bare query object
  (the collector wraps it in `$query`).
- **Mutually exclusive** with the query flags (`--keywords`, `--concepts`, `--categories`,
  `--sources`, `--languages`, `--date_start`, `--date_end`). Providing both is an error.
- Execution flags (`--sort_by`, `--sort_by_asc`, `--max_items`, `--save_to_file`,
  `--save_format`, `--verbose`, `--max_repeat_request`) work in both modes.

Example query file:

```json
{
  "$query": {
    "$and": [
      {"conceptUri": "http://en.wikipedia.org/wiki/Slovenia"},
      {"$or": [
        {"keyword": "EU presidency"},
        {"conceptUri": "http://en.wikipedia.org/wiki/Council_of_the_European_Union"}
      ]},
      {"$not": {"categoryUri": "dmoz/Sports"}},
      {"lang": "eng"}
    ]
  }
}
```

### 3. Incremental collection with query files

Current behavior is preserved: when `--save_to_file` points to an existing file, the date of
the last stored item replaces the start date. With a query file, the date is injected by
wrapping the original query:

```json
{"$query": {"$and": [<original query>, {"dateStart": "<last_date>"}]}}
```

This is always valid regardless of query nesting. The injection is logged.

### 4. Simple flags: URI pass-through + resolution warning

| Flag           | Pass-through condition              | Otherwise                              |
| -------------- | ----------------------------------- | -------------------------------------- |
| `--concepts`   | starts with `http://` or `https://` | auto-resolve via `getConceptUri` + warn |
| `--categories` | starts with `dmoz/` or `news/`      | auto-resolve via `getCategoryUri` + warn |
| `--sources`    | contains a dot (domain, `delo.si`)  | auto-resolve via `getSourceUri` + warn  |

Warning format:
`WARNING: resolved 'slovenia' -> http://en.wikipedia.org/wiki/Slovenia (use 'collect suggest concepts' to pick explicitly)`

Existing cronjob.sh and QUERIES.md commands keep working unchanged.

### 5. Code changes

- **`collector/client.py`**
  - Add `suggest_concepts`, `suggest_categories`, `suggest_sources` methods returning the
    raw candidate lists.
  - `get_articles` / `get_events` gain `query: Optional[Dict[str, Any]]`. When set, the
    query routes to `initWithComplexQuery`; the flat parameters must be unset. Date-resume
    and save-to-file logic is shared between both paths.
  - Resolution helpers (`get_concepts`, `get_categories`, `get_sources`) gain URI detection
    and the resolution warning.
- **`collector/cli.py`**
  - `suggest` subparser with `concepts`/`categories`/`sources` sub-actions.
  - `--query_file` flag on `articles` and `events`; mutual-exclusion validation with a clear
    error message.
  - Table rendering for suggest results.
- **`tests/`** (new) — pytest suite with a mocked ER client, no live API calls:
  - bare query wrapping into `$query`
  - `dateStart` injection on resume
  - URI detection per flag type
  - mutual exclusion of `--query_file` and query flags
  - suggest output formatting (table and json)
- **Docs** — README section for `suggest` and `--query_file`; QUERIES.md gains a
  complex-query example showing the full workflow (suggest → pick URI → query file).

## Error handling

- Query file missing or invalid JSON → clear error naming the file and the parse problem.
- `--query_file` combined with any query flag → error listing the conflicting flags.
- Empty suggest results → message suggesting a different prefix or `--types`.

## Out of scope

- `event_articles` keeps its current flat filters (SDK limitation).
- No interactive query builder.
- No YAML query format (raw ER JSON only).
