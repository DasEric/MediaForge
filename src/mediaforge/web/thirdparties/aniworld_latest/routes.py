"""AniWorld Latest — Third Party integration (aniworld.to newest episodes).

Fully self-contained: its own Blueprint (own templates/ and static/ folders),
its own scraping service (service.py) and its own register(app) entry point
(see __init__.py). Mirrors the anime_seasons integration's layout.

Shows aniworld.to's "Die 50 neuesten Episoden" as a compact list. Clicking a
row opens the same cross-provider search modal Advanced Search uses
(openAniSearchModal, app.js), searching the *series* title. Each distinct
title is enriched with the same TMDB -> Crunchyroll -> Fernsehserien.de
provider pills the home page uses (enrichCardWithTmdb, app.js), so TMDB is
required (the CineInfo connection) and the others are optional fallbacks.
"""

from flask import Blueprint, jsonify, redirect, render_template, url_for

from ...db import get_setting
from ....logger import get_logger
from .service import get_latest_episodes

logger = get_logger(__name__)

SETTING_KEY = "aniworld_latest_enabled"
# Cache duration for the scraped list, in minutes (see extra_settings in
# __init__.py). Defaults to 60 -- "newest episodes" doesn't need to be live
# on every load, but shouldn't be a full day stale either.
CACHE_MINUTES_KEY = "aniworld_latest_cache_minutes"
# The provider pills need the existing CineInfo TMDB credential -- the same
# single coupling point Media Kalender uses (read-only, a plain app_settings
# key). No core file is modified; this only reads the setting to decide
# whether to show a "configure TMDB" banner.
TMDB_SETTING_KEY = "cineinfo_tmdb_api_key"

bp = Blueprint(
    "aniworld_latest",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/thirdparties/aniworld_latest/static",
)


def _enabled() -> bool:
    return get_setting(SETTING_KEY, "0") == "1"


def _tmdb_configured() -> bool:
    return bool((get_setting(TMDB_SETTING_KEY, "") or "").strip())


def _cache_ttl_seconds() -> int:
    raw = get_setting(CACHE_MINUTES_KEY, "60")
    try:
        minutes = int(str(raw).strip())
    except (TypeError, ValueError):
        minutes = 60
    if minutes < 1:
        minutes = 1
    return minutes * 60


@bp.route("/aniworld-latest")
def aniworld_latest_page():
    """Serve GET /aniworld-latest: the newest-episodes list, or redirect home
    if the integration is disabled in Settings -> Module Manager."""
    if not _enabled():
        return redirect(url_for("index"))
    return render_template(
        "aniworld_latest.html",
        tmdb_configured=_tmdb_configured(),
    )


@bp.route("/api/aniworld-latest")
def api_aniworld_latest():
    """Return the (cached) newest-episodes list. Route: GET
    /api/aniworld-latest. Called from static/aniworld_latest.js."""
    if not _enabled():
        return jsonify({"error": "disabled", "items": []}), 403
    items = get_latest_episodes(_cache_ttl_seconds())
    if items is None:
        return jsonify({"error": "fetch_failed", "items": []}), 502
    return jsonify({"items": items, "tmdb_configured": _tmdb_configured()})
