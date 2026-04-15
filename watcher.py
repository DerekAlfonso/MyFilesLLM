# watcher.py — Real-time filesystem watcher with per-file debouncing.
"""
Monitors all WATCH_PATHS for file changes and updates the index automatically.

Debouncing: each file change resets a DEBOUNCE_SECONDS timer.  The index is
only updated once the file has been stable for that long — this avoids
re-indexing mid-save when editors write files in multiple short bursts.

Usage
-----
  python watcher.py               # watch all WATCH_PATHS from config.py
  python watcher.py --once        # run indexer.py once then exit (for Task Scheduler)

To run continuously on Windows startup, create a Scheduled Task that runs:
  Program:   C:/path/to/FileIndexer/.venv/Scripts/pythonw.exe
  Arguments: watcher.py
  Start in:  C:/path/to/FileIndexer
"""

from __future__ import annotations

# ── watchdog package import workaround ────────────────────────────────────────
# The project contains a legacy file named watchdog.py.  Because Python puts the
# script's directory first on sys.path, that file would shadow the *installed*
# watchdog package if we imported it normally.  We temporarily remove this
# directory from sys.path so the real package is found in site-packages, then
# restore it afterwards.
import sys as _sys
import os as _os

_this_dir = _os.path.normcase(_os.path.dirname(_os.path.abspath(__file__)))
_saved_path = _sys.path[:]
_sys.path = [p for p in _sys.path if _os.path.normcase(p) != _this_dir]

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

_sys.path = _saved_path
del _this_dir, _saved_path
# ── end workaround ────────────────────────────────────────────────────────────

import argparse
import logging
import subprocess
import threading
import time
from pathlib import Path

from config import WATCH_PATHS, SKIP_DIRS, DEBOUNCE_SECONDS
from indexer import index_file, remove_file

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [watcher] %(message)s",
)


# ── Debounced event handler ───────────────────────────────────────────────────

class _DebouncedHandler(FileSystemEventHandler):
    """
    Routes watchdog events to index_file / remove_file with per-path debouncing.

    A threading.Lock guards the _timers dict because watchdog dispatches events
    on its own background thread while timer callbacks also run on daemon threads.
    """

    def __init__(self) -> None:
        super().__init__()
        self._timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    # ── helpers ───────────────────────────────────────────────────────────────

    def _skip(self, path: str) -> bool:
        """True if any path component is in SKIP_DIRS or starts with '.'."""
        return any(part in SKIP_DIRS or part.startswith(".")
                   for part in Path(path).parts)

    def _schedule(self, path: str, action: str) -> None:
        """Cancel any existing timer for path, then start a fresh debounce timer."""
        with self._lock:
            old = self._timers.pop(path, None)
            if old:
                old.cancel()
            if action == "remove":
                timer = threading.Timer(
                    DEBOUNCE_SECONDS, self._do_remove, args=(path,)
                )
            else:
                timer = threading.Timer(
                    DEBOUNCE_SECONDS, self._do_index, args=(path,)
                )
            self._timers[path] = timer
            timer.daemon = True
            timer.start()

    def _cancel(self, path: str) -> None:
        """Cancel any pending timer for path (used when file is deleted)."""
        with self._lock:
            timer = self._timers.pop(path, None)
            if timer:
                timer.cancel()

    def _do_index(self, path: str) -> None:
        with self._lock:
            self._timers.pop(path, None)
        if not _os.path.exists(path):
            return  # deleted before debounce fired
        try:
            result = index_file(path, force=True)
            log.info(f"[{result}] {path}")
        except Exception as exc:
            log.error(f"index_file error — {path}: {exc}")

    def _do_remove(self, path: str) -> None:
        with self._lock:
            self._timers.pop(path, None)
        try:
            remove_file(path)
        except Exception as exc:
            log.error(f"remove_file error — {path}: {exc}")

    # ── watchdog callbacks ────────────────────────────────────────────────────

    def on_created(self, event):
        if not event.is_directory and not self._skip(event.src_path):
            self._schedule(event.src_path, "index")

    def on_modified(self, event):
        if not event.is_directory and not self._skip(event.src_path):
            self._schedule(event.src_path, "index")

    def on_moved(self, event):
        if event.is_directory:
            return
        src, dest = event.src_path, event.dest_path
        # Cancel any pending index of the old path immediately — file is gone
        self._cancel(src)
        try:
            remove_file(src)
        except Exception as exc:
            log.error(f"remove_file (move src) — {src}: {exc}")
        # Schedule index of the new path (OS may still be flushing writes)
        if not self._skip(dest):
            self._schedule(dest, "index")

    def on_deleted(self, event):
        if not event.is_directory:
            # Cancel any pending index — pointless now that file is gone
            self._cancel(event.src_path)
            try:
                remove_file(event.src_path)
            except Exception as exc:
                log.error(f"remove_file (delete) — {event.src_path}: {exc}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="FileIndexer watcher — monitor directories and update the index"
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Run a full index scan once and exit (suitable for Task Scheduler)"
    )
    parser.add_argument(
        "--paths", nargs="+", metavar="PATH",
        help="Override WATCH_PATHS for this session"
    )
    args = parser.parse_args()

    watch_paths = args.paths or WATCH_PATHS

    if args.once:
        log.info("Running one-shot index scan…")
        result = subprocess.run(
            [_sys.executable, _os.path.join(_os.path.dirname(__file__), "indexer.py")]
            + (["--paths"] + watch_paths if args.paths else [])
        )
        _sys.exit(result.returncode)

    handler  = _DebouncedHandler()
    observer = Observer()

    registered = 0
    for wp in watch_paths:
        if _os.path.isdir(wp):
            observer.schedule(handler, wp, recursive=True)
            log.info(f"Watching: {wp}")
            registered += 1
        else:
            log.warning(f"Watch path not found, skipping: {wp}")

    if registered == 0:
        log.error("No valid watch paths. Check WATCH_PATHS in config.py.")
        _sys.exit(1)

    observer.start()
    log.info(
        f"Watcher running (debounce: {DEBOUNCE_SECONDS}s). "
        "Press Ctrl-C to stop."
    )
    try:
        while observer.is_alive():
            observer.join(timeout=1.0)
    except KeyboardInterrupt:
        log.info("Stopping…")
    finally:
        observer.stop()
        observer.join()
        log.info("Watcher stopped.")
