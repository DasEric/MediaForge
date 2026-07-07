"""MegaKino (megakino.to) model package.

Movies and series episodes share the same /watch/<slug>/<id> URL family and
are told apart purely by a query param: ``?episode=N`` means a series
episode (MegakinoEpisode); the bare URL means a movie (MegakinoMovie). These
are two independent classes -- MegakinoEpisode is NOT a subclass of
MegakinoMovie -- so callers distinguish them with e.g.
``isinstance(ep, MegakinoMovie)`` (see web/routes/search.py) rather than an
`is_movie` attribute. One /watch post equals one season (no separate
MegakinoSeries with multiple seasons); see series.py/season.py.
"""
from .episode import MegakinoEpisode
from .movie import MegakinoMovie
from .season import MegakinoSeason
from .series import MegakinoSeries

__all__ = ["MegakinoSeries", "MegakinoSeason", "MegakinoEpisode", "MegakinoMovie"]
