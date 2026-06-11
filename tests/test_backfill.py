"""Tests for the scripts/backfill.py helper functions."""

import importlib.util
import json
from datetime import date
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "backfill.py"
_SPEC = importlib.util.spec_from_file_location("backfill", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
backfill = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(backfill)


# ---------------------------------------------------------------------------
# Anchor snapping
# ---------------------------------------------------------------------------


def test_most_recent_completed_sunday_midweek():
    """A midweek day anchors to the Sunday ending the previous week."""
    assert backfill.most_recent_completed_sunday(date(2026, 6, 10)) == date(2026, 6, 7)


def test_most_recent_completed_sunday_on_monday():
    """A Monday anchors to yesterday, the week that just completed."""
    assert backfill.most_recent_completed_sunday(date(2026, 6, 8)) == date(2026, 6, 7)


def test_most_recent_completed_sunday_on_sunday():
    """A Sunday anchors to the previous Sunday because its week is incomplete."""
    assert backfill.most_recent_completed_sunday(date(2026, 6, 7)) == date(2026, 5, 31)


def test_most_recent_completed_sunday_on_saturday():
    """A Saturday anchors to the Sunday before the current incomplete week."""
    assert backfill.most_recent_completed_sunday(date(2026, 6, 6)) == date(2026, 5, 31)


def test_snap_anchor_default_no_end_date():
    """Without an end date the anchor defaults to the last completed Sunday, unmoved."""
    anchor, moved = backfill.snap_anchor(None, date(2026, 6, 10))
    assert anchor == date(2026, 6, 7)
    assert moved is False


def test_snap_anchor_past_sunday_unmoved():
    """A past Sunday end date is kept as-is."""
    anchor, moved = backfill.snap_anchor(date(2026, 5, 31), date(2026, 6, 10))
    assert anchor == date(2026, 5, 31)
    assert moved is False


def test_snap_anchor_midweek_end_date_snaps_down():
    """A midweek end date snaps down to the Sunday of the enclosing completed week."""
    anchor, moved = backfill.snap_anchor(date(2026, 6, 3), date(2026, 6, 10))
    assert anchor == date(2026, 5, 31)
    assert moved is True


def test_snap_anchor_end_date_today_sunday_capped():
    """An end date equal to today (a Sunday) is capped to the previous Sunday."""
    anchor, moved = backfill.snap_anchor(date(2026, 6, 7), date(2026, 6, 7))
    assert anchor == date(2026, 5, 31)
    assert moved is True


def test_snap_anchor_future_end_date_capped():
    """A future end date is capped at the last completed Sunday."""
    anchor, moved = backfill.snap_anchor(date(2099, 1, 1), date(2026, 6, 10))
    assert anchor == date(2026, 6, 7)
    assert moved is True


# ---------------------------------------------------------------------------
# iter_windows
# ---------------------------------------------------------------------------


def test_iter_windows_mon_sun_alignment():
    """A Sunday anchor yields contiguous non-overlapping Mon-Sun windows, most recent first."""
    windows = backfill.iter_windows(date(2026, 6, 7), 3, None)
    assert windows == [
        (date(2026, 6, 1), date(2026, 6, 7)),
        (date(2026, 5, 25), date(2026, 5, 31)),
        (date(2026, 5, 18), date(2026, 5, 24)),
    ]
    assert all(start.isoweekday() == 1 and end.isoweekday() == 7 for start, end in windows)


def test_iter_windows_clamps_to_start_limit():
    """Iteration stops at the start limit and clamps the final window to it."""
    windows = backfill.iter_windows(date(2026, 6, 7), 10, date(2026, 5, 27))
    assert windows == [
        (date(2026, 6, 1), date(2026, 6, 7)),
        (date(2026, 5, 27), date(2026, 5, 31)),
    ]


def test_iter_windows_start_limit_on_boundary():
    """A start limit equal to a window start clamps that window and stops."""
    windows = backfill.iter_windows(date(2026, 6, 7), 10, date(2026, 5, 25))
    assert windows == [
        (date(2026, 6, 1), date(2026, 6, 7)),
        (date(2026, 5, 25), date(2026, 5, 31)),
    ]


def test_iter_windows_respects_weeks_count():
    """No more than the requested number of windows is produced."""
    assert len(backfill.iter_windows(date(2026, 6, 7), 1, None)) == 1
    assert len(backfill.iter_windows(date(2026, 6, 7), 5, None)) == 5


# ---------------------------------------------------------------------------
# pick_output_file
# ---------------------------------------------------------------------------


def test_pick_output_file_base_when_free(tmp_path):
    """The plain {key}.jsonl name is used when nothing is taken."""
    assert backfill.pick_output_file(str(tmp_path), "2026-06-01_2026-06-07", []) == "2026-06-01_2026-06-07.jsonl"


def test_pick_output_file_r2_when_base_on_disk(tmp_path):
    """An existing base file on disk pushes the run to the .r2 revision."""
    (tmp_path / "2026-06-01_2026-06-07.jsonl").touch()
    assert backfill.pick_output_file(str(tmp_path), "2026-06-01_2026-06-07", []) == "2026-06-01_2026-06-07.r2.jsonl"


def test_pick_output_file_skips_known_files(tmp_path):
    """Names recorded in the manifest are skipped even when absent from disk."""
    known = ["2026-06-01_2026-06-07.jsonl"]
    assert backfill.pick_output_file(str(tmp_path), "2026-06-01_2026-06-07", known) == "2026-06-01_2026-06-07.r2.jsonl"


def test_pick_output_file_increments_past_taken_revisions(tmp_path):
    """The smallest free revision index is chosen."""
    (tmp_path / "2026-06-01_2026-06-07.jsonl").touch()
    (tmp_path / "2026-06-01_2026-06-07.r2.jsonl").touch()
    known = ["2026-06-01_2026-06-07.r3.jsonl"]
    assert backfill.pick_output_file(str(tmp_path), "2026-06-01_2026-06-07", known) == "2026-06-01_2026-06-07.r4.jsonl"


# ---------------------------------------------------------------------------
# load_sources
# ---------------------------------------------------------------------------


def test_load_sources_filters_comments_blanks_and_dupes(tmp_path):
    """Comments, blank lines, and duplicates are dropped while order is preserved."""
    sources_file = tmp_path / "sources.txt"
    sources_file.write_text("delo.si\n\n# rtvslo.si\nsta.si\ndelo.si\n  \n24ur.com\n")
    assert backfill.load_sources(str(sources_file)) == ["delo.si", "sta.si", "24ur.com"]


def test_load_sources_missing_file_exits(tmp_path):
    """A missing sources file exits with an error."""
    with pytest.raises(SystemExit):
        backfill.load_sources(str(tmp_path / "missing.txt"))


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


def test_manifest_save_load_round_trip(tmp_path):
    """A saved manifest loads back identically."""
    path = str(tmp_path / "coverage.json")
    manifest = {"windows": {"2026-06-01_2026-06-07": {"sources": ["delo.si"], "files": [], "runs": []}}}
    backfill.save_manifest(path, manifest)
    assert backfill.load_manifest(path) == manifest
    # The file is valid, indented JSON with a trailing newline.
    content = Path(path).read_text()
    assert content.endswith("\n")
    assert json.loads(content) == manifest


def test_load_manifest_missing_returns_empty_windows(tmp_path):
    """A missing manifest file yields an empty windows mapping."""
    assert backfill.load_manifest(str(tmp_path / "coverage.json")) == {"windows": {}}


# ---------------------------------------------------------------------------
# has_api_key
# ---------------------------------------------------------------------------


def test_has_api_key_from_environment(tmp_path, monkeypatch):
    """A non-empty API_KEY environment variable is sufficient."""
    monkeypatch.setenv("API_KEY", "secret")
    assert backfill.has_api_key(tmp_path / ".env") is True


def test_has_api_key_from_env_file(tmp_path, monkeypatch):
    """API_KEY is found in plain, quoted, and export-prefixed .env lines."""
    monkeypatch.delenv("API_KEY", raising=False)
    env_file = tmp_path / ".env"
    for line in ["API_KEY=secret", 'API_KEY="secret"', "export API_KEY='secret'"]:
        env_file.write_text(f"OTHER=1\n{line}\n")
        assert backfill.has_api_key(env_file) is True, line


def test_has_api_key_absent(tmp_path, monkeypatch):
    """No env var and a missing or empty-valued .env file means no key."""
    monkeypatch.delenv("API_KEY", raising=False)
    assert backfill.has_api_key(tmp_path / ".env") is False
    env_file = tmp_path / ".env"
    env_file.write_text("API_KEY=\nOTHER=1\n")
    assert backfill.has_api_key(env_file) is False


# ---------------------------------------------------------------------------
# acquire_lock
# ---------------------------------------------------------------------------


def test_acquire_lock_blocks_second_acquisition(tmp_path):
    """A second acquisition of the same lock file exits while the first holds it."""
    lock_path = str(tmp_path / "coverage.json.lock")
    lock_file = backfill.acquire_lock(lock_path)
    try:
        with pytest.raises(SystemExit):
            backfill.acquire_lock(lock_path)
    finally:
        lock_file.close()
    # After release the lock can be taken again.
    backfill.acquire_lock(lock_path).close()
