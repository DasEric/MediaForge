"""
Library file watcher — watches configured download folders for changes
and triggers targeted cache rescans via filesystem events (watchdog).

Falls back gracefully if watchdog is not installed.
"""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    logger.warning("watchdog is not installed — file watching disabled (pip install watchdog)")


# Video file extensions we care about
_VIDEO_EXTS = {".mkv", ".mp4", ".avi", ".webm", ".flv", ".mov", ".wmv", ".m4v", ".ts"}


# ------------------------------------------------------------------ #
#  Event handler with debounce                                        #
# ------------------------------------------------------------------ #

if WATCHDOG_AVAILABLE:

    class _LibraryEventHandler(FileSystemEventHandler):
        """Debounces rapid burst events and calls scan_callback(path_key)."""

        def __init__(self, path_key: str, scan_callback: Callable[[str], None], debounce: float = 4.0):
            super().__init__()
            self.path_key = path_key
            self.scan_callback = scan_callback
            self.debounce = debounce
            self._timer: Optional[threading.Timer] = None
            self._lock = threading.Lock()

        def _is_relevant(self, path: str) -> bool:
            p = Path(path)
            if p.suffix.lower() not in _VIDEO_EXTS:
                return False
            # Exclude intermediate download files — their stem contains markers like
            # ".temp_audio", ".raw_full", ".new" (e.g. "Title S01E01.temp_audio.mkv")
            stem = p.stem
            for marker in (".temp_", ".raw_", ".new"):
                if marker in stem:
                    return False
            return True

        def _schedule_scan(self) -> None:
            with self._lock:
                if self._timer and self._timer.is_alive():
                    self._timer.cancel()
                self._timer = threading.Timer(self.debounce, self._fire)
                self._timer.daemon = True
                self._timer.start()

        def _fire(self) -> None:
            try:
                self.scan_callback(self.path_key)
            except Exception:
                logger.exception("Library scan callback failed for path_key=%s", self.path_key)

        # watchdog callbacks
        def on_created(self, event):
            if not event.is_directory and self._is_relevant(event.src_path):
                logger.debug("Library: new file detected: %s", event.src_path)
                self._schedule_scan()

        def on_deleted(self, event):
            if self._is_relevant(event.src_path):
                logger.debug("Library: file deleted: %s", event.src_path)
                self._schedule_scan()

        def on_moved(self, event):
            if self._is_relevant(event.src_path) or self._is_relevant(event.dest_path):
                logger.debug("Library: file moved: %s -> %s", event.src_path, event.dest_path)
                self._schedule_scan()


# ------------------------------------------------------------------ #
#  Watcher                                                            #
# ------------------------------------------------------------------ #

class LibraryWatcher:
    """
    Watches one or more base directories and triggers targeted rescans.

    Usage::

        watcher = LibraryWatcher()
        watcher.start(targets, scan_callback)
        # ...
        watcher.stop()
    """

    def __init__(self):
        self._observer = None
        self._active = False
        self._watched: list[dict] = []   # [{path_key, label, path}]
        self._lock = threading.Lock()

    # ---- public API ----

    def start(self, targets: list[tuple], scan_callback: Callable[[str], None]) -> None:
        """
        targets: list of (label, custom_path_id, base_path) — same format as _lib_build_scan_targets()
        scan_callback(path_key): called when a change is detected for path_key
        """
        if not WATCHDOG_AVAILABLE:
            return

        with self._lock:
            self._stop_observer()
            self._watched = []

            observer = Observer()
            for (label, cp_id, base_path) in targets:
                path_key = "default" if cp_id is None else str(cp_id)
                bp = Path(base_path)
                if not bp.is_dir():
                    # Create directory so watchdog can watch it (downloads haven't started yet)
                    try:
                        bp.mkdir(parents=True, exist_ok=True)
                    except OSError:
                        logger.warning("Library watcher: cannot create %s, skipping", bp)
                        continue

                handler = _LibraryEventHandler(path_key, scan_callback)
                observer.schedule(handler, str(bp), recursive=True)
                self._watched.append({"path_key": path_key, "label": label, "path": str(bp)})
                logger.info("Library watcher: watching %s (%s)", bp, path_key)

            observer.start()
            self._observer = observer
            self._active = True

    def stop(self) -> None:
        with self._lock:
            self._stop_observer()

    def restart(self, targets: list[tuple], scan_callback: Callable[[str], None]) -> None:
        """Stop and restart with updated targets (e.g., after settings change)."""
        self.stop()
        self.start(targets, scan_callback)

    @property
    def active(self) -> bool:
        return self._active and WATCHDOG_AVAILABLE

    @property
    def available(self) -> bool:
        return WATCHDOG_AVAILABLE

    @property
    def watched(self) -> list[dict]:
        return list(self._watched)

    # ---- private ----

    def _stop_observer(self) -> None:
        """Must be called while holding self._lock."""
        if self._observer is not None:
            try:
                self._observer.stop()
                self._observer.join(timeout=3)
            except Exception:
                pass
            self._observer = None
        self._active = False
        self._watched = []


# Module-level singleton — imported by app.py
_watcher = LibraryWatcher()


def get_watcher() -> LibraryWatcher:
    return _watcher
