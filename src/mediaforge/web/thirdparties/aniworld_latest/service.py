"""AniWorld "Die 50 neuesten Episoden" scraping service.

Fetches aniworld.to's dedicated newest-episodes page
(https://aniworld.to/neue-episoden -- the page renders 150 rows; we keep the
first 50) and normalizes each row into the shape routes.py's API needs. The
home page ("/") is deliberately NOT used: it mixes in unrelated
Crunchyroll/carousel widgets whose rows have no date and titles formatted
like "<Series> St. 1 Ep. 3", which is exactly what we don't want.

Results are persisted in the shared ``provider_cache`` table (see ..db -- the
same generic cache Crunchyroll/Fernsehserien.de/Anime Seasons use) so a
restart doesn't lose the data and aniworld.to isn't hit on every page load.

Network access reuses MediaForge's existing, Cloudflare-tolerant
``GLOBAL_SESSION`` (mediaforge.config) -- the very same session the core
AniWorld models (models/aniworld_to/*) fetch series pages with. Nothing in
this module touches core code: it only *imports* GLOBAL_SESSION (read), the
shared provider cache (read/write, namespaced) and the logger.

--------------------------------------------------------------------------
Source markup (verified against a live https://aniworld.to/neue-episoden
capture), one entry per episode:

    <div class="newEpisodeList"><div class="rows">
      <div class="col-md-12"><div class="row"><div class="col-md-12">
        <a href="/anime/stream/<slug>/staffel-1/episode-1">
          <strong>KAMUI: He's Behind You</strong>
          <span class="listTag bigListTag blue2">S01 E01</span>
          <span class="elementFloatRight">Fr, 10.07.2026</span>
        </a>
        <img class="flag loaded" src="/public/img/japanese-german.svg" ...>
        <span class="listTag bigListTag green right">Neu!</span>
      </div></div></div>
      ...
    </div></div>

So per row: the clean series title is the <strong>, the S/E badge is the
".blue2" listTag, the date is ".elementFloatRight", the language flag is an
<img> whose src basename maps to one of MediaForge's local flags, and "Neu!"
is a ".green" listTag present only on the most recent rows. Movies use a
".../filme/film-<N>" href instead of staffel/episode.
"""

from __future__ import annotations

import re
import threading
import time
from urllib.parse import urljoin

from ....config import GLOBAL_SESSION
from ....logger import get_logger
from ...db import get_provider_cache, set_provider_cache

logger = get_logger(__name__)

_BASE_URL = "https://aniworld.to"
_LIST_URL = _BASE_URL + "/neue-episoden"
_NAMESPACE = "aniworld_latest"
_REQUEST_TIMEOUT = 20
_MAX_ROWS = 50

# Bump when _parse_row() output shape changes, so already-cached (now
# stale-shaped) entries are treated as a cache miss immediately.
_CACHE_SCHEMA_VERSION = 2
_CACHE_KEY = f"newest:v{_CACHE_SCHEMA_VERSION}"

# Episode links: /anime/stream/<slug>/staffel-<S>/episode-<E> or a movie
# /anime/stream/<slug>/filme/film-<N>. Group 1 = slug, 2/3 = season/episode,
# 4 = movie number (mutually exclusive with 2/3).
_EPISODE_HREF_RE = re.compile(
    r"/anime/stream/([^/\"'?#]+)/(?:staffel-(\d+)/episode-(\d+)|filme/film-(\d+))",
    re.IGNORECASE,
)

# AniWorld flag basenames -> MediaForge's local flags (web/static/flags/).
# AniWorld ships "<audio>-<sub>" combos (japanese-german = Japanese audio +
# German subtitle); MediaForge's local files carry a "Sub" suffix for the
# subtitle variants. Anything unmapped simply shows no flag rather than a
# broken image.
_FLAG_MAP = {
    "german": "german",
    "english": "english",
    "japanese-german": "japanese-germanSub",
    "japanese-english": "japanese-englishSub",
    "english-german": "english-germanSub",
}

# In-flight de-duplication so a cold cache doesn't fire several scrapes at
# once when multiple page loads race.
_refresh_lock = threading.Lock()
_refreshing = False


def _clean_title(text: str) -> str:
    """Collapse whitespace and strip surrounding punctuation."""
    text = re.sub(r"\s+", " ", (text or "").strip())
    return text.strip(" -–—·|")


def _strip_season_episode(title: str) -> str:
    """Remove a trailing season/episode suffix from a title so the search
    runs on the bare series name -- e.g. "The Villager of Level 999 St. 1
    Ep. 3" -> "The Villager of Level 999". Keyword-anchored (St./Staffel/Ep./
    Folge) so titles that merely contain numbers ("Level 999", "The 100
    Girlfriends...") are never touched."""
    t = title
    t = re.sub(r"\s+St\.?\s*\d+\s*Ep\.?\s*\d+\s*$", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s+Staffel\s*\d+\s*Folge\s*\d+\s*$", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s+(?:St\.?|Staffel)\s*\d+\s*$", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s+(?:Ep\.?|Folge)\s*\d+\s*$", "", t, flags=re.IGNORECASE)
    return _clean_title(t)


def _flag_from_src(src: str):
    """Map a flag <img> src to a canonical local flag name, or None."""
    if not src:
        return None
    base = src.rsplit("/", 1)[-1]
    base = re.sub(r"\.(svg|png|jpe?g|webp)$", "", base, flags=re.IGNORECASE)
    return _FLAG_MAP.get(base.lower())


def _parse_row(anchor, em) -> "dict | None":
    """Normalize one newest-episode row (its <a> element + siblings)."""
    slug = em.group(1)
    season = em.group(2)
    episode = em.group(3)
    movie = em.group(4)
    url = urljoin(_BASE_URL, em.group(0))

    # Clean series title from the <strong> inside the anchor.
    strong = anchor.find("strong")
    title = _clean_title(strong.get_text(" ", strip=True)) if strong else ""
    if not title:
        title = _clean_title(slug.replace("-", " ")).title()
    # Bare series name for search / provider enrichment (no St./Ep. suffix).
    title = _strip_season_episode(title)

    # S/E badge from the blue listTag; fall back to the URL.
    se_span = anchor.find("span", class_="blue2")
    se_label = _clean_title(se_span.get_text(" ", strip=True)) if se_span else ""
    if not se_label:
        if movie:
            se_label = f"Film {int(movie)}"
        elif season and episode:
            se_label = f"S{int(season):02d} E{int(episode):02d}"

    # Date from the right-floated span.
    date_span = anchor.find("span", class_="elementFloatRight")
    date_label = _clean_title(date_span.get_text(" ", strip=True)) if date_span else ""

    # The flag <img> and the "Neu!" tag are siblings of the anchor, inside
    # the same row container.
    row = anchor.parent
    languages = []
    is_new = False
    if row is not None:
        for img in row.find_all("img"):
            flag = _flag_from_src(img.get("src") or img.get("data-src") or "")
            if flag and flag not in languages:
                languages.append(flag)
        is_new = row.find("span", class_="green") is not None

    return {
        "title": title,
        "slug": slug,
        "url": url,
        "season": int(season) if season else None,
        "episode": int(episode) if episode else None,
        "is_movie": bool(movie),
        "se_label": se_label,
        "languages": languages,
        "is_new": is_new,
        "date_label": date_label,
    }


def _parse_newest_episodes(html: str) -> list:
    """Extract up to 50 rows from the ``.newEpisodeList`` block. Duplicates
    (same episode, different language) are intentionally kept 1:1."""
    try:
        from bs4 import BeautifulSoup
    except Exception as exc:  # pragma: no cover - bs4 is a hard dependency
        logger.error("[AniworldLatest] BeautifulSoup unavailable: %s", exc)
        return []

    soup = BeautifulSoup(html, "html.parser")
    container = soup.find(class_="newEpisodeList") or soup

    rows = []
    for a in container.find_all("a", href=True):
        em = _EPISODE_HREF_RE.search(a.get("href", ""))
        if not em:
            continue
        parsed = _parse_row(a, em)
        if parsed:
            rows.append(parsed)
        if len(rows) >= _MAX_ROWS:
            break
    return rows


def _fetch_latest() -> list:
    """Fetch + parse /neue-episoden. Best-effort: returns [] on any failure."""
    try:
        resp = GLOBAL_SESSION.get(_LIST_URL, timeout=_REQUEST_TIMEOUT)
        html = resp.text
    except Exception as exc:
        logger.warning("[AniworldLatest] Fetch failed: %s", exc)
        return []

    rows = _parse_newest_episodes(html)
    if not rows:
        logger.warning(
            "[AniworldLatest] Parsed 0 rows from %s (block missing or markup "
            "changed?). HTML length=%d", _LIST_URL, len(html or "")
        )
    return rows


def get_latest_episodes(ttl_seconds: int) -> "list | None":
    """Cached list of newest-episode dicts, or None if the cache is cold and
    the live fetch also failed. Never raises."""
    cached = get_provider_cache(_NAMESPACE, _CACHE_KEY, ttl=ttl_seconds)
    if cached is not None:
        return cached.get("items", [])

    global _refreshing
    with _refresh_lock:
        already = _refreshing
        if not already:
            _refreshing = True

    if already:
        # Another request is already fetching -- wait briefly for its result
        # instead of firing a second scrape.
        for _ in range(20):
            time.sleep(0.5)
            cached = get_provider_cache(_NAMESPACE, _CACHE_KEY, ttl=ttl_seconds)
            if cached is not None:
                return cached.get("items", [])
        return None

    try:
        items = _fetch_latest()
        if items:
            set_provider_cache(_NAMESPACE, _CACHE_KEY, {"items": items})
        return items or None
    finally:
        with _refresh_lock:
            _refreshing = False
