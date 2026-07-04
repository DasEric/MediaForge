from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Pattern, Type
from urllib.parse import urlparse, urlunparse

import re as _re

from .config import (
    MEDIAFORGE_EPISODE_PATTERN,
    MEDIAFORGE_SEASON_PATTERN,
    MEDIAFORGE_SERIES_PATTERN,
    MEGAKINO_EPISODE_PATTERN,
    MEGAKINO_MOVIE_PATTERN,
    MEGAKINO_SERIES_PATTERN,
    SERIENSTREAM_EPISODE_PATTERN,
    SERIENSTREAM_SEASON_PATTERN,
    SERIENSTREAM_SERIES_PATTERN,
)
from .models import (
    AniworldEpisode,
    AniworldSeason,
    AniworldSeries,
    SerienstreamEpisode,
    SerienstreamSeason,
    SerienstreamSeries,
)
from .models.filmpalast_to.episode import FilmPalastEpisode
from .models.megakino_to.episode import MegakinoEpisode
from .models.megakino_to.movie import MegakinoMovie
from .models.megakino_to.season import MegakinoSeason
from .models.megakino_to.series import MegakinoSeries

# FilmPalast episode URLs: https://filmpalast.to/stream/<slug>
FILMPALAST_EPISODE_PATTERN = _re.compile(
    r"^https?://filmpalast\.to/stream/[a-zA-Z0-9\-]+/?$"
)


@dataclass(frozen=True)
class Provider:
    name: str
    series_pattern: Optional[Pattern[str]] = None
    season_pattern: Optional[Pattern[str]] = None
    episode_pattern: Optional[Pattern[str]] = None

    series_cls: Optional[Type] = None
    season_cls: Optional[Type] = None
    episode_cls: Optional[Type] = None


PROVIDERS = [
    Provider(
        name="AniWorld",
        series_pattern=MEDIAFORGE_SERIES_PATTERN,
        season_pattern=MEDIAFORGE_SEASON_PATTERN,
        episode_pattern=MEDIAFORGE_EPISODE_PATTERN,
        series_cls=AniworldSeries,
        season_cls=AniworldSeason,
        episode_cls=AniworldEpisode,
    ),
    Provider(
        name="SerienStream",
        series_pattern=SERIENSTREAM_SERIES_PATTERN,
        season_pattern=SERIENSTREAM_SEASON_PATTERN,
        episode_pattern=SERIENSTREAM_EPISODE_PATTERN,
        series_cls=SerienstreamSeries,
        season_cls=SerienstreamSeason,
        episode_cls=SerienstreamEpisode,
    ),
    # FilmPalast: movies only — no series/season structure.
    # The "episode" URL is the movie page itself.
    Provider(
        name="FilmPalast",
        episode_pattern=FILMPALAST_EPISODE_PATTERN,
        episode_cls=FilmPalastEpisode,
    ),
    # MegaKino series: one post == one season. Episode URLs are synthetic
    # (<post>.html?episode=N).
    Provider(
        name="Megakino",
        series_pattern=MEGAKINO_SERIES_PATTERN,
        season_pattern=MEGAKINO_SERIES_PATTERN,
        episode_pattern=MEGAKINO_EPISODE_PATTERN,
        series_cls=MegakinoSeries,
        season_cls=MegakinoSeason,
        episode_cls=MegakinoEpisode,
    ),
    # MegaKino movies: standalone films (the movie page is the "episode").
    Provider(
        name="MegakinoFilm",
        episode_pattern=MEGAKINO_MOVIE_PATTERN,
        episode_cls=MegakinoMovie,
    ),
]


def normalize_url(url: str) -> str:
    if not url:
        return url

    url = url.strip()

    parsed = urlparse(url)
    path = parsed.path

    # --- SerienStream alias handling ---
    # Some endpoints use /serie/stream/<slug>; normalize to /serie/<slug>.
    if path.startswith("/serie/stream/"):
        slug = path[len("/serie/stream/") :].strip("/")
        if slug:
            path = f"/serie/{slug}"

    # remove trailing slash
    path = path.rstrip("/")

    return urlunparse(parsed._replace(path=path))


def resolve_provider(url: str) -> Provider:
    url = normalize_url(url)

    for provider in PROVIDERS:
        if provider.series_pattern and provider.series_pattern.fullmatch(url):
            return provider
        if provider.season_pattern and provider.season_pattern.fullmatch(url):
            return provider
        if provider.episode_pattern and provider.episode_pattern.fullmatch(url):
            return provider

    raise ValueError(f"Unsupported URL: {url}")
