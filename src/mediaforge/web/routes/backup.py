"""Full & Selective Backup routes (admin only).

Exposes the export/preview/import endpoints backing the "Backup" settings tab.
Every endpoint is gated on the current request being an admin (auth disabled =>
treated as admin, matching the rest of the settings API).

Extracted as a plain route-registration function (no Flask blueprint: endpoint
names stay bare so url_for() keeps working).
"""

import io

from flask import jsonify
from flask import request
from flask import send_file

from .. import backup as _backup
from ..backup import BackupError
from ..request_context import get_current_user_info as _get_current_user_info
from ...logger import get_logger

logger = get_logger(__name__)


def _require_admin():
    """Return an error response tuple if the caller is not an admin, else None."""
    _user, is_admin = _get_current_user_info()
    if not is_admin:
        return jsonify({"error": "admin access required"}), 403
    return None


def register_backup_routes(app):
    """Register the /api/backup/* endpoints on *app*."""

    @app.route("/api/backup/categories", methods=["GET"])
    def api_backup_categories():
        """List available backup categories with current row counts."""
        denied = _require_admin()
        if denied:
            return denied
        return jsonify({"categories": _backup.list_categories()})

    @app.route("/api/backup/export", methods=["POST"])
    def api_backup_export():
        """Create a backup and return it as a downloadable .mfbackup file."""
        denied = _require_admin()
        if denied:
            return denied
        payload = request.get_json(silent=True) or {}
        categories = payload.get("categories") or []
        password = payload.get("password") or ""
        if not password:
            return jsonify({"error": "password required"}), 400
        try:
            blob = _backup.export_backup(categories, password)
        except BackupError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception:
            logger.exception("Backup export failed")
            return jsonify({"error": "export failed"}), 500

        import time
        filename = f"mediaforge-backup-{time.strftime('%Y%m%d-%H%M%S')}.mfbackup"
        return send_file(
            io.BytesIO(blob),
            mimetype="application/json",
            as_attachment=True,
            download_name=filename,
        )

    @app.route("/api/backup/preview", methods=["POST"])
    def api_backup_preview():
        """Inspect an uploaded backup file without importing anything."""
        denied = _require_admin()
        if denied:
            return denied
        file = request.files.get("file")
        if file is None:
            return jsonify({"error": "no file uploaded"}), 400
        password = request.form.get("password", "")
        try:
            info = _backup.preview_backup(file.read(), password)
        except BackupError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception:
            logger.exception("Backup preview failed")
            return jsonify({"error": "could not read backup"}), 500
        return jsonify(info)

    @app.route("/api/backup/import", methods=["POST"])
    def api_backup_import():
        """Restore selected categories from an uploaded backup file."""
        denied = _require_admin()
        if denied:
            return denied
        file = request.files.get("file")
        if file is None:
            return jsonify({"error": "no file uploaded"}), 400
        password = request.form.get("password", "")
        if not password:
            return jsonify({"error": "password required"}), 400
        mode = request.form.get("mode", "merge")
        categories = [c for c in request.form.get("categories", "").split(",") if c]
        try:
            report = _backup.import_backup(file.read(), password, categories, mode)
        except BackupError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception:
            logger.exception("Backup import failed")
            return jsonify({"error": "import failed"}), 500
        return jsonify({"ok": True, "imported": report})
