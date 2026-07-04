"""hanime.tv extractor.

Unlike the other providers (which resolve a third-party video *hoster* embed),
hanime serves its own HLS streams.  ``get_direct_link_from_hanime`` turns a
hanime video/series URL into the best available ``.m3u8`` master playlist, and
``download_from_hanime`` grabs it with the shared concurrent yt-dlp helper.

Self-contained on purpose (mirrors extractors/provider/veev.py): it does its
own tiny API fetch so importing the extractor never pulls in the model layer.
"""
import re

try:
    from ...config import HANIME_API_BASE, HANIME_BASE_URL, logger
except ImportError:  # pragma: no cover
    from mediaforge.config import HANIME_API_BASE, HANIME_BASE_URL, logger

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": HANIME_BASE_URL + "/",
    "Origin": HANIME_BASE_URL,
}


def _slug(url):
    m = re.search(r"/videos/hentai/([a-zA-Z0-9._\-]+)", url or "")
    return m.group(1) if m else (url or "").strip()


def _best_stream_from_detail(detail):
    manifest = (detail or {}).get("videos_manifest") or {}
    best_url, best_h = "", -1
    for server in manifest.get("servers") or []:
        for st in server.get("streams") or []:
            url = st.get("url") or ""
            if not url:
                continue
            try:
                h = int(st.get("height") or 0)
            except (TypeError, ValueError):
                h = 0
            if h > best_h:
                best_h, best_url = h, url
    return best_url


def get_direct_link_from_hanime(url):
    """Return the HLS (.m3u8) URL for a hanime video URL.

    hanime signs every /api/v8 request since the Astro rewrite, so the stream
    is resolved through the signing headless browser (shared with the model
    scraper, which caches the result so we don't launch twice).
    """
    slug = _slug(url)
    if not slug:
        return None
    try:
        from ...models.hanime_tv import scraper
    except ImportError:
        from mediaforge.models.hanime_tv import scraper
    link = scraper.stream_for_slug(slug)
    # Fallback: if only the detail JSON was captured, derive the stream from it.
    if not link:
        detail = scraper.video_detail(slug)
        link = _best_stream_from_detail(detail or {})
    if not link:
        logger.warning("hanime get_direct_link found no stream for %s", slug)
    return link


def download_from_hanime(stream_url, output_path, cancel_event=None, label=""):
    """Download a hanime HLS stream to ``output_path`` (best quality)."""
    try:
        from ...models.common.common import _run_ytdlp_download
    except ImportError:
        from mediaforge.models.common.common import _run_ytdlp_download
    _run_ytdlp_download(
        stream_url,
        output_path,
        headers={"Referer": HANIME_BASE_URL + "/", "User-Agent": _HEADERS["User-Agent"]},
        label=label,
        cancel_event=cancel_event,
    )
    return True
