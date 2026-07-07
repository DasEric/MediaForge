"""Route registration modules for the Flask web UI.

Empty on purpose: each ``register_xxx_routes(app)`` function (search,
queue, upscale, history, favourites, v1_api, captcha, progress, ...) is
imported directly by ``mediaforge.web.app.create_app()`` (e.g.
``from .routes.search import register_search_routes``) rather than through
this package's namespace, so no re-exports are needed here.
"""
