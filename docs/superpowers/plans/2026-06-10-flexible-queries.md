# Flexible Queries + Manual Concept Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add complex query support (`--query_file` with ER's `$and`/`$or`/`$not` JSON) and a `suggest` subcommand so the user picks concept/category/source URIs manually instead of relying on silent auto-resolution.

**Architecture:** A new pure-function module `collector/query.py` handles loading/wrapping/date-injecting complex query JSON. `collector/client.py` gains suggest methods, URI pass-through in its resolution helpers, and a `query` parameter on `get_articles`/`get_events` that routes to `initWithComplexQuery`. `collector/cli.py` gains the `suggest` subparser, `--query_file`, and mutual-exclusion validation. All tests mock the ER SDK — no live API calls.

**Tech Stack:** Python 3.9+, `eventregistry` 9.1, pytest (in `dev` extra), uv. Run tests with `uv run --extra dev pytest tests/ -v`. Follow Google style, type hints from `typing` (List/Dict/Optional), 120-char lines, Google docstrings.

**Spec:** `docs/superpowers/specs/2026-06-10-flexible-queries-design.md`

---

### Task 1: Query helper module (`collector/query.py`)

**Files:**
- Create: `tests/test_query.py`
- Create: `collector/query.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_query.py`:

```python
"""Tests for the complex query helper functions."""

import json

import pytest

from collector.query import inject_date_start, load_query_file, wrap_query


def test_wrap_query_bare_object():
    """A bare query object is wrapped into the $query form."""
    assert wrap_query({"conceptUri": "http://en.wikipedia.org/wiki/Slovenia"}) == {
        "$query": {"conceptUri": "http://en.wikipedia.org/wiki/Slovenia"}
    }


def test_wrap_query_full_form_unchanged():
    """A query already containing $query is returned unchanged."""
    query = {"$query": {"conceptUri": "x"}, "$filter": {"dataType": "news"}}
    assert wrap_query(query) == query


def test_inject_date_start_wraps_in_and():
    """The dateStart condition is AND-ed with the original query."""
    query = {"$query": {"$or": [{"keyword": "a"}, {"keyword": "b"}]}}
    result = inject_date_start(query, "2026-01-01")
    assert result == {
        "$query": {"$and": [{"$or": [{"keyword": "a"}, {"keyword": "b"}]}, {"dateStart": "2026-01-01"}]}
    }


def test_inject_date_start_preserves_filter():
    """Top-level keys next to $query (e.g. $filter) are preserved."""
    query = {"$query": {"keyword": "a"}, "$filter": {"dataType": "news"}}
    result = inject_date_start(query, "2026-01-01")
    assert result["$filter"] == {"dataType": "news"}
    assert result["$query"] == {"$and": [{"keyword": "a"}, {"dateStart": "2026-01-01"}]}


def test_inject_date_start_does_not_mutate_input():
    """The original query dict is not modified."""
    query = {"$query": {"keyword": "a"}}
    inject_date_start(query, "2026-01-01")
    assert query == {"$query": {"keyword": "a"}}


def test_load_query_file_valid(tmp_path):
    """A valid query file is loaded and wrapped."""
    path = tmp_path / "query.json"
    path.write_text(json.dumps({"conceptUri": "x"}))
    assert load_query_file(str(path)) == {"$query": {"conceptUri": "x"}}


def test_load_query_file_missing(tmp_path):
    """A missing file raises a ValueError naming the path."""
    path = str(tmp_path / "missing.json")
    with pytest.raises(ValueError, match="not found"):
        load_query_file(path)


def test_load_query_file_invalid_json(tmp_path):
    """Invalid JSON raises a ValueError naming the file."""
    path = tmp_path / "broken.json"
    path.write_text("{not json")
    with pytest.raises(ValueError, match="not valid JSON"):
        load_query_file(str(path))


def test_load_query_file_not_an_object(tmp_path):
    """A JSON array (not object) raises a ValueError."""
    path = tmp_path / "list.json"
    path.write_text("[1, 2]")
    with pytest.raises(ValueError, match="JSON object"):
        load_query_file(str(path))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --extra dev pytest tests/test_query.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'collector.query'`

- [ ] **Step 3: Write the implementation**

Create `collector/query.py`:

```python
"""Helpers for loading and manipulating Event Registry complex queries.

The complex query format is Event Registry's advanced query language:
a JSON object with a ``$query`` condition tree built from ``$and``,
``$or`` and ``$not`` operators, and an optional ``$filter`` object. See
https://github.com/EventRegistry/event-registry-python/wiki/Searching-for-articles#advanced-query-language.
"""

import json
import os
from typing import Any, Dict


def wrap_query(query: Dict[str, Any]) -> Dict[str, Any]:
    """Wraps a bare query object into the full ``$query`` form.

    Args:
        query (Dict[str, Any]): Either a full complex query (containing the
            ``$query`` key) or a bare condition object.

    Returns:
        Dict[str, Any]: The query in the full ``{"$query": ...}`` form.
    """
    if "$query" in query:
        return query
    return {"$query": query}


def inject_date_start(query: Dict[str, Any], date_start: str) -> Dict[str, Any]:
    """Returns a copy of the query constrained to dates >= `date_start`.

    The original ``$query`` condition is AND-ed with a ``dateStart``
    condition, which is valid regardless of the query nesting. Other
    top-level keys (e.g. ``$filter``) are preserved.

    Args:
        query (Dict[str, Any]): The complex query in the full ``$query`` form.
        date_start (str): The start date in the YYYY-MM-DD format.

    Returns:
        Dict[str, Any]: A new query dict with the injected date condition.
    """
    return {
        **query,
        "$query": {"$and": [query["$query"], {"dateStart": date_start}]},
    }


def load_query_file(path: str) -> Dict[str, Any]:
    """Loads and normalizes a complex query from a JSON file.

    Args:
        path (str): The path to the JSON query file.

    Returns:
        Dict[str, Any]: The query in the full ``{"$query": ...}`` form.

    Raises:
        ValueError: If the file does not exist, is not valid JSON, or does
            not contain a JSON object.
    """
    if not os.path.isfile(path):
        raise ValueError("Query file not found: {}".format(path))
    with open(path) as in_file:
        try:
            query = json.load(in_file)
        except json.JSONDecodeError as error:
            raise ValueError("Query file is not valid JSON: {} ({})".format(path, error))
    if not isinstance(query, dict):
        raise ValueError("Query file must contain a JSON object: {}".format(path))
    return wrap_query(query)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --extra dev pytest tests/test_query.py -v`
Expected: 9 PASSED

- [ ] **Step 5: Commit**

```bash
git add tests/test_query.py collector/query.py
git commit -m "feat: add complex query helper module"
```

---

### Task 2: URI pass-through in resolution helpers

**Files:**
- Create: `tests/test_client.py`
- Modify: `collector/client.py` (the `get_concepts`, `get_categories`, `get_sources` methods, ~lines 115-152; add module-level URI predicates after `print_query_params`)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_client.py`:

```python
"""Tests for the EventRegistryCollector client (with a mocked ER SDK)."""

import json
import logging
from unittest import mock

import pytest

from collector.client import (
    URI,
    EventRegistryCollector,
    is_category_uri,
    is_concept_uri,
    is_source_uri,
)


@pytest.fixture
def collector():
    """An EventRegistryCollector with a mocked EventRegistry instance."""
    with mock.patch("collector.client.ER.EventRegistry"):
        c = EventRegistryCollector(api_key="test-key")
    return c


def test_is_concept_uri():
    assert is_concept_uri("http://en.wikipedia.org/wiki/Slovenia")
    assert is_concept_uri("https://en.wikipedia.org/wiki/Slovenia")
    assert not is_concept_uri("slovenia")


def test_is_category_uri():
    assert is_category_uri("dmoz/Sports")
    assert is_category_uri("news/Politics")
    assert not is_category_uri("sports")


def test_is_source_uri():
    assert is_source_uri("delo.si")
    assert not is_source_uri("BBC")


def test_get_concepts_uri_passthrough(collector):
    """Explicit URIs are used as-is without calling the resolution API."""
    uri = "http://en.wikipedia.org/wiki/Slovenia"
    assert collector.get_concepts([uri]) == [URI(uri, uri)]
    collector._er.getConceptUri.assert_not_called()


def test_get_concepts_resolves_and_warns(collector, caplog):
    """Plain names are auto-resolved with a warning showing the resolution."""
    collector._er.getConceptUri.return_value = "http://en.wikipedia.org/wiki/Slovenia"
    with caplog.at_level(logging.WARNING):
        result = collector.get_concepts(["slovenia"])
    assert result == [URI("slovenia", "http://en.wikipedia.org/wiki/Slovenia")]
    assert "resolved" in caplog.text
    assert "suggest concepts" in caplog.text


def test_get_categories_uri_passthrough(collector):
    assert collector.get_categories(["dmoz/Sports"]) == [URI("dmoz/Sports", "dmoz/Sports")]
    collector._er.getCategoryUri.assert_not_called()


def test_get_categories_resolves_and_warns(collector, caplog):
    collector._er.getCategoryUri.return_value = "dmoz/Sports"
    with caplog.at_level(logging.WARNING):
        result = collector.get_categories(["sports"])
    assert result == [URI("sports", "dmoz/Sports")]
    assert "suggest categories" in caplog.text


def test_get_sources_uri_passthrough(collector):
    assert collector.get_sources(["delo.si"]) == [URI("delo.si", "delo.si")]
    collector._er.getSourceUri.assert_not_called()


def test_get_sources_resolves_and_warns(collector, caplog):
    collector._er.getSourceUri.return_value = "bbc.co.uk"
    with caplog.at_level(logging.WARNING):
        result = collector.get_sources(["BBC"])
    assert result == [URI("BBC", "bbc.co.uk")]
    assert "suggest sources" in caplog.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --extra dev pytest tests/test_client.py -v`
Expected: FAIL with `ImportError: cannot import name 'is_category_uri'`

- [ ] **Step 3: Write the implementation**

In `collector/client.py`, add after the `print_query_params` function (module level):

```python
def is_concept_uri(value: str) -> bool:
    """Checks whether the value is already a concept URI.

    Args:
        value (str): The concept name or URI.

    Returns:
        bool: True if the value is a URI (starts with http:// or https://).
    """
    return value.startswith(("http://", "https://"))


def is_category_uri(value: str) -> bool:
    """Checks whether the value is already a category URI.

    Args:
        value (str): The category name or URI.

    Returns:
        bool: True if the value is a URI (starts with dmoz/ or news/).
    """
    return value.startswith(("dmoz/", "news/"))


def is_source_uri(value: str) -> bool:
    """Checks whether the value is already a source URI.

    Args:
        value (str): The source name or URI.

    Returns:
        bool: True if the value looks like a domain (contains a dot).
    """
    return "." in value
```

Replace the bodies of `get_concepts`, `get_categories` and `get_sources` (keep the existing docstring Args/Returns, extend the summary line to mention pass-through):

```python
    def get_concepts(self, concepts: List[str]) -> List[URI]:
        """Get the list of event registry concepts.

        Values that are already URIs are passed through unchanged; plain
        names are auto-resolved with a warning.

        Args:
            concepts (List[str]): The list of concept names or URIs.

        Returns:
            List[URI]: A list of URI objects with the given concept URIs.
        """
        uris = []
        for k in concepts:
            if is_concept_uri(k):
                uris.append(URI(k, k))
                continue
            uri = self._er.getConceptUri(k)
            logger.warning("resolved %r -> %s (use 'collect suggest concepts' to pick explicitly)", k, uri)
            uris.append(URI(k, uri))
        return uris

    def get_categories(self, categories: List[str]) -> List[URI]:
        """Get the list of event registry categories.

        Values that are already URIs are passed through unchanged; plain
        names are auto-resolved with a warning.

        Args:
            categories (List[str]): The list of category names or URIs.

        Returns:
            List[URI]: A list of URI objects with the given category URIs.
        """
        uris = []
        for k in categories:
            if is_category_uri(k):
                uris.append(URI(k, k))
                continue
            uri = self._er.getCategoryUri(k)
            logger.warning("resolved %r -> %s (use 'collect suggest categories' to pick explicitly)", k, uri)
            uris.append(URI(k, uri))
        return uris

    def get_sources(self, sources: List[str]) -> List[URI]:
        """Get the list of source uris.

        Values that look like domains are passed through unchanged; plain
        names are auto-resolved with a warning.

        Args:
            sources (List[str]): The list of source names or URIs.

        Returns:
            List[URI]: A list of URI objects with the given source URIs.
        """
        uris = []
        for k in sources:
            if is_source_uri(k):
                uris.append(URI(k, k))
                continue
            uri = self._er.getSourceUri(k)
            logger.warning("resolved %r -> %s (use 'collect suggest sources' to pick explicitly)", k, uri)
            uris.append(URI(k, uri))
        return uris
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --extra dev pytest tests/test_client.py -v`
Expected: 9 PASSED

- [ ] **Step 5: Commit**

```bash
git add tests/test_client.py collector/client.py
git commit -m "feat: pass URIs through resolution helpers and warn on auto-resolve"
```

---

### Task 3: Suggest methods on the client

**Files:**
- Modify: `tests/test_client.py` (append tests)
- Modify: `collector/client.py` (add methods to `EventRegistryCollector`, after `get_sources`)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_client.py`:

```python
def test_suggest_concepts_default_types(collector):
    """Without types the SDK is queried with the broad 'concepts' source."""
    collector._er.suggestConcepts.return_value = [{"uri": "u", "type": "wiki"}]
    result = collector.suggest_concepts("luka")
    assert result == [{"uri": "u", "type": "wiki"}]
    collector._er.suggestConcepts.assert_called_once_with("luka", sources=["concepts"], lang="eng", count=20)


def test_suggest_concepts_with_types(collector):
    collector._er.suggestConcepts.return_value = []
    collector.suggest_concepts("luka", types=["person", "org"], lang="slv", count=5)
    collector._er.suggestConcepts.assert_called_once_with("luka", sources=["person", "org"], lang="slv", count=5)


def test_suggest_categories(collector):
    collector._er.suggestCategories.return_value = [{"uri": "dmoz/Sports"}]
    assert collector.suggest_categories("sport", count=5) == [{"uri": "dmoz/Sports"}]
    collector._er.suggestCategories.assert_called_once_with("sport", count=5)


def test_suggest_sources(collector):
    collector._er.suggestNewsSources.return_value = [{"uri": "delo.si", "title": "Delo"}]
    assert collector.suggest_sources("delo") == [{"uri": "delo.si", "title": "Delo"}]
    collector._er.suggestNewsSources.assert_called_once_with("delo", count=20)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --extra dev pytest tests/test_client.py -v -k suggest`
Expected: 4 FAILED with `AttributeError: 'EventRegistryCollector' object has no attribute 'suggest_concepts'`

- [ ] **Step 3: Write the implementation**

Add to `EventRegistryCollector` in `collector/client.py`, after `get_sources`:

```python
    def suggest_concepts(
        self,
        prefix: str,
        types: Optional[List[str]] = None,
        lang: str = "eng",
        count: int = 20,
    ) -> List[Dict[str, Any]]:
        """Gets the ranked concept suggestions for the given prefix.

        Args:
            prefix (str): The text the concept should match.
            types (Optional[List[str]]): The concept types to return. Valid
                values: person, loc, org, wiki, entities, concepts. If None,
                all concept types are returned (Default: None).
            lang (str): The language of the prefix (Default: 'eng').
            count (int): The number of suggestions to return (Default: 20).

        Returns:
            List[Dict[str, Any]]: The ranked concept candidates with their
                uri, type and label.
        """
        return self._er.suggestConcepts(prefix, sources=types or ["concepts"], lang=lang, count=count)

    def suggest_categories(self, prefix: str, count: int = 20) -> List[Dict[str, Any]]:
        """Gets the ranked category suggestions for the given prefix.

        Args:
            prefix (str): The text the category name should match.
            count (int): The number of suggestions to return (Default: 20).

        Returns:
            List[Dict[str, Any]]: The ranked category candidates with their uri.
        """
        return self._er.suggestCategories(prefix, count=count)

    def suggest_sources(self, prefix: str, count: int = 20) -> List[Dict[str, Any]]:
        """Gets the ranked news source suggestions for the given prefix.

        Args:
            prefix (str): The text the source name or uri should match.
            count (int): The number of suggestions to return (Default: 20).

        Returns:
            List[Dict[str, Any]]: The ranked source candidates with their
                uri and title.
        """
        return self._er.suggestNewsSources(prefix, count=count)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --extra dev pytest tests/test_client.py -v`
Expected: 13 PASSED

- [ ] **Step 5: Commit**

```bash
git add tests/test_client.py collector/client.py
git commit -m "feat: add suggest methods for concepts, categories and sources"
```

---

### Task 4: Complex query support in `get_articles` / `get_events`

**Files:**
- Modify: `tests/test_client.py` (append tests)
- Modify: `collector/client.py` (`get_articles` ~lines 154-257, `get_events` ~lines 259-363; add `get_last_date` module-level helper)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_client.py`:

```python
def test_get_last_date_missing_file(tmp_path):
    from collector.client import get_last_date

    assert get_last_date(str(tmp_path / "missing.jsonl"), "date") is None


def test_get_last_date_reads_last_line(tmp_path):
    from collector.client import get_last_date

    path = tmp_path / "articles.jsonl"
    path.write_text(json.dumps({"date": "2026-01-01"}) + "\n" + json.dumps({"date": "2026-01-02"}) + "\n")
    assert get_last_date(str(path), "date") == "2026-01-02"


def test_get_articles_complex_query(collector):
    """A complex query is routed to initWithComplexQuery."""
    query = {"$query": {"conceptUri": "http://en.wikipedia.org/wiki/Slovenia"}}
    with mock.patch("collector.client.ER.QueryArticlesIter") as mock_iter:
        mock_iter.initWithComplexQuery.return_value.execQuery.return_value = []
        result = collector.get_articles(query=query)
    mock_iter.initWithComplexQuery.assert_called_once_with(query)
    assert result == []


def test_get_articles_complex_query_rejects_flat_params(collector):
    """Combining a complex query with flat parameters is an error."""
    with pytest.raises(ValueError, match="cannot be combined"):
        collector.get_articles(query={"$query": {}}, concepts=["slovenia"])


def test_get_articles_complex_query_resumes_date(collector, tmp_path):
    """An existing save file injects the last date into the complex query."""
    save_file = tmp_path / "articles.jsonl"
    save_file.write_text(json.dumps({"date": "2026-01-02"}) + "\n")
    with mock.patch("collector.client.ER.QueryArticlesIter") as mock_iter:
        mock_iter.initWithComplexQuery.return_value.execQuery.return_value = []
        collector.get_articles(query={"$query": {"conceptUri": "x"}}, save_to_file=str(save_file))
    expected = {"$query": {"$and": [{"conceptUri": "x"}, {"dateStart": "2026-01-02"}]}}
    mock_iter.initWithComplexQuery.assert_called_once_with(expected)


def test_get_events_complex_query(collector):
    query = {"$query": {"conceptUri": "x"}}
    with mock.patch("collector.client.ER.QueryEventsIter") as mock_iter:
        mock_iter.initWithComplexQuery.return_value.execQuery.return_value = []
        result = collector.get_events(query=query)
    mock_iter.initWithComplexQuery.assert_called_once_with(query)
    assert result == []


def test_get_events_complex_query_resumes_date(collector, tmp_path):
    """Events resume from the eventDate of the last stored event."""
    save_file = tmp_path / "events.jsonl"
    save_file.write_text(json.dumps({"eventDate": "2026-01-03"}) + "\n")
    with mock.patch("collector.client.ER.QueryEventsIter") as mock_iter:
        mock_iter.initWithComplexQuery.return_value.execQuery.return_value = []
        collector.get_events(query={"$query": {"conceptUri": "x"}}, save_to_file=str(save_file))
    expected = {"$query": {"$and": [{"conceptUri": "x"}, {"dateStart": "2026-01-03"}]}}
    mock_iter.initWithComplexQuery.assert_called_once_with(expected)


def test_get_events_complex_query_rejects_flat_params(collector):
    with pytest.raises(ValueError, match="cannot be combined"):
        collector.get_events(query={"$query": {}}, languages=["eng"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --extra dev pytest tests/test_client.py -v -k "complex or last_date"`
Expected: FAILED (no `get_last_date`, no `query` parameter)

- [ ] **Step 3: Write the implementation**

In `collector/client.py`:

1. Add the import at the top (with the other local imports):

```python
from collector.query import inject_date_start
```

2. Add a module-level helper after the URI predicates:

```python
def get_last_date(file_path: Optional[str], date_field: str) -> Optional[str]:
    """Reads the date of the last stored item in a JSONL file.

    Args:
        file_path (Optional[str]): The path of the JSONL file.
        date_field (str): The attribute holding the item date (e.g. 'date'
            for articles, 'eventDate' for events).

    Returns:
        Optional[str]: The date of the last item, or None if the file does
            not exist or is empty.
    """
    if not (file_path and os.path.isfile(file_path)):
        return None
    with open(file_path) as in_file:
        lines = in_file.readlines()
    if len(lines) == 0:
        return None
    return json.loads(lines[-1]).get(date_field)
```

3. In `get_articles`, add the parameter `query: Optional[Dict[str, Any]] = None` after `verbose`, document it in the docstring:

```python
            query (Optional[Dict[str, Any]]): A complex query in Event
                Registry's advanced query language (the full
                {"$query": ...} form). Cannot be combined with the flat
                query parameters (keywords, concepts, categories, sources,
                languages, date_start, date_end) (Default: None).
```

Replace the body between the start of the method and the `q = ER.QueryArticlesIter(...)` call (the existing flat-path code stays in the `else` branch; the existing read-last-date block is replaced by `get_last_date`):

```python
        if query is not None:
            flat_params = [keywords, concepts, categories, sources, languages, date_start, date_end]
            if any(p is not None for p in flat_params):
                raise ValueError("get_articles: 'query' cannot be combined with the flat query parameters")

            last_date = get_last_date(save_to_file, "date")
            if last_date:
                query = inject_date_start(query, last_date)
                logger.info("Resuming collection from %s (last date in %s)", last_date, save_to_file)

            q = ER.QueryArticlesIter.initWithComplexQuery(query)
        else:
            # setup the event registry parameters
            er_keywords = ER.QueryItems.AND(keywords) if keywords else None
            er_concepts = ER.QueryItems.AND([c.uri for c in self.get_concepts(concepts)]) if concepts else None
            er_categories = ER.QueryItems.AND([c.uri for c in self.get_categories(categories)]) if categories else None
            er_sources = ER.QueryItems.OR([c.uri for c in self.get_sources(sources)]) if sources else None
            er_lang = ER.QueryItems.OR(languages) if languages else None

            # when saving to file check the last date and use it as start date
            last_date = get_last_date(save_to_file, "date")
            if last_date:
                date_start = last_date

            if verbose:
                print_query_params(
                    {
                        "keywords": er_keywords,
                        "concepts": er_concepts,
                        "categories": er_categories,
                        "sources": er_sources,
                        "date_start": date_start,
                        "date_end": date_end,
                        "languages": languages,
                    }
                )

            # creates the query articles object
            q = ER.QueryArticlesIter(
                keywords=er_keywords,
                conceptUri=er_concepts,
                categoryUri=er_categories,
                sourceUri=er_sources,
                dateStart=date_start,
                dateEnd=date_end,
                lang=er_lang,
            )
```

The trailing `execQuery` / `save_result_in_file` / `return` code stays as is.

4. Apply the identical change to `get_events` with two differences: the error message says `get_events:`, and the date field is `"eventDate"` (`get_last_date(save_to_file, "eventDate")` in both branches), routing to `ER.QueryEventsIter.initWithComplexQuery(query)` and keeping the existing `ER.QueryEventsIter(...)` flat path in the `else` branch.

- [ ] **Step 4: Run all tests to verify they pass**

Run: `uv run --extra dev pytest tests/ -v`
Expected: all PASSED (21 in test_client.py + 9 in test_query.py)

- [ ] **Step 5: Commit**

```bash
git add tests/test_client.py collector/client.py
git commit -m "feat: support complex queries in get_articles and get_events"
```

---

### Task 5: CLI `suggest` subcommand

**Files:**
- Create: `tests/test_cli.py`
- Modify: `collector/cli.py` (add `import json`; add rendering helpers after the imports; add the suggest subparser in `create_argparser`; handle the suggest action in `main`)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cli.py`:

```python
"""Tests for the CLI helper functions."""

import argparse

from collector.cli import format_label, get_conflicting_flags, render_suggestions


def test_format_label_language_dict():
    assert format_label({"label": {"eng": "Luka Dončić"}}) == "Luka Dončić"


def test_format_label_plain_string():
    assert format_label({"label": "Sports"}) == "Sports"


def test_format_label_falls_back_to_title():
    assert format_label({"title": "Delo"}) == "Delo"


def test_format_label_missing():
    assert format_label({"uri": "x"}) == ""


def test_render_suggestions_table():
    items = [
        {"type": "person", "label": {"eng": "Luka Dončić"}, "uri": "http://en.wikipedia.org/wiki/Luka_Dončić"},
        {"title": "Delo", "uri": "delo.si"},
    ]
    out = render_suggestions(items)
    lines = out.splitlines()
    assert lines[0].split() == ["#", "TYPE", "LABEL", "URI"]
    assert "Luka Dončić" in lines[1]
    assert "delo.si" in lines[2]


def test_render_suggestions_empty():
    assert "No suggestions" in render_suggestions([])


def test_get_conflicting_flags():
    args = argparse.Namespace(keywords="a,b", concepts=None, categories=None, sources="delo.si", languages=None, date_start=None, date_end=None)
    assert get_conflicting_flags(args) == ["keywords", "sources"]


def test_get_conflicting_flags_none_set():
    args = argparse.Namespace()
    assert get_conflicting_flags(args) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --extra dev pytest tests/test_cli.py -v`
Expected: FAIL with `ImportError: cannot import name 'format_label'`

- [ ] **Step 3: Write the implementation**

In `collector/cli.py`:

1. Add `import json` to the stdlib imports and a new typing import (cli.py has none yet):

```python
import json
from typing import Any, Dict, List
```

2. Add module-level helpers after `logger = logging.getLogger(__name__)`:

```python
# the flags that define the query and conflict with --query_file
QUERY_FLAGS = ("keywords", "concepts", "categories", "sources", "languages", "date_start", "date_end")


def format_label(item: Dict[str, Any]) -> str:
    """Extracts a display label from a suggestion item.

    Args:
        item (Dict[str, Any]): A suggestion returned by the ER suggest API.

    Returns:
        str: The label in English (or the first available language), the
            source title, or an empty string.
    """
    label = item.get("label") or item.get("title") or ""
    if isinstance(label, dict):
        return label.get("eng") or next(iter(label.values()), "")
    return str(label)


def render_suggestions(items: List[Dict[str, Any]]) -> str:
    """Renders the suggestion items as an aligned text table.

    Args:
        items (List[Dict[str, Any]]): The suggestions returned by the ER
            suggest API.

    Returns:
        str: The table with index, type, label and URI columns, or a
            message if there are no suggestions.
    """
    if not items:
        return "No suggestions found. Try a different prefix or, for concepts, the --types option."
    header = ("#", "TYPE", "LABEL", "URI")
    rows = [(str(i), item.get("type", "-"), format_label(item), item.get("uri", "")) for i, item in enumerate(items, 1)]
    widths = [max(len(row[col]) for row in [header] + rows) for col in range(4)]
    lines = ["  ".join(value.ljust(width) for value, width in zip(row, widths)) for row in [header] + rows]
    return "\n".join(lines)


def get_conflicting_flags(args: argparse.Namespace) -> List[str]:
    """Returns the query flags that were set and conflict with --query_file.

    Args:
        args (argparse.Namespace): The parsed command line arguments.

    Returns:
        List[str]: The names of the conflicting flags.
    """
    return [flag for flag in QUERY_FLAGS if getattr(args, flag, None)]
```

3. In `create_argparser`, add the suggest subparser before the `return argparser` line:

```python
    ###################################
    # Suggest Query
    ###################################

    subparser = subparsers.add_parser("suggest", help="Suggests concept/category/source URIs for a search prefix")
    subparser.set_defaults(action="suggest")

    subparser.add_argument(
        "suggest_type",
        choices=["concepts", "categories", "sources"],
        help="The type of suggestions to retrieve",
    )
    subparser.add_argument("prefix", type=str, help="The text the suggestions should match")
    subparser.add_argument(
        "--types",
        type=str,
        default=None,
        help="The comma separated concept types (concepts only). Options: person, loc, org, wiki, entities, concepts",
    )
    subparser.add_argument("--lang", type=str, default="eng", help="The language of the prefix (concepts only)")
    subparser.add_argument("--count", type=int, default=20, help="The number of suggestions to return")
    subparser.add_argument(
        "--format",
        dest="output_format",
        choices=["table", "json"],
        default="table",
        help="The output format of the suggestions",
    )
```

4. Add a `run_suggest` function after `get_conflicting_flags`:

```python
def run_suggest(er: EventRegistryCollector, args: argparse.Namespace) -> None:
    """Executes the suggest action and prints the results.

    Args:
        er (EventRegistryCollector): The initialized collector.
        args (argparse.Namespace): The parsed command line arguments.
    """
    types = [t.strip() for t in args.types.split(",")] if args.types else None
    if args.suggest_type == "concepts":
        items = er.suggest_concepts(args.prefix, types=types, lang=args.lang, count=args.count)
    elif args.suggest_type == "categories":
        items = er.suggest_categories(args.prefix, count=args.count)
    else:
        items = er.suggest_sources(args.prefix, count=args.count)

    if args.output_format == "json":
        print(json.dumps(items, ensure_ascii=False, indent=2))
    else:
        print(render_suggestions(items))
```

5. In `main`, make `max_repeat_request` safe for the suggest parser (which doesn't define it) by changing:

```python
        max_repeat_request = args.max_repeat_request
```

to:

```python
        max_repeat_request = getattr(args, "max_repeat_request", -1)
```

6. In `main`, right after `er = EventRegistryCollector(...)` is initialized, add the suggest branch before the `if args.action == "articles":` check:

```python
        if args.action == "suggest":
            run_suggest(er, args)
            return
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --extra dev pytest tests/test_cli.py -v`
Expected: 8 PASSED

- [ ] **Step 5: Smoke-test the argparser wiring (no API call)**

Run: `uv run collect suggest --help`
Expected: usage text showing `{concepts,categories,sources} prefix` and the `--types`, `--lang`, `--count`, `--format` options.

- [ ] **Step 6: Commit**

```bash
git add tests/test_cli.py collector/cli.py
git commit -m "feat: add suggest subcommand for manual URI selection"
```

---

### Task 6: CLI `--query_file` flag with mutual exclusion

**Files:**
- Modify: `tests/test_cli.py` (append test)
- Modify: `collector/cli.py` (add `--query_file` to the `articles` and `events` subparsers; wire the query into `main`)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli.py`:

```python
def test_articles_and_events_parsers_accept_query_file():
    from collector.cli import create_argparser

    parser = create_argparser()
    args = parser.parse_args(["articles", "--query_file=queries/eu.json"])
    assert args.query_file == "queries/eu.json"
    args = parser.parse_args(["events", "--query_file=queries/eu.json"])
    assert args.query_file == "queries/eu.json"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --extra dev pytest tests/test_cli.py -v -k query_file`
Expected: FAIL with `unrecognized arguments: --query_file=queries/eu.json` (SystemExit)

- [ ] **Step 3: Write the implementation**

In `collector/cli.py`:

1. Add the import at the top (with the local imports):

```python
from collector.query import load_query_file
```

2. In `create_argparser`, add to **both** the `articles` and the `events` subparser (after their `--max_repeat_request` argument — the same block twice):

```python
    subparser.add_argument(
        "--query_file",
        type=str,
        default=None,
        help="The path to a JSON file with a complex query in the ER advanced query language. "
        "Cannot be combined with the keywords/concepts/categories/sources/languages/date flags",
    )
```

3. In `main`, after the `verbose` assignment and before the API key validation, add:

```python
        # load the complex query file if provided
        query = None
        query_file = getattr(args, "query_file", None)
        if query_file:
            conflicting = get_conflicting_flags(args)
            if conflicting:
                logger.error(
                    "--query_file cannot be combined with: %s",
                    ", ".join("--" + flag for flag in conflicting),
                )
                sys.exit(1)
            try:
                query = load_query_file(query_file)
            except ValueError as error:
                logger.error(str(error))
                sys.exit(1)
```

4. Add `query=query,` to the `er.get_articles(...)` call (in the `articles` branch) and the `er.get_events(...)` call (in the `events` branch).

- [ ] **Step 4: Run all tests to verify they pass**

Run: `uv run --extra dev pytest tests/ -v`
Expected: all PASSED

- [ ] **Step 5: Smoke-test the conflict validation (no API call needed — validation runs before the key check only if you have a key set; use a dummy)**

Run: `cd /home/erikn/code/services/event-registry-data-collector && echo '{"conceptUri": "x"}' > /tmp/q.json && uv run collect events --query_file=/tmp/q.json --concepts=slovenia 2>&1 | tail -2; rm /tmp/q.json`
Expected: `ERROR ... --query_file cannot be combined with: --concepts` and exit before any API access.

- [ ] **Step 6: Commit**

```bash
git add tests/test_cli.py collector/cli.py
git commit -m "feat: add --query_file flag for complex queries"
```

---

### Task 7: Documentation and example query

**Files:**
- Create: `queries/eu_presidency.json`
- Modify: `README.md` (add `query_file` rows to the articles/events tables; add a "suggest" action section; add a complex query example)
- Modify: `QUERIES.md` (add the suggest → query file workflow example)

- [ ] **Step 1: Create the example query file**

Create `queries/eu_presidency.json`:

```json
{
  "$query": {
    "$and": [
      {"conceptUri": "http://en.wikipedia.org/wiki/Slovenia"},
      {
        "$or": [
          {"keyword": "EU presidency"},
          {"conceptUri": "http://en.wikipedia.org/wiki/Council_of_the_European_Union"}
        ]
      },
      {"$not": {"categoryUri": "dmoz/Sports"}},
      {"lang": "eng"}
    ]
  }
}
```

- [ ] **Step 2: Update README.md**

Add a `query_file` row to both the `articles` and `events` parameter tables:

```markdown
| query_file         | True     | The path to a JSON file containing a complex query in the Event Registry [advanced query language](https://github.com/EventRegistry/event-registry-python/wiki/Searching-for-articles#advanced-query-language). Cannot be combined with the keywords, concepts, categories, sources, languages, date_start or date_end parameters (Default: None) |
```

Add a new action section after the `events` section:

````markdown
### <a name="suggest"></a> Action: "suggest"

This `{action}` queries the Event Registry suggest API and prints the ranked candidate URIs,
so you can pick the exact concept/category/source instead of relying on automatic resolution.

| Name   | Optional | Description                                                                                                  |
| ------ | -------- | ------------------------------------------------------------------------------------------------------------ |
| type   | False    | The suggestion type (positional). Options: `concepts`, `categories`, `sources`                              |
| prefix | False    | The text the suggestions should match (positional)                                                           |
| types  | True     | The comma separated concept types (concepts only). Options: person, loc, org, wiki, entities, concepts      |
| lang   | True     | The language of the prefix (concepts only) (Default: `'eng'`)                                                |
| count  | True     | The number of suggestions to return (Default: 20)                                                            |
| format | True     | The output format. Options: `table`, `json` (Default: `'table'`)                                             |

```bash
collect suggest concepts "luka doncic" --types=person
collect suggest categories "basketball"
collect suggest sources "delo"
```

When a query uses plain names instead of URIs, the collector resolves them automatically and
logs a warning showing the chosen URI. Use the URI directly (in the flags or in a query file)
to avoid the automatic selection.

### Complex queries with --query_file

For queries that need nested AND/OR/NOT logic, pass a JSON file in the Event Registry
advanced query language to the `articles` or `events` action:

```bash
collect events \
    --max_repeat_request=5 \
    --query_file=./queries/eu_presidency.json \
    --save_to_file=./data/eu_presidency_events.jsonl
```

The file contains a `$query` object built from `$and`/`$or`/`$not` operators (see
[queries/eu_presidency.json](./queries/eu_presidency.json) for an example). A bare query
object without the `$query` wrapper is also accepted. When `--save_to_file` points to an
existing file, the date of the last stored item is injected into the query automatically,
so repeated runs only collect new items.
````

- [ ] **Step 3: Update QUERIES.md**

Add a section at the end:

````markdown
### Complex query: Slovenian EU presidency (excluding sports)

```bash
# 1. find the exact concept URIs to use
collect suggest concepts "slovenia" --types=loc
collect suggest concepts "council of the european union"

# 2. put the chosen URIs into a query file (see queries/eu_presidency.json)

# 3. collect the events matching the complex query
collect events \
    --max_repeat_request=5 \
    --query_file=./queries/eu_presidency.json \
    --save_to_file=./data/events_eu_presidency.jsonl

# 4. get the articles of the collected events
collect event_articles_from_file \
    --max_repeat_request=5 \
    --event_ids_file=./data/events_eu_presidency.jsonl \
    --save_to_file=./data/events_eu_presidency
```
````

- [ ] **Step 4: Run the full test suite and linting**

Run: `uv run --extra dev pytest tests/ -v && uv run --extra dev ruff check collector/ tests/`
Expected: all tests PASSED, no ruff errors

- [ ] **Step 5: Commit**

```bash
git add queries/eu_presidency.json README.md QUERIES.md
git commit -m "docs: document suggest subcommand and complex query files"
```
