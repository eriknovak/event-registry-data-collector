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
