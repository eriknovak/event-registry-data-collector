"""Tests for the file-saving helpers."""

import json

from collector.storage import save_result_in_file


def test_line_format_preserves_utf8(tmp_path):
    """Slovenian characters are stored as literal UTF-8, not \\uXXXX escapes."""
    file_path = tmp_path / "articles.jsonl"
    articles = [{"title": "Slovenščina: čšž ČŠŽ", "body": "Maribor — đ"}]

    save_result_in_file(articles, str(file_path))

    raw = file_path.read_text(encoding="utf-8")
    assert "Slovenščina: čšž ČŠŽ" in raw
    assert "\\u" not in raw
    assert json.loads(raw)["title"] == "Slovenščina: čšž ČŠŽ"


def test_array_format_preserves_utf8(tmp_path):
    """The array save format also stores literal UTF-8 characters."""
    file_path = tmp_path / "articles.json"
    articles = [{"title": "Žužemberk"}, {"title": "Škofja Loka"}]

    save_result_in_file(articles, str(file_path), save_format="array")

    raw = file_path.read_text(encoding="utf-8")
    assert "Žužemberk" in raw
    assert "Škofja Loka" in raw
    assert "\\u" not in raw
    assert [a["title"] for a in json.loads(raw)] == ["Žužemberk", "Škofja Loka"]
