"""
VIDARA (vidara.to) stream extractor.

The VIDARA embed page makes a POST request to /api/stream with the filecode
extracted from the URL path (e.g. https://vidara.to/e/{filecode}).
The response JSON contains a `streaming_url` field with the direct HLS URL.
"""
import logging
import re

import niquests

logger = logging.getLogger(__name__)

try:
    from ...config import DEFAULT_USER_AGENT
except ImportError:
    from mediaforge.config import DEFAULT_USER_AGENT

VIDARA_DOMAINS = {"vidara.to"}


def _extract_filecode(url: str) -> str:
    """Extract the filecode from a VIDARA embed URL.

    Accepts:
      https://vidara.to/e/<filecode>
      https://vidara.to/v/<filecode>
    """
    match = re.search(r"/(?:e|v)/([A-Za-z0-9_\-]+)", url)
    if not match:
        raise ValueError(f"Cannot extract filecode from VIDARA URL: {url}")
    return match.group(1)


def get_direct_link_from_vidara(embed_url: str, headers=None, timeout: int = 20) -> str:
    """Return the direct HLS stream URL from a VIDARA embed link.

    Args:
        embed_url: A VIDARA embed URL such as https://vidara.to/e/fMxYhG3HN5mUn
        headers:   Optional request headers (defaults applied if None).
        timeout:   Request timeout in seconds.

    Returns:
        Direct HLS/MP4 stream URL string.

    Raises:
        ValueError: If extraction fails for any reason.
    """
    filecode = _extract_filecode(embed_url)

    req_headers = {
        "User-Agent": headers.get("User-Agent", DEFAULT_USER_AGENT) if headers else DEFAULT_USER_AGENT,
        "Referer": embed_url,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    api_url = "https://vidara.to/api/stream"
    payload = {"filecode": filecode, "device": "web"}

    try:
        resp = niquests.post(api_url, json=payload, headers=req_headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        raise ValueError(f"VIDARA API request failed for {embed_url}: {exc}") from exc

    streaming_url = data.get("streaming_url") or data.get("file") or data.get("url")
    if not streaming_url:
        raise ValueError(
            f"No streaming_url in VIDARA API response for {embed_url}. "
            f"Response: {str(data)[:200]}"
        )

    logger.debug("VIDARA stream URL extracted: %s…", streaming_url[:60])
    return streaming_url


if __name__ == "__main__":
    url = input("Enter VIDARA embed URL: ").strip()
    print("Stream URL:", get_direct_link_from_vidara(url))
