"""MegaKino series. On megakino a single post == one season, so a "series"
here is really one season post; ``seasons`` yields exactly that one season."""
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
    def __init__(self, url=None):
        if not MEGAKINO_SERIES_PATTERN.match(url or ""):
            raise ValueError(f"Invalid MegaKino series URL: {url}")
        self.url = url
        self.__meta = None
        self.__seasons = None
        self.__html = None

    @property
    def _html(self):
        if self.__html is None:
            self.__html = scraper.fetch_html(self.url)
        return self.__html

    @property
    def _meta(self):
        if self.__meta is None:
            self.__meta = scraper.parse_meta(self._html)
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
        # MegaKino does not expose an IMDb id (only a rating), so leave empty.
        return ""

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
            season = MegakinoSeason(url=self.url, series=self, _html=self._html)
            self.__seasons = [season]
        return self.__seasons
