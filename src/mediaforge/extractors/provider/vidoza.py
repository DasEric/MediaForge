"""Vidoza (videzz.net and other Vidoza mirrors) video hoster extractor.

Strategy: fetch the embed page HTML and, when it contains a "sourcesCode:"
JW-Player config block, regex out the plain-text ``src: "..."`` video URL
(and, separately, the ``poster: "..."`` thumbnail URL for previews). No
JS deobfuscation is required -- the URLs are inline, unobfuscated strings.

Used by: dispatched generically via extractors.provider_functions (key
"get_direct_link_from_vidoza"); see the provider alias table in
models/megakino_to/scraper.py (("vidoza", "Vidoza")) and the generic
provider dispatch in models/megakino_to/{episode,movie}.py.
"""
import re

import niquests

try:
    from ...config import DEFAULT_USER_AGENT, GLOBAL_SESSION, is_source_unavailable
except ImportError:
    from mediaforge.config import DEFAULT_USER_AGENT, GLOBAL_SESSION, is_source_unavailable


# Compile regex pattern once for better performance
SOURCE_LINK_PATTERN = re.compile(r'src:\s*"([^"]+)"')
IMAGE_LINK_PATTERN = re.compile(r'poster:\s*"([^"]+)"')


def get_direct_link_from_vidoza(embeded_vidoza_link):
    """Fetch the Vidoza embed page and return the direct video URL from its JW-Player config."""
    try:
        resp = GLOBAL_SESSION.get(
            embeded_vidoza_link, headers={"User-Agent": DEFAULT_USER_AGENT}
        )
        resp.raise_for_status()
        html = resp.text

        if is_source_unavailable(html, resp.status_code):
            raise ValueError("Vidoza: Video nicht verfügbar oder wurde entfernt.")

        if "sourcesCode:" in html:
            match = SOURCE_LINK_PATTERN.search(html)
            if match:
                return match.group(1)

    except niquests.RequestException as err:
        raise ValueError(f"Failed to fetch Vidoza page: {err}") from err


def get_preview_image_link_from_vidoza(embeded_vidoza_link):
    """Fetch the Vidoza embed page and return its poster/preview image URL."""
    try:
        resp = GLOBAL_SESSION.get(
            embeded_vidoza_link, headers={"User-Agent": DEFAULT_USER_AGENT}
        )
        resp.raise_for_status()
        html = resp.text

        if "sourcesCode:" in html:
            match = IMAGE_LINK_PATTERN.search(html)
            if match:
                return match.group(1)

    except niquests.RequestException as err:
        raise ValueError(f"Failed to fetch Vidoza page: {err}") from err


if __name__ == "__main__":
    # Tested on 2026/01/27 -> WORKING
    # Example: https://videzz.net/embed-xneznizpludf.html

    # logging.basicConfig(level=logging.DEBUG)

    link = input("Enter Vidoza Link: ").strip()
    if not link:
        print("Error: No link provided")
        exit(1)

    try:
        print("=" * 25)

        direct_link = get_direct_link_from_vidoza(link)
        print("Direct link:", direct_link)
        print("=" * 25)

        print("Preview image:", get_preview_image_link_from_vidoza(link))
        print("=" * 25)

        print(
            f'mpv "{direct_link}" --http-header-fields=User-Agent: "{DEFAULT_USER_AGENT}"'
        )

        print("=" * 25)
    except ValueError as e:
        print("Error:", e)
