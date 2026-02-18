"""
SAPISIDHASH Authentication Generator
-------------------------------------
Generates the SAPISIDHASH Authorization header used by Google's internal APIs.
This is the same mechanism used by yt-dlp, ytmusicapi, and other tools that
access Google services using an existing browser session.

Formula: SHA1(f"{unix_timestamp} {SAPISID} {origin}")
Header:  Authorization: SAPISIDHASH {unix_timestamp}_{sha1_hex}

References:
  - https://gist.github.com/eyecatchup/2d700122e24154fdc985b7071ec7764a
  - https://brutecat.com/articles/decoding-google
  - Used by: yt-dlp, ytmusicapi, gpt4free
"""

import hashlib
import time
import logging
from typing import Optional

from .chrome_cookies import get_google_cookies, get_sapisid, build_cookie_header

logger = logging.getLogger(__name__)

# GSC API origin - must match the API host for XD3 validation
GSC_ORIGIN = "https://searchconsole.googleapis.com"

# User-Agent matching Chrome to avoid bot detection
CHROME_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/121.0.0.0 Safari/537.36"
)


def compute_sapisidhash(sapisid: str, origin: str = GSC_ORIGIN) -> str:
    """
    Compute the SAPISIDHASH value.

    Args:
        sapisid: The SAPISID cookie value from Chrome
        origin: The origin URL (default: https://search.google.com)

    Returns:
        SAPISIDHASH string in format: "SAPISIDHASH {timestamp}_{hex_digest}"
    """
    timestamp = int(time.time())
    message = f"{timestamp} {sapisid} {origin}"
    digest = hashlib.sha1(message.encode("utf-8")).hexdigest()
    return f"SAPISIDHASH {timestamp}_{digest}"


def get_gsc_auth_headers(
    cookies: Optional[dict[str, str]] = None,
    origin: str = GSC_ORIGIN,
) -> dict[str, str]:
    """
    Build the complete set of HTTP headers required for authenticated
    Google Search Console API requests.

    Args:
        cookies: Pre-fetched cookie dict. If None, will fetch from Chrome.
        origin: The X-Origin header value (default: https://search.google.com)

    Returns:
        Dict of HTTP headers ready to use with httpx

    Raises:
        RuntimeError: If Google cookies are not available
    """
    if cookies is None:
        cookies = get_google_cookies()

    sapisid = get_sapisid(cookies)
    sapisidhash = compute_sapisidhash(sapisid, origin)
    cookie_header = build_cookie_header(cookies)

    headers = {
        "Authorization": sapisidhash,
        "Cookie": cookie_header,
        "X-Origin": origin,
        "X-Referer": origin,
        "Origin": origin,
        "Referer": f"{origin}/search-console/",
        "Content-Type": "application/json",
        "User-Agent": CHROME_USER_AGENT,
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "X-Goog-Authuser": "0",
    }

    logger.debug(f"Built GSC auth headers with SAPISIDHASH")
    return headers


def validate_gsc_auth() -> bool:
    """
    Check if we can generate valid GSC auth headers.
    Returns True if cookies are available, False otherwise.
    """
    try:
        get_gsc_auth_headers()
        return True
    except RuntimeError:
        return False
