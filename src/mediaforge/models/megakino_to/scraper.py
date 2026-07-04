"""Shared scraping helpers for megakino9.com (DataLife Engine based site).

Everything megakino-specific that both the detail model classes and the
listing/search scrapers need lives here: HTTP fetching, URL helpers, listing
card parsing, DLE search and the hoster-embed extraction.
"""
import re
from html import unescape

try:
    from ...config import MEGAKINO_BASE_URL, logger
except ImportError:  # pragma: no cover - allow running as a script
    from mediaforge.config import MEGAKINO_BASE_URL, logger

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"

# Known stream hosters, mapped from a substring of their embed domain to the
# canonical provider name used by the extractors.
_HOSTER_DOMAINS = [
    ("voe.sx", "VOE"),
    ("voe.", "VOE"),
    ("vidmoly", "Vidmoly"),
    ("vidoza", "Vidoza"),
    ("veev", "VeeV"),
    ("filemoon", "Filemoon"),
    ("dood", "Doodstream"),
    ("streamtape", "Streamtape"),
    ("luluvdo", "Luluvdo"),
    ("loadx", "LoadX"),
    ("vidara", "Vidara"),
]


def base_url():
    return MEGAKINO_BASE_URL.rstrip("/")


def abs_url(path):
    """Turn a possibly protocol-relative / root-relative megakino path into an
    absolute URL on the configured base domain."""
    if not path:
        return path
    path = path.strip()
    if path.startswith("//"):
        return "https:" + path
    if path.startswith("http"):
        return path
    if path.startswith("/"):
        return base_url() + path
    return base_url() + "/" + path


# ---------------------------------------------------------------------------
# HTTP session with token handshake
# ---------------------------------------------------------------------------
# megakino gates every page behind a tiny JS shim that first calls
# /index.php?yg=token (which sets a `yg_token` cookie) and then reloads. We
# replicate that with a persistent session: do the handshake once, reuse the
# cookie, and transparently redo it if a response comes back as the challenge
# stub (e.g. after the cookie expires).
import threading as _threading

_HEADERS = {
    "User-Agent": _UA,
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

_session = None
_session_lock = _threading.Lock()


def _new_session():
    import requests as _req
    s = _req.Session()
    s.headers.update(_HEADERS)
    return s


def _handshake(s):
    try:
        s.get(base_url() + "/index.php?yg=token", timeout=10)
    except Exception as e:  # pragma: no cover - network best effort
        logger.debug("Megakino token handshake failed: %s", e)


def _get_session():
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                s = _new_session()
                _handshake(s)
                _session = s
    return _session


def reset_session():
    """Drop the cached session (e.g. if the base URL changed)."""
    global _session
    with _session_lock:
        _session = None


def _looks_like_challenge(text):
    if not text:
        return True
    if len(text) < 1200 and ("yg=token" in text or "location.replace" in text):
        return True
    return False


def _request(method, url, **kwargs):
    kwargs.setdefault("timeout", 20)
    s = _get_session()
    resp = s.request(method, url, **kwargs)
    if _looks_like_challenge(resp.text):
        _handshake(s)
        resp = s.request(method, url, **kwargs)
    resp.raise_for_status()
    return resp.text


def fetch_html(url, timeout=20):
    """Fetch a megakino page as text (through the token-gated session)."""
    return _request("GET", url, timeout=timeout)


def classify_hoster(url):
    """Return the canonical provider name for an embed URL, or None."""
    if not url:
        return None
    low = url.lower()
    for needle, name in _HOSTER_DOMAINS:
        if needle in low:
            return name
    return None


def _clean_text(s):
    return unescape(re.sub(r"\s+", " ", s or "").strip())


def is_series_path(url):
    return "/serials/" in (url or "")


def parse_cards(html):
    """Parse listing/search/carousel cards.

    megakino uses two card markups:
      * carousels / homepage widgets:  <a class="top ..." href=...>
            .top__title / .top__desc / img[data-src] / .poster__rating
      * category grids / search results: <a class="poster grid-item ..." href=...>
            .poster__title / .poster__subtitle / img[data-src] / .poster__label

    Returns a list of dicts: {title, url, poster_url, genre, rating, is_series}.
    """
    results = []
    seen = set()
    content_re = re.compile(r"/(?:films|serials|kinofilme|multfilm|documentary)/\d+-", re.IGNORECASE)

    for m in re.finditer(
        r'<a\b[^>]*class="([^"]*)"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        html,
        re.DOTALL | re.IGNORECASE,
    ):
        cls, href, inner = m.group(1), m.group(2), m.group(3)
        if "top" not in cls and "poster" not in cls:
            continue
        if not content_re.search(href):
            continue
        url = abs_url(href.split("#")[0])
        if url in seen:
            continue

        # Title (.top__title or .poster__title)
        tm = re.search(r'class="[^"]*(?:top__title|poster__title)[^"]*"[^>]*>(.*?)</',
                       inner, re.DOTALL | re.IGNORECASE)
        title = _clean_text(re.sub(r"<[^>]+>", "", tm.group(1))) if tm else ""
        if not title:
            continue

        # Poster: prefer data-src (lazy), skip the no-img placeholder in src
        poster = ""
        pm = re.search(r'<img\b[^>]*?data-src="([^"]+)"', inner, re.IGNORECASE)
        if pm:
            poster = pm.group(1)
        else:
            pm2 = re.search(r'<img\b[^>]*?\ssrc="([^"]+)"', inner, re.IGNORECASE)
            if pm2 and "no-img" not in pm2.group(1) and "data:image" not in pm2.group(1):
                poster = pm2.group(1)
        poster = abs_url(poster) if poster else ""

        # Genre / type line
        genre = ""
        gm = re.search(r'class="[^"]*top__desc[^"]*"[^>]*>(.*?)</div>', inner, re.DOTALL | re.IGNORECASE)
        if gm:
            genre = _clean_text(re.sub(r"<[^>]+>", " ", gm.group(1)))
        else:
            # .poster__subtitle: pick the <li> that looks like the genre line
            for li in re.findall(r'<li[^>]*>(.*?)</li>',
                                 _first([r'class="[^"]*poster__subtitle[^"]*"[^>]*>(.*?)</ul>'], inner) or "",
                                 re.DOTALL | re.IGNORECASE):
                txt = _clean_text(re.sub(r"<[^>]+>", " ", li))
                if "/" in txt or any(w in txt.lower() for w in ("serien", "filme")):
                    genre = txt
                    break

        # Rating (only carousel cards expose a numeric rating-N)
        rating = ""
        rm = re.search(r'poster__rating[^"]*rating-(\d+)[^"]*"[^>]*>\s*([\d.,]+)', inner, re.IGNORECASE)
        if rm:
            rating = rm.group(2).replace(",", ".")

        seen.add(url)
        results.append({
            "title": title,
            "url": url,
            "poster_url": poster,
            "genre": genre,
            "rating": rating,
            "is_series": is_series_path(url),
        })
    return results


def search(keyword):
    """Run a DLE search and return parsed cards."""
    try:
        text = _request(
            "POST",
            base_url() + "/index.php?do=search",
            data={
                "do": "search",
                "subaction": "search",
                "story": keyword,
                "search_start": "0",
                "full_search": "0",
                "result_from": "1",
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": base_url() + "/",
            },
            timeout=15,
        )
    except Exception as e:
        logger.warning("Megakino search failed: %s", e)
        return []
    return parse_cards(text)


def fetch_new_movies():
    try:
        html = fetch_html(base_url() + "/films/")
    except Exception as e:
        logger.warning("Megakino new-movies fetch failed: %s", e)
        return None
    return [c for c in parse_cards(html) if not c["is_series"]]


def fetch_new_series():
    try:
        html = fetch_html(base_url() + "/serials/")
    except Exception as e:
        logger.warning("Megakino new-series fetch failed: %s", e)
        return None
    return [c for c in parse_cards(html) if c["is_series"]]


def fetch_popular():
    """DLE built-in top module -> most-rated/most-viewed, mixed films + series."""
    try:
        html = fetch_html(base_url() + "/index.php?do=top")
    except Exception as e:
        logger.warning("Megakino popular fetch failed: %s", e)
        return None
    return parse_cards(html)


# ---------------------------------------------------------------------------
# Detail-page (single post) helpers
# ---------------------------------------------------------------------------

def extract_movie_hosters(html):
    """Return {provider_name: embed_url} for a movie post.

    The active hoster iframe is #film_main (data-src / src); additional hosters
    live in sibling .tabs-block__content iframes.  We simply collect every
    iframe embed in the player and classify it by domain.
    """
    hosters = {}
    # Restrict to the player block if we can find it, else scan whole page.
    player = html
    pm = re.search(r'class="pmovie__player.*', html, re.DOTALL)
    if pm:
        player = pm.group(0)
    for im in re.finditer(r'<iframe\b[^>]*?(?:data-src|src)="([^"]+)"', player, re.IGNORECASE):
        url = im.group(1)
        name = classify_hoster(url)
        if name and name not in hosters:
            hosters[name] = url
    # Fallback: a bare voe url anywhere in the player.
    if not hosters:
        vm = re.search(r'https?://[^"\']*voe[^"\']*/e/[a-z0-9]+', player, re.IGNORECASE)
        if vm:
            hosters["VOE"] = vm.group(0)
    return hosters


def extract_episode_hosters(html, episode_number):
    """Return {provider_name: embed_url} for one episode of a season post.

    Season posts embed a per-episode <select id="epN"> whose <option value>
    holds the hoster embed URL and whose text is the hoster label.
    """
    hosters = {}
    block = re.search(
        r'<select\b[^>]*\bid="ep%d"[^>]*>(.*?)</select>' % int(episode_number),
        html,
        re.DOTALL | re.IGNORECASE,
    )
    if not block:
        return hosters
    for om in re.finditer(
        r'<option\b[^>]*value="([^"]+)"[^>]*>(.*?)</option>',
        block.group(1),
        re.DOTALL | re.IGNORECASE,
    ):
        url = unescape(om.group(1).strip())
        label = _clean_text(re.sub(r"<[^>]+>", "", om.group(2)))
        name = classify_hoster(url) or (label.upper().replace(" ", "") and label.strip())
        if not name:
            continue
        # Normalise a few common labels to canonical extractor names
        norm = {"Voe": "VOE", "VOE": "VOE"}.get(name, name)
        if norm not in hosters:
            hosters[norm] = url
    return hosters


def count_episodes(html):
    """Number of episodes on a season post (count of #epN selects)."""
    nums = [int(n) for n in re.findall(r'<select\b[^>]*\bid="ep(\d+)"', html, re.IGNORECASE)]
    return max(nums) if nums else 0


def episode_titles(html):
    """Map episode number -> label from the main episode <select> (.se-select)."""
    titles = {}
    sel = re.search(r'<select\b[^>]*\bclass="[^"]*se-select[^"]*"[^>]*>(.*?)</select>', html, re.DOTALL | re.IGNORECASE)
    if not sel:
        return titles
    n = 0
    for om in re.finditer(r'<option\b[^>]*>(.*?)</option>', sel.group(1), re.DOTALL | re.IGNORECASE):
        n += 1
        titles[n] = _clean_text(re.sub(r"<[^>]+>", "", om.group(1)))
    return titles


def _first(patterns, html, flags=re.DOTALL | re.IGNORECASE):
    for pat in patterns:
        m = re.search(pat, html, flags)
        if m:
            return m.group(1)
    return None


def parse_meta(html):
    """Extract shared metadata from a movie or season post page."""
    title_raw = _first([r'<h1\b[^>]*>(.*?)</h1>'], html) or ""
    title = _clean_text(re.sub(r"<[^>]+>", "", title_raw))

    original = _first([r'class="[^"]*pmovie__original-title[^"]*"[^>]*>(.*?)</'], html)
    original = _clean_text(re.sub(r"<[^>]+>", "", original)) if original else ""

    year_raw = _first([
        r'itemprop="dateCreated"[^>]*>(.*?)</span>',
        r'class="[^"]*pmovie__year[^"]*"[^>]*>(.*?)</div>',
    ], html) or ""
    ym = re.search(r"\b(19|20)\d{2}\b", year_raw)
    year = ym.group(0) if ym else ""

    genres_raw = _first([r'class="[^"]*pmovie__genres[^"]*"[^>]*>(.*?)</div>'], html) or ""
    genres_txt = _clean_text(re.sub(r"<[^>]+>", " ", genres_raw))
    genres = [g.strip() for g in re.split(r"[/,]", genres_txt) if g.strip()]
    # Drop the leading media-type token ("Filme" / "Serien") if present
    if genres and genres[0].lower() in ("filme", "serien", "serie", "kinofilme",
                                        "dokumentationen", "documentary"):
        genres = genres[1:]

    desc = _first([
        r'itemprop="description"[^>]*>(.*?)</',
        r'class="[^"]*pmovie__text[^"]*"[^>]*>(.*?)</div>',
        r'class="[^"]*full-text[^"]*"[^>]*>(.*?)</div>',
    ], html) or ""
    description = _clean_text(re.sub(r"<[^>]+>", " ", desc))

    poster = _first([
        r'class="[^"]*pmovie__poster[^"]*"[^>]*>\s*<img\b[^>]*?(?:data-src|src)="([^"]+)"',
        r'<img\b[^>]*class="[^"]*(?:pmovie__poster|xfieldimage)[^"]*"[^>]*?(?:data-src|src)="([^"]+)"',
        r'<meta\b[^>]*property="og:image"[^>]*content="([^"]+)"',
    ], html)
    poster = abs_url(poster) if poster else ""

    imdb = _first([r'class="[^"]*pmovie__subrating--kp[^"]*"[^>]*>(.*?)</'], html)
    imdb = _clean_text(re.sub(r"<[^>]+>", "", imdb)) if imdb else ""

    return {
        "title": title,
        "original_title": original,
        "year": year,
        "genres": genres,
        "description": description,
        "poster_url": poster,
        "imdb_rating": imdb,
    }


def strip_season_suffix(title):
    """'Star City - 1 Staffel' / 'Silo - Staffel 3' -> 'Star City' / 'Silo'."""
    if not title:
        return title
    t = re.sub(r"\s*[-–]\s*\d+\.?\s*Staffel\b.*$", "", title, flags=re.IGNORECASE)
    t = re.sub(r"\s*[-–]\s*Staffel\s*\d+\b.*$", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*Staffel\s*\d+\b.*$", "", t, flags=re.IGNORECASE)
    return t.strip(" -–") or title.strip()


def parse_season_number(title, url=""):
    """Best-effort season number from a season-post title or its slug."""
    for pat in (r"(\d+)\.?\s*Staffel", r"Staffel\s*(\d+)"):
        m = re.search(pat, title or "", re.IGNORECASE)
        if m:
            return int(m.group(1))
    m = re.search(r"(\d+)-staffel", url or "", re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r"staffel-(\d+)", url or "", re.IGNORECASE)
    if m:
        return int(m.group(1))
    return 1
