"""hanime.tv extractor.

Unlike the other providers (which resolve a third-party video *hoster* embed),
hanime serves its own HLS streams.  ``get_direct_link_from_hanime`` turns a
hanime video/series URL into the best available ``.m3u8`` master playlist, and
``download_from_hanime`` grabs it with the shared concurrent yt-dlp helper.

Self-contained on purpose (mirrors extractors/provider/veev.py): it does its
own tiny API fetch so importing the extractor never pulls in the model layer.

Used by: models/hanime_tv/episode.py, which imports
get_direct_link_from_hanime and download_from_hanime directly (this
provider is not dispatched through extractors.provider_functions like the
other hosters, since hanime is the site's own player rather than a
third-party embed).
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
    """Extract the hanime video slug from a full video URL, if present.

    Falls back to returning the (stripped) input unchanged, so this also
    accepts a bare slug directly.
    """
    m = re.search(r"/videos/hentai/([a-zA-Z0-9._\-]+)", url or "")
    return m.group(1) if m else (url or "").strip()


def _best_stream_from_detail(detail):
    """Pick the highest-resolution HLS stream URL out of a video-detail JSON blob.

    Walks every server's stream list in ``videos_manifest`` and keeps the
    one with the largest ``height`` value.
    """
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
    """Download a hanime HLS stream to ``output_path``.

    hanime streams are AES-128 encrypted HLS with ``.html``-disguised segments
    and the key on ``sign.bin``.  yt-dlp (without pycryptodomex) delegates that
    to a *verbose* internal ffmpeg -> console spam + no progress.  Instead we run
    ONE ffmpeg pass ourselves via ``_run_ffmpeg_with_progress`` (ffmpeg decrypts
    AES-128 natively): stderr is piped/parsed (no spam) and the known manifest
    duration yields a real progress bar, consistent with the other providers.
    """
    import os
    from pathlib import Path
    import ffmpeg
    try:
        from ...models.common import common as C
    except ImportError:
        from mediaforge.models.common import common as C

    output_path = Path(output_path)
    os.makedirs(C._MEDIAFORGE_TEMP_DIR, exist_ok=True)
    tmp = C._MEDIAFORGE_TEMP_DIR / f"{output_path.stem}.hanime.mkv"

    in_opts = {
        "headers": f"Referer: {HANIME_BASE_URL}/\r\n",
        "user_agent": _HEADERS["User-Agent"],
        # segments are served as .html and the key/segments use crypto+https
        "allowed_extensions": "ALL",
        "protocol_whitelist": "file,http,https,tcp,tls,crypto,httpproxy,data",
        "reconnect": 1,
        "reconnect_streamed": 1,
        "reconnect_delay_max": 30,
    }
    vcodec, acodec, vopts, gargs = C._get_ffmpeg_codec_opts()
    node = ffmpeg.input(stream_url, **in_opts).output(
        str(tmp), vcodec=vcodec, acodec=acodec, **vopts
    )
    if gargs:
        node = node.global_args(*gargs)
    # This single pass IS the download (segments fetched + AES-decrypted),
    # so report it as the Download phase rather than 'FFmpeg'.
    C._run_ffmpeg_with_progress(node, label=label, cancel_event=cancel_event, phase="download")

    os.makedirs(output_path.parent, exist_ok=True)
    C._move_with_progress(tmp, output_path, label=label, cancel_event=cancel_event)
    return True
