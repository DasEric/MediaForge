"""MegaKino season == one megakino post."""
try:
    from ...config import MEGAKINO_SERIES_PATTERN
    from . import scraper
    from .episode import MegakinoEpisode
except ImportError:  # pragma: no cover
    from mediaforge.config import MEGAKINO_SERIES_PATTERN
    from mediaforge.models.megakino_to import scraper
    from mediaforge.models.megakino_to.episode import MegakinoEpisode


class MegakinoSeason:
    are_movies = False

    def __init__(self, url=None, series=None, season_number=None, _html=None):
        if not MEGAKINO_SERIES_PATTERN.match(url or ""):
            raise ValueError(f"Invalid MegaKino season URL: {url}")
        self.url = url
        self._series = series
        self.__season_number = season_number
        self.__html = _html
        self.__episodes = None
        self.__episode_count = None

    @property
    def _html(self):
        if self.__html is None:
            self.__html = scraper.fetch_html(self.url)
        return self.__html

    @property
    def series(self):
        if self._series is None:
            from .series import MegakinoSeries
            self._series = MegakinoSeries(url=self.url)
        return self._series

    @property
    def season_number(self):
        if self.__season_number is None:
            title = ""
            try:
                title = scraper.parse_meta(self._html).get("title") or ""
            except Exception:
                pass
            self.__season_number = scraper.parse_season_number(title, self.url)
        return self.__season_number

    @property
    def episode_count(self):
        if self.__episode_count is None:
            self.__episode_count = scraper.count_episodes(self._html)
        return self.__episode_count

    @property
    def episodes(self):
        if self.__episodes is None:
            html = self._html
            titles = scraper.episode_titles(html)
            count = scraper.count_episodes(html)
            eps = []
            for n in range(1, count + 1):
                hosters = scraper.extract_episode_hosters(html, n)
                ep = MegakinoEpisode(
                    url=f"{self.url}?episode={n}",
                    series=self.series,
                    season=self,
                    episode_number=n,
                    title_de=titles.get(n, f"Episode {n}"),
                    provider_data={"German Dub": hosters} if hosters else {},
                )
                eps.append(ep)
            self.__episodes = eps
        return self.__episodes
