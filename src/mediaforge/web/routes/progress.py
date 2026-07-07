"""Watch-progress routes.

Extracted from create_app as a plain route-registration function
(no Flask blueprint: endpoint names stay bare so url_for() keeps working).
"""

from ..db import get_watch_progress
from ..db import get_watch_progress_bulk
from ..db import save_watch_progress
from flask import jsonify
from flask import request
from ..request_context import get_current_user_info as _get_current_user_info


def register_progress_routes(app):
    """Register the watch-progress save/get/bulk-get endpoints used by the player."""
    @app.route("/api/progress/save", methods=["POST"])
    def api_progress_save():
        """Save the current playback position for an episode.

        POST /api/progress/save. Called from player.js's _saveProgress().
        """
        data     = request.get_json(force=True, silent=True) or {}
        path     = data.get("path", "")
        position = float(data.get("position", 0) or 0)
        duration = float(data.get("duration", 0) or 0)
        if not path:
            return jsonify({"error": "path required"}), 400
        _user, _ = _get_current_user_info()
        save_watch_progress(path, position, duration, username=_user)
        return jsonify({"ok": True})
    @app.route("/api/progress/get")
    def api_progress_get():
        """Return the saved playback position for a single episode path.

        GET /api/progress/get. Called from app.js's streamEpisode() to
        resume playback from where the user left off.
        """
        path = request.args.get("path", "")
        if not path:
            return jsonify({"error": "path required"}), 400
        _user, _ = _get_current_user_info()
        return jsonify(get_watch_progress(path, username=_user))
    @app.route("/api/progress/bulk", methods=["POST"])
    def api_progress_bulk():
        """Return saved playback positions for multiple episode paths at once.

        POST /api/progress/bulk. Called from library.js's
        _libFlushProgress() to annotate the library listing with
        "continue watching" progress in one request.
        """
        data  = request.get_json(force=True, silent=True) or {}
        paths = data.get("paths", [])
        if not isinstance(paths, list):
            return jsonify({"error": "paths must be list"}), 400
        _user, _ = _get_current_user_info()
        return jsonify(get_watch_progress_bulk(paths, username=_user))
