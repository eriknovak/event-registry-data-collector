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
        yield EventRegistryCollector(api_key="test-key")


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
    assert is_source_uri("bbc.co.uk")
    assert not is_source_uri("BBC")
    assert not is_source_uri("http://en.wikipedia.org/wiki/BBC")


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


def test_suggest_concepts_default_types(collector):
    """Without types the SDK is queried with the broad 'concepts' source."""
    collector._er.suggestConcepts.return_value = [{"uri": "u", "type": "wiki"}]
    result = collector.suggest_concepts("luka")
    assert result == [{"uri": "u", "type": "wiki"}]
    collector._er.suggestConcepts.assert_called_once_with(
        "luka", sources=["concepts"], lang="eng", count=20
    )


def test_suggest_concepts_with_types(collector):
    """Explicit types are forwarded as the SDK sources parameter."""
    collector._er.suggestConcepts.return_value = []
    collector.suggest_concepts("luka", types=["person", "org"], lang="slv", count=5)
    collector._er.suggestConcepts.assert_called_once_with(
        "luka", sources=["person", "org"], lang="slv", count=5
    )


def test_suggest_categories(collector):
    collector._er.suggestCategories.return_value = [{"uri": "dmoz/Sports"}]
    assert collector.suggest_categories("sport", count=5) == [{"uri": "dmoz/Sports"}]
    collector._er.suggestCategories.assert_called_once_with("sport", count=5)


def test_suggest_sources(collector):
    collector._er.suggestNewsSources.return_value = [{"uri": "delo.si", "title": "Delo"}]
    assert collector.suggest_sources("delo") == [{"uri": "delo.si", "title": "Delo"}]
    collector._er.suggestNewsSources.assert_called_once_with("delo", count=20)


def test_get_last_date_missing_file(tmp_path):
    from collector.client import get_last_date

    assert get_last_date(str(tmp_path / "missing.jsonl"), "date") is None


def test_get_last_date_reads_last_line(tmp_path):
    from collector.client import get_last_date

    path = tmp_path / "articles.jsonl"
    path.write_text(json.dumps({"date": "2026-01-01"}) + "\n" + json.dumps({"date": "2026-01-02"}) + "\n")
    assert get_last_date(str(path), "date") == "2026-01-02"


def test_get_last_date_empty_file(tmp_path):
    from collector.client import get_last_date

    path = tmp_path / "empty.jsonl"
    path.write_text("")
    assert get_last_date(str(path), "date") is None


def test_get_last_date_ignores_trailing_blank_lines(tmp_path):
    from collector.client import get_last_date

    path = tmp_path / "articles.jsonl"
    path.write_text(json.dumps({"date": "2026-01-02"}) + "\n\n")
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


def test_get_articles_complex_query_requires_query_key(collector):
    """A bare query dict without $query is rejected up front."""
    with pytest.raises(ValueError, match="full"):
        collector.get_articles(query={"conceptUri": "x"})


def test_get_events_complex_query_requires_query_key(collector):
    with pytest.raises(ValueError, match="full"):
        collector.get_events(query={"conceptUri": "x"})
