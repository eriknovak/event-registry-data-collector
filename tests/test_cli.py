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
    args = argparse.Namespace(
        keywords="a,b", concepts=None, categories=None, sources="delo.si", languages=None, date_start=None, date_end=None
    )
    assert get_conflicting_flags(args) == ["keywords", "sources"]


def test_get_conflicting_flags_none_set():
    args = argparse.Namespace()
    assert get_conflicting_flags(args) == []


def test_articles_and_events_parsers_accept_query_file():
    from collector.cli import create_argparser

    parser = create_argparser()
    args = parser.parse_args(["articles", "--query_file=examples/eu.json"])
    assert args.query_file == "examples/eu.json"
    args = parser.parse_args(["events", "--query_file=examples/eu.json"])
    assert args.query_file == "examples/eu.json"


def test_run_suggest_routes_by_type(capsys):
    from unittest import mock

    from collector.cli import run_suggest

    er = mock.Mock()
    er.suggest_categories.return_value = [{"uri": "dmoz/Sports"}]
    args = argparse.Namespace(
        suggest_type="categories", prefix="sport", types=None, lang="eng", count=20, output_format="table"
    )
    run_suggest(er, args)
    er.suggest_categories.assert_called_once_with("sport", count=20)
    er.suggest_concepts.assert_not_called()
    er.suggest_sources.assert_not_called()
    assert "dmoz/Sports" in capsys.readouterr().out


def test_run_suggest_json_output(capsys):
    from unittest import mock

    from collector.cli import run_suggest

    er = mock.Mock()
    er.suggest_sources.return_value = [{"uri": "delo.si", "title": "Delo"}]
    args = argparse.Namespace(
        suggest_type="sources", prefix="delo", types=None, lang="eng", count=20, output_format="json"
    )
    run_suggest(er, args)
    import json as json_lib

    assert json_lib.loads(capsys.readouterr().out) == [{"uri": "delo.si", "title": "Delo"}]


def test_article_parsers_accept_article_fields():
    from collector.cli import create_argparser

    parser = create_argparser()
    for action in ("articles", "event_articles", "event_articles_from_file"):
        args = parser.parse_args([action, "--article_fields=concepts,categories"])
        assert args.article_fields == "concepts,categories"


def test_articles_parser_duplicates_defaults_to_keep():
    from collector.cli import create_argparser

    parser = create_argparser()
    assert parser.parse_args(["articles"]).duplicates == "keep"
    assert parser.parse_args(["articles", "--duplicates=skip"]).duplicates == "skip"


def test_duplicates_flag_reaches_get_articles(monkeypatch):
    import sys
    from unittest import mock

    from collector.cli import main

    monkeypatch.setenv("API_KEY", "test-key")
    monkeypatch.setattr(sys, "argv", ["collect", "articles", "--keywords=x", "--duplicates=skip"])
    with mock.patch("collector.cli.EventRegistryCollector") as er, mock.patch("collector.cli.load_dotenv"):
        main()
    assert er.return_value.get_articles.call_args.kwargs["is_duplicate_filter"] == "skipDuplicates"


def test_parse_article_fields_ignores_empty_items():
    from collector.cli import parse_article_fields

    info = parse_article_fields("concepts, categories,")
    assert info.getConf()["articleInfo"] == {"includeArticleConcepts": True, "includeArticleCategories": True}


def test_parse_article_fields_without_fields_keeps_the_defaults():
    from collector.cli import parse_article_fields

    assert parse_article_fields(None) is None
    assert parse_article_fields(" , ") is None


def test_parse_article_fields_rejects_unknown_fields():
    import pytest

    from collector.cli import parse_article_fields

    with pytest.raises(ValueError, match="'tone'"):
        parse_article_fields("tone")
