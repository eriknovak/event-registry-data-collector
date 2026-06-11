#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Historic backfill of Slovenian news with per-source/per-week coverage tracking.

The script walks completed Mon-Sun ISO weeks backward from the most recent
Sunday strictly before today and collects each one by shelling out to
``python -m collector articles`` (via ``uv`` when available). Anchoring windows
to completed weeks keeps the window keys canonical regardless of which day the
script runs on, so periodic runs (``scripts/cronjob.sh`` is a thin wrapper
around this script) and manual backfills always agree on what has been covered.

A JSON manifest records which source URIs have been collected for each weekly
window. When ``sources.txt`` is later updated with new outlets, re-running only
collects the new ``(source x week)`` combinations instead of re-downloading
everything. Because the collector auto-resumes from the last date of an existing
output file, every collection run writes to a fresh file (``{start}_{end}.jsonl``
or ``{start}_{end}.rN.jsonl`` for later patches) so the full date window is
always collected; partial files left by a failed run are deleted so retries
never duplicate articles.

An exclusive lock next to the manifest (``coverage.json.lock``) prevents
concurrent runs (including ``--dry-run``) from racing on the manifest and on
output filenames. Runs pointed at different ``--manifest`` paths use different
locks and do not exclude each other.
"""

import argparse
import fcntl
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, TextIO, Tuple

# The collector treats both date bounds as inclusive, so a non-overlapping
# weekly window spans the anchor day and the six days before it.
WINDOW_DAYS = 7

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCES_FILE = REPO_ROOT / "scripts" / "sources.txt"
DEFAULT_OUTPUT_DIR = "/vault/data/SLM4IE/raw/slovenian_news"
DEFAULT_WEEKS = 12


def parse_args() -> argparse.Namespace:
    """Parses the command-line arguments.

    Returns:
        argparse.Namespace: The parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Backfill historic Slovenian news week by week, tracking which "
            "sources were covered in which weekly window."
        )
    )
    parser.add_argument(
        "--weeks",
        type=int,
        default=None,
        help=f"Number of weekly windows to walk back from the anchor date "
        f"(default: {DEFAULT_WEEKS} if --start-date is not given).",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Earliest date to backfill to (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="Anchor date for the most recent window (YYYY-MM-DD). Snapped down to the Sunday "
        "ending the enclosing completed Mon-Sun week. Defaults to the most recent completed Sunday.",
    )
    parser.add_argument(
        "--sources-file",
        type=str,
        default=str(DEFAULT_SOURCES_FILE),
        help="Path to the newline-delimited list of source URIs.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where the collected JSONL files are stored.",
    )
    parser.add_argument(
        "--manifest",
        type=str,
        default=None,
        help="Path to the coverage manifest JSON (default: <output-dir>/coverage.json).",
    )
    parser.add_argument(
        "--lang",
        type=str,
        default="slv",
        help="Language code to filter articles by (default: slv).",
    )
    parser.add_argument(
        "--max-repeat-request",
        type=int,
        default=5,
        help="Maximum number of API retry attempts passed to the collector.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned work without calling the collector or writing files.",
    )
    return parser.parse_args()


def parse_date(value: str, flag: str) -> date:
    """Parses a YYYY-MM-DD string into a date.

    Args:
        value (str): The date string.
        flag (str): The originating CLI flag, used in error messages.

    Returns:
        date: The parsed date.

    Raises:
        SystemExit: If the value is not a valid YYYY-MM-DD date.
    """
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        sys.exit(f"error: {flag} must be a YYYY-MM-DD date, got: {value!r}")


def most_recent_completed_sunday(today: date) -> date:
    """Returns the latest Sunday strictly before the given day.

    This is the end of the most recent fully completed Mon-Sun ISO week: on a
    Monday it returns yesterday, while on a Sunday it returns the previous
    Sunday because the current week is not yet complete.

    Args:
        today (date): The reference day.

    Returns:
        date: The most recent Sunday strictly before ``today``.
    """
    return today - timedelta(days=today.isoweekday() % 7 or 7)


def snap_anchor(end_date: Optional[date], today: date) -> Tuple[date, bool]:
    """Snaps the anchor date down to the Sunday ending a completed Mon-Sun week.

    Args:
        end_date (Optional[date]): The requested anchor (``--end-date``), or None
            to default to the most recent completed week.
        today (date): The current day, used to cap the anchor at the last
            completed week.

    Returns:
        Tuple[date, bool]: The snapped anchor and whether it differs from the
        requested ``end_date``.
    """
    last_completed = most_recent_completed_sunday(today)
    if end_date is None:
        return last_completed, False
    # Latest Sunday <= end_date; a Sunday end-date is kept as-is.
    candidate = end_date - timedelta(days=end_date.isoweekday() % 7)
    anchor = min(candidate, last_completed)
    return anchor, anchor != end_date


def load_sources(path: str) -> List[str]:
    """Loads source URIs, skipping blank lines and comments.

    Each line is stripped, blank lines and lines starting with ``#`` are
    dropped, and duplicates are removed while preserving the original order.

    Args:
        path (str): Path to the newline-delimited source list.

    Returns:
        List[str]: The ordered, de-duplicated source URIs.

    Raises:
        SystemExit: If the file does not exist.
    """
    if not os.path.isfile(path):
        sys.exit(f"error: sources file not found: {path}")
    sources: List[str] = []
    seen: Set[str] = set()
    with open(path) as in_file:
        for line in in_file:
            value = line.strip()
            if not value or value.startswith("#"):
                continue
            if value not in seen:
                seen.add(value)
                sources.append(value)
    return sources


def iter_windows(anchor: date, weeks: int, start_limit: Optional[date]) -> List[Tuple[date, date]]:
    """Builds non-overlapping weekly windows walking backward from the anchor.

    Args:
        anchor (date): The end date of the most recent window.
        weeks (int): The maximum number of windows to produce.
        start_limit (Optional[date]): The earliest start date to include. The
            final window's start is clamped up to this date and iteration stops
            once a window would begin before it.

    Returns:
        List[Tuple[date, date]]: ``(start_date, end_date)`` pairs, most recent first.
    """
    windows: List[Tuple[date, date]] = []
    end = anchor
    for _ in range(weeks):
        start = end - timedelta(days=WINDOW_DAYS - 1)
        if start_limit is not None and start <= start_limit:
            # Clamp the final window and stop; both bounds are inclusive.
            windows.append((max(start, start_limit), end))
            break
        windows.append((start, end))
        end = end - timedelta(days=WINDOW_DAYS)
    return windows


def load_manifest(path: str) -> Dict[str, Any]:
    """Loads the coverage manifest, returning an empty one if absent.

    Args:
        path (str): Path to the manifest JSON file.

    Returns:
        Dict[str, Any]: The manifest with a top-level ``windows`` mapping.
    """
    if not os.path.isfile(path):
        return {"windows": {}}
    with open(path) as in_file:
        manifest = json.load(in_file)
    manifest.setdefault("windows", {})
    return manifest


def save_manifest(path: str, manifest: Dict[str, Any]) -> None:
    """Writes the manifest atomically (temp file + replace).

    Args:
        path (str): Destination path for the manifest JSON file.
        manifest (Dict[str, Any]): The manifest to serialize.
    """
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as out_file:
            json.dump(manifest, out_file, indent=2, ensure_ascii=False)
            out_file.write("\n")
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def acquire_lock(lock_path: str) -> TextIO:
    """Acquires an exclusive non-blocking lock, exiting if another run holds it.

    The returned handle must stay referenced for the duration of the run; the
    lock is released automatically when the process exits. The lock file is
    intentionally never unlinked (unlink combined with flock is racy).

    Args:
        lock_path (str): Path to the lock file (created if missing).

    Returns:
        TextIO: The open, locked file handle.

    Raises:
        SystemExit: If another process already holds the lock.
    """
    os.makedirs(os.path.dirname(lock_path) or ".", exist_ok=True)
    lock_file = open(lock_path, "a")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock_file.close()
        sys.exit(f"error: another backfill run holds the lock ({lock_path}); try again later")
    return lock_file


def has_api_key(env_file: Path) -> bool:
    """Checks whether API_KEY is set in the environment or present in the .env file.

    This is a cheap fail-fast heuristic, not a full dotenv parser; the collector
    subprocess loads the .env file itself and remains the authoritative
    validator.

    Args:
        env_file (Path): Path to the .env file to scan.

    Returns:
        bool: True if a non-empty API_KEY value was found.
    """
    if os.environ.get("API_KEY", "").strip():
        return True
    if not env_file.is_file():
        return False
    for raw_line in env_file.read_text().splitlines():
        line = raw_line.strip()
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        name, _, value = line.partition("=")
        if name.strip() == "API_KEY" and value.strip().strip("'\""):
            return True
    return False


def build_query(sources: List[str], lang: str, start: str, end: str) -> Dict[str, Any]:
    """Builds the Event Registry complex query for a window.

    Args:
        sources (List[str]): Source URIs to OR together.
        lang (str): Language code filter.
        start (str): Inclusive start date (YYYY-MM-DD).
        end (str): Inclusive end date (YYYY-MM-DD).

    Returns:
        Dict[str, Any]: The complex query in the full ``$query`` form.
    """
    return {
        "$query": {
            "$and": [
                {"$or": [{"sourceUri": source} for source in sources]},
                {"lang": lang},
                {"dateStart": start, "dateEnd": end},
            ]
        },
        "$filter": {"isDuplicate": "skipDuplicates"},
    }


def pick_output_file(output_dir: str, key: str, known_files: List[str]) -> str:
    """Chooses a fresh output filename for a window collection run.

    Uses ``{key}.jsonl`` for the first run, then ``{key}.rN.jsonl`` with the
    smallest ``N`` (starting at 2) that is neither on disk nor already recorded
    in the manifest. A fresh file avoids the collector's date-resume truncation.

    Args:
        output_dir (str): Directory for output files.
        key (str): The window key (``{start}_{end}``).
        known_files (List[str]): Filenames already recorded for this window.

    Returns:
        str: The chosen filename (basename, not a full path).
    """
    known = set(known_files)

    def taken(name: str) -> bool:
        return name in known or os.path.exists(os.path.join(output_dir, name))

    base = f"{key}.jsonl"
    if not taken(base):
        return base
    index = 2
    while taken(f"{key}.r{index}.jsonl"):
        index += 1
    return f"{key}.r{index}.jsonl"


def run_collector(out_path: str, query: Dict[str, Any], max_repeat: int) -> bool:
    """Runs the collector for a single window via uv or python3.

    Prefers ``uv run`` and falls back to ``python3``. The query is written to a
    temporary file because ``--query_file`` cannot be combined with the date
    flags. On failure the caller deletes any partial output file.

    Args:
        out_path (str): Destination JSONL path (must not already exist).
        query (Dict[str, Any]): The complex query to run.
        max_repeat (int): Value for ``--max_repeat_request``.

    Returns:
        bool: True if the collector exited successfully.
    """
    fd, query_path = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as query_file:
            json.dump(query, query_file, ensure_ascii=False)
        if shutil.which("uv"):
            prefix = ["uv", "run", "python", "-m", "collector"]
        else:
            prefix = ["python3", "-m", "collector"]
        cmd = prefix + [
            "articles",
            f"--max_repeat_request={max_repeat}",
            f"--query_file={query_path}",
            f"--save_to_file={out_path}",
        ]
        # When this script itself runs under `uv run`, uv sets VIRTUAL_ENV to its
        # ephemeral script environment; the nested uv would warn about it not
        # matching the project's .venv, so let the child resolve the env itself.
        env = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}
        result = subprocess.run(cmd, cwd=str(REPO_ROOT), env=env)
        return result.returncode == 0
    finally:
        if os.path.exists(query_path):
            os.remove(query_path)


def main() -> None:
    """Runs the historic backfill across weekly windows."""
    args = parse_args()

    end_date = parse_date(args.end_date, "--end-date") if args.end_date else None
    anchor, moved = snap_anchor(end_date, date.today())
    if moved:
        print(f"note: --end-date snapped to {anchor:%Y-%m-%d} (last completed Mon-Sun week)", file=sys.stderr)
    start_limit = parse_date(args.start_date, "--start-date") if args.start_date else None
    if start_limit is not None and start_limit > anchor:
        sys.exit(
            f"error: --start-date is after the anchor {anchor:%Y-%m-%d} "
            "(--end-date snapped to a completed week / last completed Sunday); nothing to do"
        )

    # Default the window count only when no range is otherwise constrained.
    if args.weeks is not None:
        weeks = args.weeks
    elif start_limit is not None:
        # Large enough to reach any plausible start date; iteration stops at the limit.
        weeks = (anchor - start_limit).days // WINDOW_DAYS + 2
    else:
        weeks = DEFAULT_WEEKS
    if weeks <= 0:
        sys.exit("error: --weeks must be positive")

    if not args.dry_run and not has_api_key(REPO_ROOT / ".env"):
        sys.exit("error: API_KEY is not set in the environment or in <repo>/.env; the collector would fail")

    sources = load_sources(args.sources_file)
    if not sources:
        sys.exit(f"error: no sources found in {args.sources_file}")

    output_dir = args.output_dir
    manifest_path = args.manifest or os.path.join(output_dir, "coverage.json")
    # Held (via the live handle) until the process exits, covering --dry-run too.
    lock_file = acquire_lock(manifest_path + ".lock")
    manifest = load_manifest(manifest_path)

    windows = iter_windows(anchor, weeks, start_limit)
    print(
        f"Backfilling {len(windows)} weekly window(s) from "
        f"{windows[-1][0]:%Y-%m-%d} to {windows[0][1]:%Y-%m-%d} "
        f"({len(sources)} source(s) in list)"
    )

    failures = 0
    for start, end in windows:
        key = f"{start:%Y-%m-%d}_{end:%Y-%m-%d}"
        entry = manifest["windows"].get(key, {})
        covered = set(entry.get("sources", []))
        needed = [source for source in sources if source not in covered]

        if not needed:
            print(f"  ✓ {key} fully covered ({len(covered)} sources), skipping")
            continue

        known_files = entry.get("files", [])
        out_name = pick_output_file(output_dir, key, known_files)
        out_path = os.path.join(output_dir, out_name)

        if args.dry_run:
            print(f"  → {key} would collect {len(needed)} source(s) into {out_name}: {needed}")
            continue

        print(f"  → {key} collecting {len(needed)} source(s) into {out_name}")
        os.makedirs(output_dir, exist_ok=True)
        query = build_query(needed, args.lang, f"{start:%Y-%m-%d}", f"{end:%Y-%m-%d}")
        if not run_collector(out_path, query, args.max_repeat_request):
            print(f"  ✗ {key} collector failed; leaving manifest unchanged", file=sys.stderr)
            # The collector creates the file even with zero articles, and the retry
            # re-collects the full window into a fresh filename, so a leftover
            # partial file would duplicate articles.
            if os.path.exists(out_path):
                os.remove(out_path)
                print(f"  ✗ {key} removed partial file {out_name}", file=sys.stderr)
            failures += 1
            continue

        # Record coverage only after a successful run.
        run_record = {
            "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "file": out_name,
            "sources": needed,
        }
        manifest["windows"][key] = {
            "sources": sorted(covered | set(needed)),
            "files": known_files + [out_name],
            "runs": entry.get("runs", []) + [run_record],
        }
        save_manifest(manifest_path, manifest)

    if failures:
        sys.exit(f"{failures} window(s) failed; re-run to retry them")
    del lock_file  # released at exit; reference kept alive until here


if __name__ == "__main__":
    main()
