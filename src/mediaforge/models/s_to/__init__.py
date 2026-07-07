"""Serienstream (s.to) Series/Season/Episode model package.

Structurally similar to AniWorld but simpler: no movie collection
(no `are_movies`/`has_movies`), and episodes have no `is_movie` or
`skip_times` (no AniSkip integration here). See episode.py for s.to's own
Audio/Subtitles enums, kept separate from mediaforge.config's because s.to
supports an English-audio-with-German-subtitles combination.
"""
from .episode import SerienstreamEpisode
from .season import SerienstreamSeason
from .series import SerienstreamSeries

__all__ = [
    "SerienstreamEpisode",
    "SerienstreamSeason",
    "SerienstreamSeries",
]
