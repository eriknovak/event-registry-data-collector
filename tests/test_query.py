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
