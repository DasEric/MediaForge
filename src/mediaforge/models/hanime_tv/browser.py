"""Headless-browser access layer for hanime.tv (post-Astro rewrite).

hanime signs every /api/v8 request (handshake + per-request signature) and the
player only fetches the HLS stream after the poster is clicked, so plain HTTP
can't reach the data.  We therefore drive a real browser (patchright /
Playwright, as VeeV does) and read what the page itself exposes:

  * metadata  – the ``application/ld+json`` block + DOM (title, poster,
                description, year, tags, censored, franchise episode links).
                No signed API call needed.
  * stream    – click the play overlay so the player loads the signed
                ``…highwinds-cdn.com/….m3u8`` and intercept that request.

All best-effort: if patchright is missing or the page changes, callers degrade
to empty results instead of crashing.
"""
try:
    from ...config import HANIME_BASE_URL, logger
except ImportError:  # pragma: no cover
    from mediaforge.config import HANIME_BASE_URL, logger

_BASE = HANIME_BASE_URL.rstrip("/")
_NAV_TIMEOUT = 45_000
_SETTLE_MS = 1_500


def _sync_playwright():
    try:
        from patchright.sync_api import sync_playwright
        return sync_playwright
    except ImportError:
        try:
            from playwright.sync_api import sync_playwright
            return sync_playwright
        except ImportError:
            return None


def _new_page(p):
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()
    return browser, context, page


def _best_stream(detail):
    """Highest-resolution HLS URL from a raw API manifest (fallback path)."""
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
    return best_url or None


# JS run inside the loaded page to harvest everything the DOM/ld+json exposes.
_EXTRACT_JS = r"""
() => {
  const out = { title:'', description:'', poster_url:'', year:'', censored:'',
                genres:[], episodes:[] };
  try {
    const ld = document.querySelector('script[type="application/ld+json"]');
    if (ld) {
      const j = JSON.parse(ld.textContent);
      out.title = j.name || '';
      out.description = j.description || '';
      out.poster_url = j.thumbnailUrl || '';
      out.year = (j.uploadDate || '').slice(0, 4);
    }
  } catch (e) {}
  const seen = new Set();
  document.querySelectorAll('a[href*="/videos/hentai/"]').forEach(a => {
    const m = (a.getAttribute('href') || '').match(/\/videos\/hentai\/([a-zA-Z0-9._-]+)/);
    if (m && !seen.has(m[1])) {
      seen.add(m[1]);
      let name = (a.getAttribute('title') || a.textContent || '').trim().replace(/\s+/g, ' ');
      out.episodes.push({ slug: m[1], name: name.slice(0, 140) });
    }
  });
  document.querySelectorAll('a[href*="/browse/hentai-tags/"], a[href*="/browse/tags/"], a[href*="/browse/tag/"]').forEach(a => {
    const t = (a.textContent || '').trim();
    if (t && out.genres.indexOf(t) === -1) out.genres.push(t);
  });
  try {
    const low = (document.body.innerText || '').toLowerCase();
    out.censored = /\buncensored\b/.test(low) ? 'Uncensored'
                 : (/\bcensored\b/.test(low) ? 'Censored' : '');
  } catch (e) {}
  return out;
}
"""

# JS to start playback so the player requests the signed .m3u8.
_PLAY_JS = r"""
() => {
  const sels = ['[aria-label="Play video"]', '[aria-label="Play"]',
                '.vjs-big-play-button', '#HTVPlayerRoot', '.vjs-poster'];
  for (const s of sels) { const el = document.querySelector(s); if (el) { try { el.click(); } catch (e) {} } }
  const v = document.querySelector('#HTVPlayer_html5_api') || document.querySelector('video');
  if (v) { try { v.muted = true; const p = v.play(); if (p && p.catch) p.catch(() => {}); } catch (e) {} }
}
"""


def fetch_video(slug, want_stream=False, timeout_ms=_NAV_TIMEOUT):
    """Return (detail, m3u8) for a hanime video slug.

    ``detail`` is a normalised dict:
        {title, description, poster_url, year, censored, genres[], episodes[]}
    ``m3u8`` is the HLS URL (only fetched when ``want_stream`` – requires
    clicking the player), else None.
    """
    spw = _sync_playwright()
    if spw is None:
        logger.warning("hanime: patchright/playwright not installed — cannot fetch video")
        return {}, None

    detail = {}
    m3u8 = [None]
    seen = []
    title = ""
    with spw() as p:
        browser, context, page = _new_page(p)
        try:
            def _on_response(resp):
                try:
                    u = resp.url
                    if ".m3u8" in u and m3u8[0] is None:
                        m3u8[0] = u
                        seen.append((u[:70], resp.status))
                    elif "handshake" in u or "sign.bin" in u:
                        seen.append((u[:70], resp.status))
                except Exception:
                    pass
            page.on("response", _on_response)
            try:
                page.goto(f"{_BASE}/videos/hentai/{slug}", wait_until="domcontentloaded", timeout=timeout_ms)
            except Exception as e:
                logger.debug("hanime goto failed: %s", e)
            page.wait_for_timeout(_SETTLE_MS)
            try:
                detail = page.evaluate(_EXTRACT_JS) or {}
            except Exception as e:
                logger.debug("hanime page extract failed: %s", e)
                detail = {}
            eps = detail.get("episodes") or []
            if slug and not any(e.get("slug") == slug for e in eps):
                eps.insert(0, {"slug": slug, "name": detail.get("title") or ""})
                detail["episodes"] = eps

            if want_stream:
                try:
                    page.wait_for_selector("#HTVPlayer_html5_api, video", timeout=8000)
                except Exception:
                    pass
                try:
                    page.evaluate(_PLAY_JS)
                except Exception:
                    pass
                try:
                    box = page.query_selector("#HTVPlayerRoot") or page.query_selector("#HTVPlayer_html5_api")
                    if box:
                        bb = box.bounding_box()
                        if bb:
                            page.mouse.click(bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2)
                except Exception:
                    pass
                for _ in range(20):
                    if m3u8[0]:
                        break
                    page.wait_for_timeout(500)
            try:
                title = page.title()
            except Exception:
                pass
        finally:
            try:
                browser.close()
            except Exception:
                pass

    if not detail or (want_stream and not m3u8[0]):
        logger.warning(
            "hanime fetch_video(%s, want_stream=%s): detail_keys=%s m3u8=%s page_title=%r seen=%s",
            slug, want_stream, list(detail.keys()) if detail else "NONE",
            m3u8[0], title, seen or "NONE",
        )
    return detail or {}, m3u8[0]
