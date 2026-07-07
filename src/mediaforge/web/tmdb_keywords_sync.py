"""Background worker that syncs the daily TMDB keyword export.

Downloads TMDB's public daily keyword-ID export (a large gzip'd JSON file) so
that CineInfo's advanced search can resolve keyword names locally instead of
hitting the TMDB API for every search. Only runs when advanced search is
enabled in settings, and only re-downloads once per day.
"""

import threading
from datetime import timedelta

from ..config import MEDIAFORGE_CONFIG_DIR
from ..logger import get_logger

logger = get_logger(__name__)


_tmdb_keywords_worker_started = False


def _tmdb_keywords_sync_worker():
    """Background loop: check hourly whether today's TMDB keyword export
    needs downloading, and fetch it if so. Runs for the lifetime of the process."""
    import time
    import gzip
    import urllib.request
    from datetime import datetime

    while True:
        try:
            from .db import get_setting
            # Only run if advanced search is enabled in config
            if get_setting("cineinfo_advanced_search", "0") != "1":
                time.sleep(3600)
                continue

            yesterday_str = (datetime.utcnow() - timedelta(days=1)).strftime("%m_%d_%Y")
            url = f"https://files.tmdb.org/p/exports/keyword_ids_{yesterday_str}.json.gz"
            dest_file = MEDIAFORGE_CONFIG_DIR / "keyword_ids.json"

            download_needed = True
            if dest_file.exists():
                mtime = datetime.utcfromtimestamp(dest_file.stat().st_mtime)
                if mtime.date() == datetime.utcnow().date():
                    download_needed = False

            if download_needed:
                logger.info(f"Downloading TMDB keywords from {url}")
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                try:
                    with urllib.request.urlopen(req, timeout=30) as response:
                        with gzip.GzipFile(fileobj=response) as gz:
                            data = gz.read()
                            with open(dest_file, "wb") as f:
                                f.write(data)
                    logger.info("Successfully downloaded TMDB keywords.")
                except Exception as e:
                    logger.warning(f"Failed to download TMDB keywords: {e}")

        except Exception as e:
            logger.error(f"Error in TMDB keywords sync worker: {e}")

        time.sleep(3600)  # Check every hour


def _ensure_tmdb_keywords_sync_worker():
    """Start the background sync thread once (idempotent). Safe to call on
    every request/startup path that needs the keyword export available.

    Used by: app.py, called during create_app() startup.
    """
    global _tmdb_keywords_worker_started
    if _tmdb_keywords_worker_started:
        return
    _tmdb_keywords_worker_started = True
    thread = threading.Thread(target=_tmdb_keywords_sync_worker, daemon=True)
    thread.start()
