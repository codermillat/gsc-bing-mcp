"""
Chrome Cookie Extractor
-----------------------
Uses rookiepy to read Chrome/Brave/Edge's encrypted cookie database directly
from disk. No browser launch required. Handles macOS (Keychain AES), Windows
(DPAPI), and Linux (Gnome Keyring / kwallet) automatically.

Multi-browser support: tries Chrome → Brave → Edge in order.
Environment variable overrides:
  BROWSER            - force a specific browser: "chrome", "brave", "edge"
  CHROME_PROFILE     - force a Chrome profile path (full path to profile dir)

Includes a 5-minute TTL cache to avoid repeated disk reads per session.
"""

import os
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

# Browser extractors in order of preference
_BROWSER_EXTRACTORS = [
    ("chrome", lambda: rookiepy.chrome(["google.com"])),
    ("brave", lambda: rookiepy.brave(["google.com"])),
    ("edge", lambda: rookiepy.edge(["google.com"])),
]


def _raw_cookies_to_dict(raw_cookies: list) -> dict[str, str]:
    """Convert rookiepy list of cookie dicts → {name: value} dict."""
    cookies: dict[str, str] = {}
    for cookie in raw_cookies:
        name = cookie.get("name", "")
        value = cookie.get("value", "")
        if name and value:
            cookies[name] = str(value)
    return cookies


def _has_sapisid(cookies: dict[str, str]) -> bool:
    """Check if cookie dict has a usable SAPISID."""
    return bool(
        cookies.get("SAPISID")
        or cookies.get("__Secure-3PAPISID")
        or cookies.get("__Secure-1PAPISID")
    )


def _try_extract_from_browser(browser_name: str, fn) -> Optional[dict[str, str]]:
    """Try to extract Google cookies from a single browser. Returns None on failure."""
    try:
        raw = fn()
        if not raw:
            return None
        cookies = _raw_cookies_to_dict(raw)
        if _has_sapisid(cookies):
            logger.debug(f"Got {len(cookies)} Google cookies from {browser_name}")
            return cookies
        else:
            logger.debug(f"{browser_name}: found {len(cookies)} cookies but no SAPISID")
            return None
    except Exception as e:
        logger.debug(f"{browser_name} cookie extraction failed: {e}")
        return None


def get_google_cookies(force_refresh: bool = False) -> dict[str, str]:
    """
    Extract Google authentication cookies from Chrome/Brave/Edge.

    Priority order:
      1. BROWSER env var override (e.g., BROWSER=brave)
      2. CHROME_PROFILE env var for custom Chrome profile path
      3. Auto-detect: Chrome → Brave → Edge

    Returns a dict of cookie_name → cookie_value for google.com.
    Caches results for 5 minutes.

    Raises:
        RuntimeError: If not logged in to Google in any browser, or DB is locked.
    """
    if not force_refresh:
        cached = _get_cache("google")
        if cached:
            logger.debug("Using cached Google cookies")
            return cached

    logger.debug("Extracting Google cookies...")

    browser_override = os.environ.get("BROWSER", "").lower().strip()
    profile_override = os.environ.get("CHROME_PROFILE", "").strip()

    cookies: Optional[dict[str, str]] = None
    used_browser = "unknown"

    # 1. CHROME_PROFILE env var: use rookiepy with explicit profile path
    if profile_override:
        logger.debug(f"Using CHROME_PROFILE override: {profile_override}")
        try:
            raw = rookiepy.chrome(["google.com"])  # rookiepy reads default profile
            # Note: rookiepy doesn't support explicit profile path yet;
            # this is a best-effort attempt
            cookies = _raw_cookies_to_dict(raw)
            if _has_sapisid(cookies):
                used_browser = f"chrome (profile: {profile_override})"
        except Exception as e:
            logger.debug(f"CHROME_PROFILE extraction failed: {e}")

    # 2. BROWSER env var override
    if cookies is None and browser_override:
        extractor_map = {name: fn for name, fn in _BROWSER_EXTRACTORS}
        if browser_override in extractor_map:
            logger.debug(f"Using BROWSER override: {browser_override}")
            cookies = _try_extract_from_browser(browser_override, extractor_map[browser_override])
            if cookies:
                used_browser = browser_override
        else:
            logger.warning(
                f"BROWSER={browser_override!r} is not supported. "
                f"Valid options: {list(extractor_map.keys())}"
            )

    # 3. Auto-detect: try each browser in order
    if cookies is None:
        errors = []
        for browser_name, fn in _BROWSER_EXTRACTORS:
            try:
                raw = fn()
                if not raw:
                    continue
                candidate = _raw_cookies_to_dict(raw)
                if _has_sapisid(candidate):
                    cookies = candidate
                    used_browser = browser_name
                    logger.debug(f"Auto-detected: using {browser_name} ({len(cookies)} cookies)")
                    break
                else:
                    logger.debug(f"  {browser_name}: {len(candidate)} cookies but no SAPISID")
            except Exception as e:
                error_str = str(e).lower()
                if "locked" in error_str or "busy" in error_str:
                    errors.append(f"{browser_name}: database locked (close {browser_name} and retry)")
                elif "permission" in error_str or "access" in error_str:
                    errors.append(f"{browser_name}: permission denied")
                elif "no such file" in error_str or "not found" in error_str:
                    errors.append(f"{browser_name}: not installed")
                else:
                    errors.append(f"{browser_name}: {e}")

        if cookies is None:
            error_detail = "; ".join(errors) if errors else "No browsers found"
            raise RuntimeError(
                f"Google session cookies not found in any browser. {error_detail}. "
                "Please make sure you are logged in to Google in Chrome, Brave, or Edge. "
                "Tip: set BROWSER=chrome or BROWSER=brave environment variable to force a specific browser."
            )

    _set_cache("google", cookies)
    logger.debug(f"Using cookies from {used_browser} ({len(cookies)} total)")
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
        "SAPISID cookie not found. Please log in to Google in Chrome, Brave, or Edge."
    )


def build_cookie_header(cookies: dict[str, str]) -> str:
    """
    Build a Cookie header string from a dict of cookie name→value pairs.
    Includes all Google auth cookies (named + __Host-/__Secure- prefixed).
    """
    parts = []

    # Priority cookies first
    for name in sorted(GOOGLE_COOKIE_NAMES):
        if name in cookies:
            parts.append(f"{name}={cookies[name]}")

    # Also include any __Host- and __Secure- prefixed cookies
    for name, value in cookies.items():
        if (name.startswith("__Host-") or name.startswith("__Secure-")) and name not in GOOGLE_COOKIE_NAMES:
            parts.append(f"{name}={value}")

    return "; ".join(parts)


def get_all_cookies_header(cookies: Optional[dict[str, str]] = None) -> str:
    """
    Build a Cookie header string with ALL google.com cookies (not just auth ones).
    This is used for batchexecute requests which need the full session context.
    """
    if cookies is None:
        cookies = get_google_cookies()
    return "; ".join(f"{k}={v}" for k, v in cookies.items())


def clear_cookie_cache() -> None:
    """Force clear the cookie cache (useful after re-login)."""
    _cache["google"]["data"] = None
    _cache["google"]["expires"] = 0.0
    logger.debug("Cookie cache cleared")
