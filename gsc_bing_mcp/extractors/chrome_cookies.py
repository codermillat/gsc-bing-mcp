"""
Chrome Cookie Extractor
-----------------------
Uses rookiepy to read Chrome's encrypted cookie database directly from disk.
No browser launch required. Handles macOS (Keychain AES), Windows (DPAPI),
and Linux (Gnome Keyring / kwallet) automatically.

Includes a 5-minute TTL cache to avoid repeated disk reads per session.
"""

import time
import logging
from typing import Optional

try:
    import rookiepy
except ImportError as e:
    raise ImportError(
        "rookiepy is required. Install with: pip install rookiepy"
    ) from e

logger = logging.getLogger(__name__)

# ─── TTL Cache ────────────────────────────────────────────────────────────────

CACHE_TTL = 300  # 5 minutes

_cache: dict = {
    "google": {"data": None, "expires": 0.0},
}


def _is_cached(key: str) -> bool:
    return (
        _cache[key]["data"] is not None
        and time.time() < _cache[key]["expires"]
    )


def _set_cache(key: str, data: dict) -> None:
    _cache[key]["data"] = data
    _cache[key]["expires"] = time.time() + CACHE_TTL


def _get_cache(key: str) -> Optional[dict]:
    return _cache[key]["data"] if _is_cached(key) else None


# ─── Google Cookies ────────────────────────────────────────────────────────────

# Names of cookies needed for GSC SAPISIDHASH auth
GOOGLE_COOKIE_NAMES = {
    "SAPISID",
    "__Secure-1PAPISID",
    "__Secure-3PAPISID",
    "__Secure-1PSID",
    "__Secure-3PSID",
    "SID",
    "HSID",
    "SSID",
    "APISID",
    "OSID",
    "NID",
}


def get_google_cookies(force_refresh: bool = False) -> dict[str, str]:
    """
    Extract Google authentication cookies from Chrome.

    Returns a dict of cookie_name → cookie_value for google.com.
    Caches results for 5 minutes.

    Raises:
        RuntimeError: If not logged in to Google in Chrome, or Chrome DB is locked.
    """
    if not force_refresh:
        cached = _get_cache("google")
        if cached:
            logger.debug("Using cached Google cookies")
            return cached

    logger.debug("Extracting Google cookies from Chrome...")

    try:
        raw_cookies = rookiepy.chrome(["google.com"])
    except Exception as e:
        error_str = str(e).lower()
        if "locked" in error_str or "busy" in error_str or "unable to open" in error_str:
            raise RuntimeError(
                "Chrome's cookie database is locked. "
                "Please close Chrome completely and try again, "
                "or wait a moment if Chrome just closed."
            ) from e
        if "permission" in error_str or "access" in error_str:
            raise RuntimeError(
                "Permission denied reading Chrome cookies. "
                "On macOS, grant Full Disk Access to your terminal/IDE in "
                "System Settings → Privacy & Security → Full Disk Access."
            ) from e
        raise RuntimeError(
            f"Failed to read Chrome cookies: {e}. "
            "Make sure Chrome is installed and you have been logged in to Google."
        ) from e

    # Build name→value dict
    cookies: dict[str, str] = {}
    for cookie in raw_cookies:
        name = cookie.get("name", "")
        value = cookie.get("value", "")
        if name and value:
            cookies[name] = value

    # Verify we have the essential SAPISID cookie
    sapisid = (
        cookies.get("SAPISID")
        or cookies.get("__Secure-3PAPISID")
        or cookies.get("__Secure-1PAPISID")
    )

    if not sapisid:
        raise RuntimeError(
            "Google session cookies not found. "
            "Please make sure you are logged in to Google in Chrome "
            "and Chrome has been opened at least once since login."
        )

    _set_cache("google", cookies)
    logger.debug(f"Extracted {len(cookies)} Google cookies")
    return cookies


def get_sapisid(cookies: Optional[dict[str, str]] = None) -> str:
    """
    Get the SAPISID value (or equivalent) from Google cookies.
    Tries multiple cookie names in order of preference.
    """
    if cookies is None:
        cookies = get_google_cookies()

    # Try in order of preference
    for name in ("SAPISID", "__Secure-3PAPISID", "__Secure-1PAPISID"):
        value = cookies.get(name)
        if value:
            return value

    raise RuntimeError(
        "SAPISID cookie not found. Please log in to Google in Chrome."
    )


def build_cookie_header(cookies: dict[str, str]) -> str:
    """
    Build a Cookie header string from a dict of cookie name→value pairs.
    Filters to only relevant Google auth cookies.
    """
    parts = []
    for name in GOOGLE_COOKIE_NAMES:
        if name in cookies:
            parts.append(f"{name}={cookies[name]}")

    # Also include any __Host- and __Secure- prefixed cookies
    for name, value in cookies.items():
        if (name.startswith("__Host-") or name.startswith("__Secure-")) and name not in GOOGLE_COOKIE_NAMES:
            parts.append(f"{name}={value}")

    return "; ".join(parts)


def clear_cookie_cache() -> None:
    """Force clear the cookie cache (useful after re-login)."""
    _cache["google"]["data"] = None
    _cache["google"]["expires"] = 0.0
    logger.debug("Cookie cache cleared")
