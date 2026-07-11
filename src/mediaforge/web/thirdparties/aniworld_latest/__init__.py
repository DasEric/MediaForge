"""AniWorld Latest — registration entry point.

This is the file web/thirdparties/__init__.py's auto-discovery loader
imports: it must expose a ``register(app)`` callable, which is the only
contract a thirdparties/<name>/ folder needs to fulfil to be picked up
automatically (see the parent package's docstring). Everything this
integration needs -- its scraping service (service.py), routes/templates/
static and translations -- lives inside this one folder; nothing outside it
is modified.
"""

from .routes import bp, SETTING_KEY
from ..registry import register_thirdparty

# MODULE_* constants the admin Modulmanager page (/extensions) reads off
# every thirdparty's __init__.py. Purely descriptive except
# MODULE_ENABLED_DEFAULT, which only applies the first time this module is
# discovered.
MODULE_NAME = "AniWorld Latest"
MODULE_DESCRIPTION = "The 50 newest episodes from aniworld.to as a compact list; clicking a row opens the cross-provider search modal for the series title, enriched with the same TMDB/Crunchyroll/Fernsehserien.de provider pills as the home page."
MODULE_DESCRIPTION_DE = "Die 50 neuesten Episoden von aniworld.to als kompakte Liste; ein Klick öffnet die Anbieter-übergreifende Suche für den Serientitel, angereichert mit den gleichen TMDB-/Crunchyroll-/Fernsehserien.de-Anbieter-Badges wie die Startseite."
MODULE_AUTHOR = "PD Codes"
MODULE_VERSION = "1.0.0"
MODULE_API_VERSION = 1
MODULE_ENABLED_DEFAULT = False

# "New / lightning" style icon, same stroke-based style as the other sidebar
# icons in base.html.
_ICON_SVG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round">'
    '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>'
    '</svg>'
)


def register(app) -> None:
    """Called once by web/thirdparties/discover_and_register(app)."""
    app.register_blueprint(bp)

    register_thirdparty(
        item_id="aniworld_latest",
        label="AniWorld Latest",
        endpoint="aniworld_latest.aniworld_latest_page",
        icon_svg=_ICON_SVG,
        enabled_setting_key=SETTING_KEY,
        section="discover",
        badges=[("AniWorld", "#ff9800"), ("TMDB", "#01b4e4"), ("Menu", "#7c3aed")],
        description=(
            "Fetches aniworld.to's \"Die 50 neuesten Episoden\" and shows them "
            "as a compact list. Clicking a row opens the cross-provider search "
            "modal (AniWorld/S.to/FilmPalast/MegaKino) for the series title, "
            "just like Advanced Search. Each title is enriched with the same "
            "CineInfo (TMDB) / Crunchyroll / Fernsehserien.de pills as the home "
            "page -- requires a TMDB API key under Settings -> Integrations -> "
            "CineInfo for the TMDB pill."
        ),
        enable_label="Enable AniWorld Latest",
        enable_desc=(
            'Adds an "AniWorld Latest" entry under Discover in the sidebar. '
            "Provider pills need a configured CineInfo TMDB key; without one, "
            "the list still works but shows a notice and only the "
            "Crunchyroll/Fernsehserien.de fallback pills."
        ),
        extra_settings=[
            {
                "key": "aniworld_latest_cache_minutes",
                "label": "Cache duration (minutes)",
                "description": "How long the scraped list is cached before being refreshed from aniworld.to.",
                "type": "number",
                "default": "60",
            },
        ],
    )
