"""LoadX video hoster extractor.

Not implemented yet: both functions below are stubs that always raise
NotImplementedError. Recognized as a valid provider name (see the
"loadx" -> "LoadX" alias in models/megakino_to/scraper.py), but
selecting it as the active provider will currently fail at download time.

Used by: dispatched generically via extractors.provider_functions
(key "get_direct_link_from_loadx") once selected as a provider by
models/megakino_to/{episode,movie}.py or similar model code."""
try:
    from ...config import DEFAULT_USER_AGENT
except ImportError:
    from mediaforge.config import DEFAULT_USER_AGENT


def get_direct_link_from_loadx(embeded_loadx_link, headers=None):
    """Get direct LoadX video URL. Not implemented: always raises NotImplementedError."""
    raise NotImplementedError("get_direct_link_from_loadx is not implemented yet.")


def get_preview_image_link_from_loadx(embeded_loadx_link, headers=None):
    """Get LoadX preview image URL. Not implemented: always raises NotImplementedError."""
    raise NotImplementedError(
        "get_preview_image_link_from_loadx is not implemented yet."
    )


if __name__ == "__main__":
    # Tested on xxxx/xx/xx -> WORKING
    # Example: https://xxx

    # logging.basicConfig(level=logging.DEBUG)

    link = input("Enter LoadX Link: ").strip()
    if not link:
        print("Error: No link provided")
        exit(1)

    try:
        print("=" * 25)

        direct_link = get_direct_link_from_loadx(link)
        print("Direct link:", direct_link)
        print("=" * 25)

        print("Preview image:", get_preview_image_link_from_loadx(link))
        print("=" * 25)

        print(
            f'mpv "{direct_link}" --http-header-fields=User-Agent: "{DEFAULT_USER_AGENT}"'
        )

        print("=" * 25)
    except ValueError as e:
        print("Error:", e)
