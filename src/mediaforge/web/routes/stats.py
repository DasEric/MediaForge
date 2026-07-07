"""Statistics routes.

Extracted from create_app as a plain route-registration function
(no Flask blueprint: endpoint names stay bare so url_for() keeps working).
"""

from ..db import add_media_ignores
from ..db import get_all_library_cache
from ..db import get_general_stats
from ..db import get_media_ignores
from ..db import get_queue_stats
from ..db import get_setting
from ..db import get_sync_stats
from ..db import remove_media_ignore
from ..runtime_state import SYNC_SCHEDULE_MAP
from .library import _lib_build_scan_targets
from .library import _lib_trigger_scan_async
from flask import jsonify
from flask import render_template
from flask import request
import os


def _media_missing_episodes(seasons: dict) -> list:
    """Detect gaps in a series' episode numbering from library data alone.

    Returns a list of human-readable missing slots (e.g. "S1E3", "S2").
    A whole season counts as missing when it is absent within the
    1..max-season range; within a present season, any episode missing
    between 1 and the highest present episode is reported. An empty list
    means the series is considered complete."""
    notes = []
    season_nums = sorted(
        int(k) for k in seasons.keys()
        if k != "movies" and str(k).isdigit()
    )
    if not season_nums:
        return notes  # only loose/movie files — not treated as a gappy series
    for s in range(1, max(season_nums) + 1):
        skey = str(s)
        if s not in season_nums:
            notes.append(f"S{s}")  # whole season missing
            continue
        eps = sorted({
            e.get("episode") for e in seasons.get(skey, [])
            if e.get("episode") is not None and e.get("is_video", True)
        })
        if not eps:
            continue
        present = set(eps)
        for ep in range(1, max(eps) + 1):
            if ep not in present:
                notes.append(f"S{s}E{ep}")
    return notes


def _compute_media_stats():
    """Build the Media statistics category from the library cache.

    The library cache is kept current by the library watcher, so these
    numbers track on-disk media automatically. Series that appear in
    multiple language folders (lang-separation mode) are merged by folder
    name so each logical series is counted once; their seasons are unioned
    so an episode present in any language counts as present."""
    cache = get_all_library_cache()
    any_scanning = any(e.get("is_scanning") for e in cache.values())
    ignores = get_media_ignores()

    # Merge titles across all locations / language folders by folder name.
    series = {}  # folder -> {"seasons": {skey: set(eps)}, "episodes": int, "location": str}
    movie_folders = set()

    for path_key, entry in cache.items():
        data = entry.get("data") or {}
        location = data.get("label", path_key)
        lang_folders = data.get("lang_folders") or []
        if lang_folders:
            title_lists = [lf.get("titles") or [] for lf in lang_folders]
        else:
            title_lists = [data.get("titles") or []]
        for titles in title_lists:
            for t in titles:
                folder = t.get("folder")
                if not folder:
                    continue
                if t.get("is_movie"):
                    movie_folders.add(folder.lower())
                    continue
                agg = series.setdefault(
                    folder.lower(),
                    {"title": folder, "seasons": {}, "location": location},
                )
                for skey, eps in (t.get("seasons") or {}).items():
                    bucket = agg["seasons"].setdefault(skey, set())
                    for e in eps:
                        if e.get("episode") is not None and e.get("is_video", True):
                            bucket.add(e.get("episode"))

    movies_total = len(movie_folders)
    series_total = len(series)
    episodes_total = 0
    complete = 0
    incomplete_list = []

    for folder_key, agg in series.items():
        # episode count = distinct episodes across all (numeric) seasons
        for skey, eps in agg["seasons"].items():
            if skey != "movies":
                episodes_total += len(eps)
        seasons_for_gap = {
            skey: [{"episode": ep} for ep in eps]
            for skey, eps in agg["seasons"].items()
        }
        missing = _media_missing_episodes(seasons_for_gap)
        # Subtract user-ignored slots so a series whose remaining gaps are
        # all ignored counts as complete.
        ig = ignores.get(folder_key)
        if ig:
            if "__all__" in ig["slots"]:
                missing = []
            else:
                missing = [m for m in missing if m not in ig["slots"]]
        if missing:
            incomplete_list.append({
                "folder": folder_key,
                "title": agg["title"],
                "location": agg["location"],
                "missing": missing,
            })
        else:
            complete += 1

    incomplete_list.sort(key=lambda x: x["title"].lower())

    # Management view: everything the user has ignored, so it can be restored.
    ignored_list = [
        {
            "folder": folder_key,
            "title": ig.get("title") or folder_key,
            "slots": sorted(ig["slots"]),
        }
        for folder_key, ig in ignores.items()
    ]
    ignored_list.sort(key=lambda x: x["title"].lower())

    return {
        "movies_total": movies_total,
        "series_total": series_total,
        "series_complete": complete,
        "series_incomplete": len(incomplete_list),
        "episodes_total": episodes_total,
        "incomplete": incomplete_list,
        "ignored": ignored_list,
        "scanning": any_scanning,
        "scanned": bool(cache),
    }


def register_stats_routes(app):
    """Register the Statistics page and its supporting API routes
    (general/queue/sync/media stats, ignore-list management) on the
    Flask app."""
    @app.route("/stats")
    def stats_page():
        """Render the Statistics page. GET /stats."""
        return render_template("stats.html")
    @app.route("/api/stats")
    def api_stats():
        """Return the combined stats payload (general, queue, sync, and —
        if enabled — media library stats). Triggers an initial library scan
        on first call if media stats are enabled but nothing has been
        scanned yet. GET /api/stats.

        Called from static/stats.js's `loadStats()`."""
        payload = {
            "general": get_general_stats(),
            "queue": get_queue_stats(),
            "sync": get_sync_stats(),
        }
        media_enabled = (get_setting("media_stats_enabled")
                         or os.environ.get("MEDIAFORGE_MEDIA_STATS_ENABLED", "0")) == "1"
        if media_enabled:
            # Kick off an initial library scan if nothing has been scanned yet,
            # so the Media category isn't permanently empty for fresh installs.
            if not get_all_library_cache():
                lang_sep = os.environ.get("MEDIAFORGE_LANG_SEPARATION", "0") == "1"
                _lib_trigger_scan_async(_lib_build_scan_targets(), lang_sep)
            payload["media"] = _compute_media_stats()
        return jsonify(payload)
    @app.route("/api/media/ignore", methods=["POST"])
    def api_media_ignore():
        """Ignore missing slots (or whole series) in the Incomplete-series view.
        POST /api/media/ignore.

        Called from static/stats.js's `mediaIgnoreSelected()`."""
        data = request.get_json(silent=True) or {}
        items = data.get("items", [])
        if not isinstance(items, list) or not items:
            return jsonify({"error": "items required"}), 400
        for it in items:
            folder = str(it.get("folder", "")).strip()
            title = str(it.get("title", "")).strip()
            if it.get("all"):
                slots = ["__all__"]
            else:
                slots = [str(s).strip() for s in (it.get("slots") or []) if str(s).strip()]
            if folder and slots:
                add_media_ignores(folder, slots, title)
        return jsonify({"ok": True})
    @app.route("/api/media/unignore", methods=["POST"])
    def api_media_unignore():
        """Restore a previously ignored slot (or the whole series).
        POST /api/media/unignore.

        Called from static/stats.js's `mediaUnignore()`."""
        data = request.get_json(silent=True) or {}
        folder = str(data.get("folder", "")).strip()
        if not folder:
            return jsonify({"error": "folder required"}), 400
        if data.get("all"):
            remove_media_ignore(folder, all_slots=True)
        else:
            slot = str(data.get("slot", "")).strip()
            if not slot:
                return jsonify({"error": "slot required"}), 400
            remove_media_ignore(folder, slot=slot)
        return jsonify({"ok": True})
    @app.route("/api/stats/sync")
    def api_stats_sync():
        """Return sync stats plus the computed next scheduled run time.
        GET /api/stats/sync. No confirmed frontend caller was found in
        static/templates."""
        stats = get_sync_stats()
        # Compute next_run_at from last check + schedule interval
        schedule_key = os.environ.get("MEDIAFORGE_SYNC_SCHEDULE", "0")
        interval = SYNC_SCHEDULE_MAP.get(schedule_key, 0)
        stats["schedule"] = schedule_key
        stats["next_run_at"] = None
        if interval and stats.get("last_check"):
            from datetime import datetime, timedelta

            try:
                last = datetime.strptime(stats["last_check"], "%Y-%m-%d %H:%M:%S")
                nxt = last + timedelta(seconds=interval)
                stats["next_run_at"] = nxt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass
        return jsonify(stats)
    @app.route("/api/stats/queue")
    def api_stats_queue():
        """Return queue stats only. GET /api/stats/queue. No confirmed
        frontend caller was found in static/templates."""
        return jsonify(get_queue_stats())
    @app.route("/api/stats/general")
    def api_stats_general():
        """Return general stats only. GET /api/stats/general. No confirmed
        frontend caller was found in static/templates."""
        return jsonify(get_general_stats())
