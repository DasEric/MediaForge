"""Favourites routes.

Extracted from create_app as a plain route-registration function
(no Flask blueprint: endpoint names stay bare so url_for() keeps working).
"""

from ..db import add_favourite
from ..db import get_favourites
from ..db import is_favourite
from ..db import remove_favourite
from flask import jsonify
from flask import render_template
from flask import request
from .. import runtime_state
from ..auth import get_current_user
from .image_proxy import _poster_proxy


def register_favourites_routes(app):
    """Register the favourites page and its add/remove/list/check API endpoints."""
    @app.route("/favourites")
    def favourites_page():
        """Render the favourites page shell (data is loaded client-side).

        GET /favourites.
        """
        return render_template("favourites.html")
    @app.route("/api/favourites")
    def api_get_favourites():
        """Return the current user's favourites (or all, when auth is disabled).

        GET /api/favourites. Called from favourites.js's loadFavourites().
        """
        username = None
        if runtime_state.AUTH_ENABLED:
            user = get_current_user()
            username = user.get("username") if user else None
        favs = get_favourites(added_by=username)
        # Proxy poster URLs so the client never hits source sites directly
        for f in favs:
            if f.get("poster_url") and not f["poster_url"].startswith("/api/img"):
                f["poster_url"] = _poster_proxy(f["poster_url"])
        return jsonify({"favourites": favs})
    @app.route("/api/favourites", methods=["POST"])
    def api_add_favourite():
        """Add a series/movie to the current user's favourites.

        POST /api/favourites. Called from app.js's toggleFavourite() and
        favourites.js when a poster is favourited.
        """
        data = request.get_json(silent=True) or {}
        series_url = (data.get("series_url") or "").strip()
        title = (data.get("title") or "").strip()
        raw_poster = (data.get("poster_url") or "").strip()
        # Unwrap proxy URLs so the DB always stores the original source URL
        if raw_poster.startswith("/api/img?url="):
            from urllib.parse import unquote as _unquote_fav
            raw_poster = _unquote_fav(raw_poster[len("/api/img?url="):])
        poster_url = raw_poster or None
        if not series_url or not title:
            return jsonify({"error": "series_url and title required"}), 400
        username = None
        if runtime_state.AUTH_ENABLED:
            user = get_current_user()
            username = user.get("username") if user else None
        add_favourite(series_url, title, poster_url, username)
        return jsonify({"ok": True})
    @app.route("/api/favourites", methods=["DELETE"])
    def api_remove_favourite():
        """Remove a series/movie from the current user's favourites.

        DELETE /api/favourites. Called from app.js's toggleFavourite() and
        favourites.js when a favourite is removed.
        """
        data = request.get_json(silent=True) or {}
        series_url = (data.get("series_url") or "").strip()
        if not series_url:
            return jsonify({"error": "series_url required"}), 400
        username = None
        if runtime_state.AUTH_ENABLED:
            user = get_current_user()
            username = user.get("username") if user else None
        remove_favourite(series_url, username)
        return jsonify({"ok": True})
    @app.route("/api/favourites/check")
    def api_check_favourite():
        """Return whether a given series/movie URL is already favourited.

        GET /api/favourites/check. Called from app.js's
        _updateFavouriteBtn() to set the initial favourite-button state.
        """
        series_url = request.args.get("series_url", "").strip()
        if not series_url:
            return jsonify({"is_favourite": False})
        username = None
        if runtime_state.AUTH_ENABLED:
            user = get_current_user()
            username = user.get("username") if user else None
        return jsonify({"is_favourite": is_favourite(series_url, username)})
