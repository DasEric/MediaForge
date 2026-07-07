"""Manual smoke-test script for the s.to scraping + CAPTCHA-solving flow.

Not part of the automated test suite (no pytest markers/asserts) -- run
directly with `python -m mediaforge.playwright.test` to exercise
SerienstreamEpisode end-to-end, including the interactive CAPTCHA solver in
captcha.py when Cloudflare challenges the request.
"""

from mediaforge.models import SerienstreamEpisode

episode = SerienstreamEpisode("https://serienstream.to/serie/mr-pickles/staffel-1/episode-1")

print("=== SERIES INFO ===")
print("URL:", episode.url)
print("Title:", episode.title_de)
print("Redirect URL:", episode.redirect_url)
print("Provider URL:", episode.provider_url)
print("Stream URL:", episode.stream_url)

# Run this repeatedly until a CAPTCHA is triggered, to manually exercise the
# CAPTCHA solver (solve_captcha / solve_sto_modal in captcha.py).
