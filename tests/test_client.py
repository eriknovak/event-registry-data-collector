"""Tests for the EventRegistryCollector client (with a mocked ER SDK)."""

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
