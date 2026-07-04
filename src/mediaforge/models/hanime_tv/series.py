"""hanime.tv series == a franchise, represented by one of its video slugs."""
import re

try:
    from ...config import HANIME_SERIES_PATTERN
    from . import scraper
    from .season import HanimeSeason
except ImportError:  # pragma: no cover
    from mediaforge.config import HANIME_SERIES_PATTERN
    from mediaforge.models.hanime_tv import scraper
    from mediaforge.models.hanime_tv.season import HanimeSeason


class HanimeSeries:
    def __init__(self, url=None):
        if not HANIME_SERIES_PATTERN.match(url or ""):
            raise ValueError(f"Invalid hanime series URL: {url}")
        self.url = url.rstrip("/")
        self._slug = scraper.slug_from_url(self.url)
        self.__detail = None
        self.__meta = None
        self.__seasons = None

    @property
    def _detail(self):
        if self.__detail is None:
            self.__detail = scraper.video_detail(self._slug) or {}
        return self.__detail

    @property
    def _meta(self):
        if self.__meta is None:
            self.__meta = scraper.parse_meta(self._detail)
        return self.__meta

    @property
    def title(self):
        return self._meta.get("title") or ""

    @property
    def title_cleaned(self):
        t = re.sub(r'[<>:"/\\|?*]', "", self.title or "").strip()
        return t or "Hentai"

    @property
    def release_year(self):
        return self._meta.get("year") or ""

    @property
    def imdb(self):
        return ""  # hanime content is not on IMDb

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
    def censored(self):
        return self._meta.get("censored") or ""

    @property
    def seasons(self):
        if self.__seasons is None:
            self.__seasons = [HanimeSeason(url=self.url, series=self, _detail=self._detail)]
        return self.__seasons
