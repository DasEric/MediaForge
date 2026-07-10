"""Dev Infos routes -- a changelog/status feed pulled from a fixed,
unauthenticated admin server (a separate standalone app, unrelated to this
codebase) and cached locally.

The feed source (devinfos_monitor.DEVINFOS_SERVER_URL) is a hardcoded source
constant -- not admin-configurable -- so there is intentionally no settings
API here, only read-only display routes.

Extracted as a plain route-registration function (no Flask blueprint:
endpoint names stay bare so url_for() keeps working), matching every other
first-party feature module under web/routes/.
"""

from ..db import get_devinfo_count
from ..db import get_devinfo_posts
from ..devinfos_monitor import request_immediate_refresh
from ..markdown_utils import render_markdown
from flask import jsonify
from flask import render_template


def _posts_with_rendered_html():
    """Return cached Dev Info posts with an extra ``body_html`` key holding
    the sanitized Markdown-rendered HTML for ``body``, alongside the
    original raw ``body`` (kept as-is for any consumer that wants the raw
    source)."""
    return [
        {**post, "body_html": render_markdown(post.get("body"))}
        for post in get_devinfo_posts()
    ]


def register_devinfos_routes(app):
    """Register the Dev Infos page and its supporting status API on the
    given Flask app."""

    @app.route("/devinfos")
    def devinfos_page():
        """Dev Infos changelog/status feed -- visible to any logged-in user
        (or anyone if auth is disabled), same visibility level as other
        regular content pages. Not admin-gated.

        Route: GET /devinfos.
        """
        # Kick the poller so newly published posts show up without waiting
        # for the next scheduled 5-minute round -- rate-limited internally so
        # repeated visits/clicks cannot hammer the remote server.
        request_immediate_refresh()
        return render_template("devinfos.html", posts=_posts_with_rendered_html())

    @app.route("/api/devinfos/status")
    def api_devinfos_status():
        """Cached Dev Info post count + posts, for the sidebar badge poll
        (static/devinfos.js) and the page's own live refresh.

        Route: GET /api/devinfos/status.
        """
        return jsonify({
            "count": get_devinfo_count(),
            "posts": _posts_with_rendered_html(),
        })
