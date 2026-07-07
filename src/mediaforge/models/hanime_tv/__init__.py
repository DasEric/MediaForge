"""hanime.tv (adult / 18+) model package.

hanime has no movie concept (every title is a "video") and each series is a
single-season franchise (see season.py); there is no per-episode `is_movie`
or `skip_times` here, unlike AniWorld. Actual network/scraping logic lives
in scraper.py (unsigned search/listing API) and browser.py (headless-browser
access for the signed per-video API + HLS stream).
"""
from .episode import HanimeEpisode
from .season import HanimeSeason
from .series import HanimeSeries

__all__ = ["HanimeSeries", "HanimeSeason", "HanimeEpisode"]
