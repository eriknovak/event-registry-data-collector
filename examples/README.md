# Query File Examples

Ready-to-use complex query files for the `--query_file` flag of the `articles` and
`events` actions. Each file is written in the Event Registry
[advanced query language](https://github.com/EventRegistry/event-registry-python/wiki/Searching-for-articles#advanced-query-language):
a `$query` condition tree built from `$and`/`$or`/`$not`, plus an optional `$filter` block.

Run any of them with, for example:

```bash
uv run collect events \
    --max_repeat_request=5 \
    --query_file=./examples/concept_boolean.json \
    --save_to_file=./data/ai_events.jsonl
```

The concept/category/source URIs below are illustrative. Use the `suggest` action to look
up the exact URIs for your own topics (e.g. `uv run collect suggest concepts "olympics"`).

| File                                               | Demonstrates                                                                                   |
| -------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| [keyword_basic.json](./keyword_basic.json)         | Keyword search restricted to the title with phrase matching (`keywordLoc`, `keywordSearchMode`) |
| [concept_boolean.json](./concept_boolean.json)     | Multiple concepts combined with `$or` and a `$not` keyword exclusion                            |
| [category_filter.json](./category_filter.json)     | Combining a concept with a `categoryUri` include and a `categoryUri` exclude                    |
| [source_lang_filter.json](./source_lang_filter.json) | Restricting by source location (`sourceLocationUri`) and several languages                      |
| [multiple_sources.json](./multiple_sources.json)   | Retrieving from several named news sources at once (`$or` over `sourceUri`)                     |
| [slovenian_sources.json](./slovenian_sources.json) | All non-duplicate Slovenian articles from a list of sources (`$or` over `sourceUri` + `lang` + `isDuplicate`) |
| [date_filter.json](./date_filter.json)             | A date range in the query plus a `$filter` block (`dataType`, `isDuplicate`, `minSentiment`)    |
| [eu_presidency.json](./eu_presidency.json)         | A nested `$and`/`$or`/`$not` query: Slovenian EU presidency, excluding sports                   |
| [advanced_kitchen_sink.json](./advanced_kitchen_sink.json) | A maximal example combining most available conditions and every `$filter` option (see below)   |

## All available options (`advanced_kitchen_sink.json`)

`advanced_kitchen_sink.json` is a deliberately over-built query that exercises nearly every
key the Event Registry advanced query language supports. It is meant as a reference, not a
realistic search — replace the illustrative URIs with your own (use the `suggest` action).

**Condition keys (inside `$query`):**

| Key                                       | Meaning                                                                                  |
| ----------------------------------------- | ---------------------------------------------------------------------------------------- |
| `conceptUri`                              | A concept. Per-key `{"$and": [...]}` requires **all** listed concepts; `{"$or": [...]}` any |
| `keyword`                                 | A keyword/phrase. Per-key `$and`/`$or` is supported                                       |
| `keywordLoc`                              | Where to match keywords: `body`, `title`, or `title,body`                                 |
| `keywordSearchMode`                       | Keyword matching: `simple`, `exact`, or `phrase`                                          |
| `categoryUri`                             | A DMOZ category to include (or exclude under `$not`)                                      |
| `lang`                                    | Article language(s), e.g. `eng`, `deu`, `slv`                                             |
| `sourceUri`                               | A named news source domain, e.g. `bbc.com`                                                |
| `sourceLocationUri`                       | Geographic location of the source                                                        |
| `sourceGroupUri`                          | A source group (predefined or user-defined)                                              |
| `authorUri`                               | A specific article author                                                                |
| `locationUri`                             | The event/dateline location of the article                                               |
| `dateStart` / `dateEnd`                   | Publication date range (`YYYY-MM-DD`)                                                     |
| `dateMention`                             | A list of dates explicitly **mentioned** in the article text                             |
| `minArticlesInEvent` / `maxArticlesInEvent` | Keep only articles whose event has a number of articles in this range                  |
| `$not`                                    | Exclude anything matching the nested condition                                           |

**`$filter` keys (sibling of `$query`):**

| Key                                                 | Allowed values                                                            |
| --------------------------------------------------- | ------------------------------------------------------------------------- |
| `dataType`                                          | `news`, `blog`, `pr`, or an array of these                                |
| `isDuplicate`                                       | `keepAll`, `skipDuplicates`, `keepOnlyDuplicates`                         |
| `hasDuplicate`                                      | `keepAll`, `skipHasDuplicates`, `keepOnlyHasDuplicates`                   |
| `hasEvent`                                          | `keepAll`, `skipArticlesWithoutEvent`, `keepOnlyArticlesWithoutEvent`     |
| `startSourceRankPercentile` / `endSourceRankPercentile` | Multiples of 10 (start `0`–`90`, end `10`–`100`) — narrows by source rank |
| `minSentiment` / `maxSentiment`                     | Float in `[-1, 1]` — keep articles within a sentiment band                |

## Notes

- A bare condition object (without the `$query` wrapper) is also accepted; the collector
  wraps it automatically.
- For a few sources without nested logic, the `--sources` flag is simpler than a query
  file — it accepts a comma separated list and ORs them together. For example:
  `uv run collect articles --sources="bbc.com,theguardian.com,reuters.com" --keywords="artificial intelligence"`.
  Use a query file (like `multiple_sources.json`) when the sources need to be combined with
  other nested `$and`/`$or`/`$not` conditions.
- `--query_file` cannot be combined with the `--keywords`/`--concepts`/`--categories`/
  `--sources`/`--languages`/`--date_start`/`--date_end` flags.
- When `--save_to_file` points to an existing file, the date of the last stored item is
  injected into the query automatically, so repeated runs only collect new items. To pin a
  fixed window instead, set `dateStart`/`dateEnd` in the query (see `date_filter.json`).
