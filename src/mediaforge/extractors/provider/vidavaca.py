"""Vidavaca video hoster extractor (vidavaca.net …).

Vidavaca is a VIDARA clone using the identical jwplayer + /api/stream scheme,
so extraction is delegated to the shared helpers in vidara.py.
"""
try:
    from .vidara import get_stream_data as _get_stream_data
    from .vidara import _stream_from_data
except ImportError:
    from mediaforge.extractors.provider.vidara import get_stream_data as _get_stream_data
    from mediaforge.extractors.provider.vidara import _stream_from_data


def get_direct_link_from_vidavaca(embed_url, headers=None, timeout=20):
    """Return the direct HLS (m3u8) stream URL for a Vidavaca embed link."""
    data = _get_stream_data(embed_url, headers=headers, timeout=timeout)
    return _stream_from_data(data, embed_url, "Vidavaca")


def get_preview_image_link_from_vidavaca(embed_url, headers=None, timeout=20):
    """Return the Vidavaca thumbnail/preview image URL, if any."""
    data = _get_stream_data(embed_url, headers=headers, timeout=timeout)
    thumb = (data or {}).get("thumbnail")
    if not thumb:
        raise ValueError(f"No thumbnail in Vidavaca API response for {embed_url}")
    return thumb


if __name__ == "__main__":
    link = input("Enter Vidavaca Link: ").strip()
    print("Direct link:", get_direct_link_from_vidavaca(link))
