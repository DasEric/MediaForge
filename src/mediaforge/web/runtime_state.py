"""Shared module-level runtime state used across workers and routes.

This is the new home for state that used to live inline as closure variables
inside the old monolithic ``create_app()`` (registries, locks, flags, and the
small accessor functions that guard them). Pulling it out into a plain module
means every worker thread and every route module can ``import runtime_state``
and share the exact same objects, instead of relying on closures that only
``create_app()`` itself could see.

Used by (non-exhaustive): request_context.py (auth check), routes/queue.py,
routes/favourites.py and routes/syncplay.py (AUTH_ENABLED / cancel events),
routes/autosync.py and routes/search.py (series-link patterns / sync-schedule
maps), queue_worker.py and autosync_worker.py (the worker loops that actually
mutate this state), and app.py (which sets AUTH_ENABLED and wires the
pause/cancel state up at startup).
"""

import re
import threading

from ..config import SUPPORTED_PROVIDERS
from ..extractors import provider_functions
from ..logger import get_logger
from .db import get_setting, set_setting

logger = get_logger(__name__)


# Whether authentication is enabled for the running app. Set once by app.py's
# create_app() during startup. Read by request_context.get_current_user_info()
# and directly by routes/favourites.py, routes/queue.py and routes/syncplay.py
# so those modules don't need their own reference to the create_app() scope.
AUTH_ENABLED = False


# Registry of active cancel events keyed by queue item ID.
# queue_worker.py registers an event while an item is downloading; routes/queue.py's
# api_queue_cancel() sets it to interrupt the active subprocess immediately.
_active_cancel_events: dict = {}
_active_cancel_events_lock = threading.Lock()


def _get_working_providers():
    """Return only providers whose extractors are actually implemented.

    Each extractor is probed with an empty URL string.  If it raises
    NotImplementedError the provider is considered not yet implemented and is
    skipped.  Any other exception means the extractor *is* implemented (it just
    rejected the empty URL as expected).  Logging is silenced during the probe
    so that the intentional empty-URL errors don't spam the terminal on startup.
    """
    import logging as _logging
    working = []
    for p in SUPPORTED_PROVIDERS:
        func_name = f"get_direct_link_from_{p.lower()}"
        if func_name not in provider_functions:
            continue
        _logging.disable(_logging.CRITICAL)  # suppress expected empty-URL errors
        try:
            provider_functions[func_name]("")
        except NotImplementedError:
            continue
        except Exception:
            working.append(p)
        finally:
            _logging.disable(_logging.NOTSET)  # restore normal logging
    return tuple(working)


WORKING_PROVIDERS = _get_working_providers()

# Only match series-level links: /anime/stream/<slug> (no season/episode).
# Used by routes/autosync.py and routes/search.py to tell a series page apart
# from a season/episode page when scraping search results.
_SERIES_LINK_PATTERN = re.compile(r"^/anime/stream/[a-zA-Z0-9\-]+/?$", re.IGNORECASE)

# Only match s.to series-level links: /serie/<slug> (no season/episode)
_STO_SERIES_LINK_PATTERN = re.compile(
    r"^/serie/(stream/)?[a-zA-Z0-9\-]+/?$", re.IGNORECASE
)


# Global pause flag — when True the worker waits after finishing the current episode.
# Persisted in app_settings DB so it survives restarts.
_queue_paused = False
_queue_pause_lock = threading.Lock()

# Per-job skip-episode flag — worker checks this after each download attempt.
# When set for a job ID, the current episode is silently skipped (no error recorded).
_skip_episode_ids: set = set()
_skip_episode_lock = threading.Lock()


def is_episode_skip_requested(queue_id: int) -> bool:
    with _skip_episode_lock:
        return queue_id in _skip_episode_ids


def request_episode_skip(queue_id: int):
    with _skip_episode_lock:
        _skip_episode_ids.add(queue_id)


def consume_episode_skip(queue_id: int) -> bool:
    """Return True and clear the flag if a skip was requested, else False."""
    with _skip_episode_lock:
        if queue_id in _skip_episode_ids:
            _skip_episode_ids.discard(queue_id)
            return True
        return False


def _load_queue_paused_from_db() -> None:
    """Read persisted pause state from DB into the in-memory flag.

    Used by: app.py, called once during create_app() startup so the pause
    flag matches what was last saved before restart.
    """
    global _queue_paused
    try:
        val = get_setting("queue_paused", "0")
        with _queue_pause_lock:
            _queue_paused = val == "1"
    except Exception as e:
        logger.warning("[Queue] Could not load pause state from DB, defaulting to unpaused: %s", e)


def is_queue_paused():
    with _queue_pause_lock:
        return _queue_paused


def set_queue_paused(paused: bool):
    global _queue_paused
    with _queue_pause_lock:
        _queue_paused = paused
    try:
        set_setting("queue_paused", "1" if paused else "0")
    except Exception as e:
        logger.warning("[Queue] Could not persist pause state to DB (in-memory state still applied): %s", e)


# Track jobs currently being synced to prevent duplicate runs.
# Guarded by _syncing_jobs_lock in autosync_worker.py; read (without the lock,
# for a quick membership check) by routes/autosync.py to report running jobs.
_syncing_jobs = set()
_syncing_jobs_lock = threading.Lock()

# Upscale worker cancel-events registry (same pattern as _active_cancel_events,
# but for the separate upscale queue). Used by upscale_worker.py and
# routes/upscale.py's cancel endpoint.
_upscale_active_cancel_events: dict = {}
_upscale_cancel_lock = threading.Lock()

# Library move job tracking, read/written by routes/library.py's move-job
# start/status/cleanup endpoints.
_move_jobs: dict = {}  # job_id -> {status, copied_bytes, total_bytes, current_file, error}
_move_jobs_lock = threading.Lock()

# Schedule intervals in seconds
SYNC_SCHEDULE_MAP = {
    "1min": 60,
    "30min": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "8h": 28800,
    "12h": 43200,
    "16h": 57600,
    "24h": 86400,
}

# Retry delay map
SYNC_RETRY_MAP = {
    "0min": 0,
    "1min": 60,
    "2min": 120,
    "3min": 180,
    "4min": 240,
    "5min": 300,
}

# Adaptive Auto-Sync: how long without a new episode before a job enters
# "pause mode" (slower re-check cadence). Values in seconds.
SYNC_ADAPTIVE_PAUSE_MAP = {
    "2w": 2 * 7 * 86400,
    "3w": 3 * 7 * 86400,
    "4w": 4 * 7 * 86400,
    "5w": 5 * 7 * 86400,
    "6w": 6 * 7 * 86400,
    "7w": 7 * 7 * 86400,
    "8w": 8 * 7 * 86400,
}

# Adaptive Auto-Sync retry unit -> seconds multiplier.
SYNC_ADAPTIVE_UNIT_MAP = {
    "days": 86400,
    "weeks": 7 * 86400,
    "months": 30 * 86400,
}
