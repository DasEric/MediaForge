"""AniWorld (aniworld.to) Series/Season/Episode model package.

AniWorld is the anime site: a series can have both numbered seasons
(``/staffel-N``) and a movie collection (``/filme``). See series.py for
how movies are detected (the ``has_movies`` flag + a dedicated season-like
``/filme`` entry) and episode.py for the per-episode ``is_movie`` flag
(true for ``/anime/stream/<slug>/filme/film-N`` URLs).
"""
from .episode import AniworldEpisode
from .season import AniworldSeason
from .series import AniworldSeries

__all__ = [
    "AniworldSeries",
    "AniworldSeason",
    "AniworldEpisode",
]
