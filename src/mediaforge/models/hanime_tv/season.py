"""hanime.tv season == the franchise's ordered episode list (single season)."""
try:
    from ...config import HANIME_SERIES_PATTERN
    from . import scraper
    from .episode import HanimeEpisode
except ImportError:  # pragma: no cover
    from mediaforge.config import HANIME_SERIES_PATTERN
    from mediaforge.models.hanime_tv import scraper
    from mediaforge.models.hanime_tv.episode import HanimeEpisode


class HanimeSeason:
    """A hanime franchise is modelled as exactly one season containing its
    ordered episode list (see scraper.franchise_episodes)."""

    # hanime has no movie concept. This is always False; it exists purely so
    # shared code paths that branch on `season.are_movies` (e.g. AniWorld/
    # MegaKino-style season handling in web/autosync_worker.py) don't need to
    # special-case hanime with a hasattr() check.
    are_movies = False

    def __init__(self, url=None, series=None, season_number=None, _detail=None):
        if not HANIME_SERIES_PATTERN.match(url or ""):
            raise ValueError(f"Invalid hanime season URL: {url}")
        self.url = url.rstrip("/")
        self._series = series
        self.__season_number = season_number or 1
        self.__detail = _detail
        self.__episodes = None

    @property
    def _detail(self):
        if self.__detail is None:
            self.__detail = scraper.video_detail(scraper.slug_from_url(self.url)) or {}
        return self.__detail

    @property
    def series(self):
        if self._series is None:
            from .series import HanimeSeries
            self._series = HanimeSeries(url=self.url)
        return self._series

    @property
    def season_number(self):
        return self.__season_number

    @property
    def episode_count(self):
        return len(self.episodes)

    @property
    def episodes(self):
        """Build HanimeEpisode objects for every video in the franchise,
        1-indexed in the order the site lists them."""
        if self.__episodes is None:
            eps_meta = scraper.franchise_episodes(self._detail)
            eps = []
            for n, meta in enumerate(eps_meta, start=1):
                ep = HanimeEpisode(
                    url=f"{self.url}?ep={n}",
                    series=self.series,
                    season=self,
                    episode_number=n,
                    episode_slug=meta.get("slug"),
                    title_de=meta.get("name") or f"Episode {n}",
                    censored=meta.get("censored") or "",
                )
                eps.append(ep)
            self.__episodes = eps
        return self.__episodes
