import base64
import binascii
import json
import logging
import re
import time

import niquests

logger = logging.getLogger(__name__)

try:
    from ...config import DEFAULT_USER_AGENT, GLOBAL_SESSION, PROVIDER_HEADERS_D, is_source_unavailable
    from ...playwright.captcha import is_captcha_page, solve_captcha
except ImportError:
    from mediaforge.config import DEFAULT_USER_AGENT, GLOBAL_SESSION, PROVIDER_HEADERS_D, is_source_unavailable
    from mediaforge.playwright.captcha import is_captcha_page, solve_captcha

# -----------------------------
# Precompiled regex patterns
# -----------------------------
REDIRECT_PATTERN = re.compile(r"https?://[^'\"<>]+")
B64_PATTERN = re.compile(r"var a168c='([^']+)'")
HLS_PATTERN = re.compile(r"'hls': '(?P<hls>[^']+)'")
VOE_SCRIPT_PATTERN = re.compile(
    r'<script type="application/json">\s*"(?:\\.|[^"\\])*"\s*</script>', re.DOTALL
)
JUNK_PARTS = ["@$", "^^", "~@", "%?", "*~", "!!", "#&"]


# -----------------------------
# Helper functions
# -----------------------------
def shift_letters(input_str):
    """Apply ROT13 cipher to alphabetic characters."""
    result = []
    for c in input_str:
        code = ord(c)
        if 65 <= code <= 90:  # Uppercase A-Z
            code = (code - 65 + 13) % 26 + 65
        elif 97 <= code <= 122:  # Lowercase a-z
            code = (code - 97 + 13) % 26 + 97
        result.append(chr(code))
    return "".join(result)


def replace_junk(input_str):
    """Replace junk patterns with underscores."""
    for part in JUNK_PARTS:
        input_str = input_str.replace(part, "_")
    return input_str


def shift_back(s, n):
    """Shift characters back by n positions."""
    return "".join(chr(ord(c) - n) for c in s)


def decode_voe_string(encoded):
    """Decode VOE encoded string to a JSON object."""
    try:
        step1 = shift_letters(encoded)
        step2 = replace_junk(step1).replace("_", "")
        step3 = base64.b64decode(step2).decode()
        step4 = shift_back(step3, 3)
        step5 = base64.b64decode(step4[::-1]).decode()
        return json.loads(step5)
    except (binascii.Error, json.JSONDecodeError, UnicodeDecodeError) as err:
        raise ValueError(f"Failed to decode VOE string: {err}") from err


def extract_voe_source_from_html(html):
    """Extract VOE video source using regex + decode_voe_string"""
    try:
        script_blocks = re.findall(
            r'<script\s+type=["\']application/json["\']>(.*?)</script>', html, re.DOTALL
        )
        if not script_blocks:
            return None

        for script_block in script_blocks:
            encoded_text = script_block.strip()
            if encoded_text.startswith('"') and encoded_text.endswith('"'):
                encoded_text = encoded_text[1:-1]

            encoded_text = encoded_text.encode().decode("unicode_escape")

            try:
                decoded = decode_voe_string(encoded_text)
                source = decoded.get("source")
                if source:
                    return source
            except ValueError:
                continue

        return None
    except Exception:
        return None


def is_maintenance_page(html):
    """Check if the VOE CDN page is in maintenance mode."""
    return bool(re.search(r'<title>\s*Maintenance Mode\s*</title>', html, re.IGNORECASE))


# -----------------------------
# Main VOE functions
# -----------------------------
def get_direct_link_from_voe(embeded_voe_link, headers=None, max_retries=3, timeout=30):
    """Get direct VOE video URL with improved retry logic."""
    if headers is None:
        headers = PROVIDER_HEADERS_D.get("VOE", {"User-Agent": DEFAULT_USER_AGENT})
    
    # Enhanced headers for better compatibility
    enhanced_headers = {
        **headers,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    
    for attempt in range(max_retries):
        try:
            # Add delay between retries
            if attempt > 0:
                wait_time = 2 ** attempt  # Exponential backoff: 2, 4, 8 seconds
                logger.warning(f"Retry attempt {attempt + 1}/{max_retries}, waiting {wait_time}s...")
                time.sleep(wait_time)
            
            # First request to VOE
            resp = GLOBAL_SESSION.get(embeded_voe_link, headers=enhanced_headers, timeout=timeout)
            resp.raise_for_status()
            html = resp.text

            if is_source_unavailable(html, resp.status_code):
                raise ValueError("VOE: Video nicht verfügbar oder wurde entfernt.")

            # Captcha on VOE page → solve and retry this request
            if is_captcha_page(html, resp.status_code):
                solve_captcha(embeded_voe_link)
                resp = GLOBAL_SESSION.get(
                    embeded_voe_link, headers=enhanced_headers, timeout=timeout
                )
                resp.raise_for_status()
                html = resp.text

            # Try extracting source directly from the VOE embed page first
            source = extract_voe_source_from_html(html)
            if source:
                logger.debug(f"VOE source extracted on attempt {attempt + 1}")
                return source

            # Fallback: follow the redirect URL embedded in the page
            redirect_match = REDIRECT_PATTERN.search(html)
            if redirect_match:
                redirect_url = redirect_match.group(0)
                
                # Second request with retry
                for redirect_attempt in range(max_retries):
                    try:
                        if redirect_attempt > 0:
                            wait_time = 2 ** redirect_attempt
                            logger.warning(f"Redirect retry {redirect_attempt + 1}/{max_retries}, waiting {wait_time}s...")
                            time.sleep(wait_time)
                        
                        resp = GLOBAL_SESSION.get(redirect_url, headers=enhanced_headers, timeout=timeout)
                        resp.raise_for_status()
                        html = resp.text

                        # Captcha on redirect target → solve and retry
                        if is_captcha_page(html, resp.status_code):
                            solve_captcha(redirect_url)
                            resp = GLOBAL_SESSION.get(
                                redirect_url, headers=enhanced_headers, timeout=timeout
                            )
                            resp.raise_for_status()
                            html = resp.text
                        break
                    except (niquests.RequestException, Exception) as err:
                        if redirect_attempt == max_retries - 1:
                            raise ValueError(f"Weiterleitung konnte nach {max_retries} Versuchen nicht geladen werden: {err}") from err
                        continue
            
            source = extract_voe_source_from_html(html)
            if not source:
                if is_maintenance_page(html):
                    raise ValueError("Dieser VOE-Server ist derzeit im Wartungsmodus. Bitte versuche es später erneut.")
                raise ValueError("Keine VOE-Videoquelle auf der Seite gefunden.")
            
            logger.debug(f"VOE source extracted on attempt {attempt + 1}")
            return source
            
        except (niquests.RequestException, Exception) as err:
            if any(k in str(err) for k in ("Wartungsmodus", "Keine VOE-Videoquelle", "nicht verfügbar")):
                raise
            if attempt == max_retries - 1:
                raise ValueError(f"VOE-Seite konnte nach {max_retries} Versuchen nicht geladen werden: {err}") from err
            logger.warning(f"Attempt {attempt + 1} failed: {str(err)[:100]}...")
            continue
    
    raise ValueError("Unexpected error in get_direct_link_from_voe")


def get_preview_image_link_from_voe(embeded_voe_link, headers=None):
    """Get VOE preview image URL."""
    try:
        if headers is None:
            headers = PROVIDER_HEADERS_D.get("VOE", {"User-Agent": DEFAULT_USER_AGENT})

        resp = GLOBAL_SESSION.get(embeded_voe_link, headers=headers)
        resp.raise_for_status()
        html = resp.text

        redirect_match = REDIRECT_PATTERN.search(html)
        if not redirect_match:
            raise ValueError("No redirect URL found in VOE response.")

        redirect_url = redirect_match.group(0)
        image_url = f"{redirect_url.replace('/e/', '/cache/')}_storyboard_L2.jpg"

        head_resp = GLOBAL_SESSION.head(
            image_url, headers=headers, allow_redirects=True
        )
        head_resp.raise_for_status()
        if "image" not in head_resp.headers.get("Content-Type", ""):
            raise ValueError("Preview image not reachable.")
        return image_url

    except niquests.RequestException as err:
        raise ValueError(f"Failed to fetch VOE preview image: {err}") from err


if __name__ == "__main__":
    # Tested on 2026/01/27 -> WORKING
    # Example: https://voe.sx/e/oa16zsjaqohr

    # logging.basicConfig(level=logging.DEBUG)

    link = input("Enter VOE Link: ").strip()
    if not link:
        print("Error: No link provided")
        exit(1)

    try:
        print("=" * 25)

        direct_link = get_direct_link_from_voe(link)
        print("Direct link:", direct_link)
        print("=" * 25)

        print("Preview image:", get_preview_image_link_from_voe(link))
        print("=" * 25)

        print(
            f'mpv "{direct_link}" --http-header-fields=User-Agent: "{DEFAULT_USER_AGENT}"'
        )

        print("=" * 25)
    except ValueError as e:
        print("Error:", e)
