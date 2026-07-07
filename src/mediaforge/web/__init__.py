"""Flask web UI package: app factory, route registration, and the small
per-feature helper/worker modules used by the routes under web/routes/."""
from .app import start_web_ui

__all__ = ["start_web_ui"]
