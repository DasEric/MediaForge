"""MegaKino series (megakino.to, tv=1). One /watch post == one season."""
import re

try:
    from ...config import MEGAKINO_SERIES_PATTERN
    from . import scraper
    from .season import MegakinoSeason
except ImportError:  # pragma: no cover
    from mediaforge.config import MEGAKINO_SERIES_PATTERN
    from mediaforge.models.megakino_to import scraper
    from mediaforge.models.megakino_to.season import MegakinoSeason


class MegakinoSeries:
    def __init__(self, url=None, _data=None):
        if not MEGAKINO_SERIES_PATTERN.match(url or ""):
            raise ValueError(f"Invalid MegaKino series URL: {url}")
        self.url = url
        self.__data = _data
        self.__meta = None
        self.__seasons = None

    @property
    def _data(self):
        if self.__data is None:
            self.__data = scraper.fetch_watch(self.url)
        return self.__data

    @property
    def _meta(self):
        if self.__meta is None:
            self.__meta = scraper.parse_meta(self._data)
        return self.__meta

    @property
    def title(self):
        return scraper.strip_season_suffix(self._meta.get("title") or "")

    @property
    def title_cleaned(self):
        t = re.sub(r'[<>:"/\\|?*]', "", self.title or "").strip()
        return t or "Serie"

    @property
    def release_year(self):
        return self._meta.get("year") or ""

    @property
    def imdb(self):
        return self._meta.get("imdb_id") or ""

    @property
    def poster_url(self):
        return self._meta.get("poster_url") or ""

    @property
    def description(self):
        return self._meta.get("description") or ""

    @property
    def genres(self):
        return self._meta.get("genres") or []

    @property
    def seasons(self):
        if self.__seasons is None:
            self.__seasons = [MegakinoSeason(url=self.url, series=self, _data=self._data)]
        return self.__seasons
