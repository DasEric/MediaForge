"""HLS passthrough proxy for stream-from-source.

Instead of re-muxing/transcoding a provider stream through ffmpeg (which causes
video stutter on variable-frame-rate feeds), this proxies the provider's own
HLS playlists and segments through our server, adding only the required HTTP
headers (Referer / User-Agent). The browser then plays the provider's native
HLS exactly as the website does — no re-encode, no timestamp tampering, no CPU.

Flow:
  * ``create_proxy_session(headers)`` stores the provider headers under a token.
  * The browser loads ``/api/proxy/<token>/r/<b64(playlist_url)>``.
  * Playlists are fetched server-side and every child URI (variants, segments,
    EXT-X-KEY / EXT-X-MAP / EXT-X-MEDIA) is rewritten to point back at the proxy
    with the resolved absolute URL. Non-playlist resources (segments, keys) are
    streamed through verbatim, forwarding Range requests.

Security: only http/https is allowed and hosts resolving to private/loopback
addresses are rejected (SSRF guard).
"""

import base64
import ipaddress
import re
import socket
import threading
import time
import uuid
import urllib.request
from urllib.parse import urljoin, urlsplit

try:
    from ..logger import get_logger
    logger = get_logger(__name__)
except Exception:
    import logging
    logger = logging.getLogger(__name__)

_SESSION_TIMEOUT = 3600  # 1 h
_URI_ATTR_RE = re.compile(r'URI="([^"]*)"')

_sessions: dict = {}
_lock = threading.Lock()


# ── Session registry ─────────────────────────────────────────────────────────────────────
# In-memory token -> {headers, last-access} map. Tokens are short-lived and
# tied to a single playback session; they let the proxy route (routes/stream.py)
# re-attach the provider's Referer/User-Agent to every playlist/segment
# request without exposing those headers to the browser.

def create_proxy_session(headers: dict | None) -> str:
    """Create a new proxy session for the given provider headers and return its token.

    Used by: routes/stream.py when starting a stream-from-source playback.
    """
    _reap()
    token = uuid.uuid4().hex
    with _lock:
        _sessions[token] = {"headers": dict(headers or {}), "last": time.time()}
    return token


def get_proxy_session(token: str) -> dict | None:
    """Look up a session by token, refreshing its last-access time (keeps it alive)."""
    with _lock:
        s = _sessions.get(token)
        if s:
            s["last"] = time.time()
    return s


def close_proxy_session(token: str):
    """Explicitly drop a session, e.g. when playback ends."""
    with _lock:
        _sessions.pop(token, None)


def _reap():
    """Evict sessions that haven't been accessed within _SESSION_TIMEOUT."""
    now = time.time()
    with _lock:
        for t in [t for t, s in _sessions.items() if now - s["last"] > _SESSION_TIMEOUT]:
            _sessions.pop(t, None)


# ── URL (de)serialisation ─────────────────────────────────────────────────────────────────
# Absolute child URLs are embedded in the proxy path as unpadded urlsafe-base64
# so they survive being placed in a URL segment without extra escaping.

def b64e(url: str) -> str:
    """Encode a URL for embedding in a proxy path segment."""
    return base64.urlsafe_b64encode(url.encode("utf-8")).decode("ascii").rstrip("=")


def b64d(s: str) -> str:
    """Decode a URL previously encoded with :func:`b64e` (re-adds stripped padding)."""
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad).decode("utf-8")


# ── SSRF guard ────────────────────────────────────────────────────────────────────

def is_safe_url(url: str) -> bool:
    """Reject non-http(s) schemes and hosts resolving to private/loopback/link-local
    addresses, so the proxy can't be used to reach internal network services."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return False
    host = parts.hostname
    if not host:
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:
        return False
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_multicast or ip.is_reserved or ip.is_unspecified):
            return False
    return True


# ── Fetching ────────────────────────────────────────────────────────────────────────

def fetch(url: str, headers: dict, range_header: str | None = None) -> tuple:
    """Fetch a URL with the provider headers. Returns (code, headers, data, final_url)."""
    req = urllib.request.Request(url)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    # Avoid compressed responses so playlists parse and segments pass through raw.
    req.add_header("Accept-Encoding", "identity")
    if range_header:
        req.add_header("Range", range_header)
    resp = urllib.request.urlopen(req, timeout=30)
    data = resp.read()
    return resp.getcode(), dict(resp.headers), data, resp.geturl()


def is_playlist(data: bytes) -> bool:
    return data[:7] == b"#EXTM3U"


# ── Playlist rewriting ─────────────────────────────────────────────────────────

def rewrite_playlist(text: str, playlist_url: str, proxy_base: str) -> str:
    """Rewrite all child URIs in an HLS playlist to go through the proxy.

    ``proxy_base`` ends with ``/`` (e.g. ``/api/proxy/<token>/r/``). Relative
    URIs are resolved against ``playlist_url`` (the playlist's own final URL).
    """
    out = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            out.append(line)
            continue
        if stripped.startswith("#"):
            # Rewrite URI="…" attributes (EXT-X-KEY, EXT-X-MAP, EXT-X-MEDIA, …).
            m = _URI_ATTR_RE.search(line)
            if m:
                child_abs = urljoin(playlist_url, m.group(1))
                line = line[:m.start(1)] + proxy_base + b64e(child_abs) + line[m.end(1):]
            out.append(line)
        else:
            # A media/segment/variant URI line.
            child_abs = urljoin(playlist_url, stripped)
            out.append(proxy_base + b64e(child_abs))
    return "\n".join(out)
