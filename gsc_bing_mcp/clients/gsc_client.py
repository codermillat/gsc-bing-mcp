"""
Google Search Console Client — batchexecute (browser session, no API key)
--------------------------------------------------------------------------
Uses Google's internal batchexecute RPC protocol, the same mechanism the
GSC web dashboard itself uses. Authentication is via SAPISIDHASH + Chrome
session cookies — no GCP project, OAuth2, or API key required.

Endpoint: https://search.google.com/_/SearchConsoleAggReportUi/data/batchexecute

RPC IDs discovered via Playwright interception of a live GSC session:
  SM7Bqb  — list all verified properties
  gydQ5d  — site summary / property info
  OLiH4d  — performance data (queries, pages, countries, devices)
  nDAfwb  — performance table data (alternate format)
  czrWJf  — coverage/index stats
  B2IOAd  — additional stats panel
  mKtLlc  — property-level summary
"""

import json
import logging
import re
import time
import urllib.parse
from typing import Optional

import httpx

from ..extractors.chrome_cookies import get_google_cookies, get_all_cookies_header
from ..extractors.sapisidhash import compute_sapisidhash, CHROME_USER_AGENT

logger = logging.getLogger(__name__)

# ─── Constants ─────────────────────────────────────────────────────────────────

GSC_ORIGIN = "https://search.google.com"
BE_URL = "https://search.google.com/_/SearchConsoleAggReportUi/data/batchexecute"
APP_ID = "SearchConsoleAggReportUi"

REQUEST_TIMEOUT = 30.0

# ─── RPC IDs (discovered via Playwright interception) ──────────────────────────

RPC_LIST_SITES    = "SM7Bqb"   # args: [[1, [[["site_url"], ...]]]] — sends known site list
RPC_SITE_SUMMARY  = "gydQ5d"   # args: ["site_url"]
RPC_PERFORMANCE   = "OLiH4d"   # args: [site_url, period, null, null, null, [query_opts], null, null, [paging]]
RPC_PERF_TABLE    = "nDAfwb"   # args: [site_url, period, null, null, null, [query_opts]]
RPC_COVERAGE      = "czrWJf"   # args: [site_url, 7, 1]
RPC_STATS_PANEL   = "B2IOAd"   # args: [site_url, [[4, ...]]]
RPC_PROP_SUMMARY  = "mKtLlc"   # args: [site_url]
RPC_SITEMAPS      = "xDwXKd"   # args: [site_url, 7] → returns sitemap list + stats
RPC_INSIGHTS      = "oGVhvf"   # args: [site_url] → returns callouts/notifications

# ─── Dimension codes ───────────────────────────────────────────────────────────

DIMENSIONS = {
    "query":             [2],
    "page":              [3],
    "country":           [4],
    "device":            [4],  # GSC nDAfwb has no dedicated device code; falls back to country
    "search_appearance": [7],
    "date":              [8],
}

# ─── Date period codes (arg[1] in OLiH4d) ─────────────────────────────────────
# These are internal GSC codes observed from live interception.
# 27 = confirmed working for queries (default 28-day-ish range)
# Additional values may correspond to different presets.
DATE_PERIOD_DEFAULT = 27

# ─── XSRF token cache ─────────────────────────────────────────────────────────

_xsrf_cache: dict = {"token": None, "expires": 0.0}
_XSRF_TTL = 3600  # 1 hour


# ─── Core batchexecute helpers ────────────────────────────────────────────────

def _build_headers(cookies: dict[str, str]) -> dict[str, str]:
    """Build the HTTP headers required for batchexecute POST requests."""
    sapisid = (
        cookies.get("SAPISID")
        or cookies.get("__Secure-3PAPISID")
        or cookies.get("__Secure-1PAPISID")
        or ""
    )
    auth = compute_sapisidhash(sapisid, GSC_ORIGIN)
    cookie_str = get_all_cookies_header(cookies)

    return {
        "Authorization": auth,
        "Cookie": cookie_str,
        "Origin": GSC_ORIGIN,
        "Referer": f"{GSC_ORIGIN}/search-console/performance/search-analytics",
        "X-Origin": GSC_ORIGIN,
        "X-Same-Domain": "1",
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        "User-Agent": CHROME_USER_AGENT,
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "X-Goog-Authuser": "0",
    }


def _get_xsrf_token(cookies: dict[str, str]) -> str:
    """
    Obtain the XSRF token required for batchexecute requests.

    Strategy: make a dummy request that returns a 400 error containing the XSRF
    token in the response body as '"xsrf","TOKEN"'.
    """
    if _xsrf_cache["token"] and time.time() < _xsrf_cache["expires"]:
        return _xsrf_cache["token"]

    headers = _build_headers(cookies)
    # Dummy f.req that deliberately has an unknown RPC to get a 400 with XSRF
    dummy_freq = json.dumps([[["__xsrf_probe__", "null", None, "1"]]])
    body = f"f.req={urllib.parse.quote(dummy_freq)}"

    params = {
        "rpcids": "__xsrf_probe__",
        "source-path": "/search-console/performance/search-analytics",
        "f.sid": "-1",
        "bl": "boq_searchconsoleuiserver_20240101.00_p0",
        "hl": "en",
        "soc-app": "1",
        "soc-platform": "1",
        "soc-device": "1",
        "_reqid": "1",
        "rt": "c",
    }

    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            resp = client.post(BE_URL, headers=headers, content=body, params=params)

        resp_text = resp.text
        # Look for '"xsrf","TOKEN"' in the 400 response body
        match = re.search(r'"xsrf","([^"]+)"', resp_text)
        if match:
            token = match.group(1)
            _xsrf_cache["token"] = token
            _xsrf_cache["expires"] = time.time() + _XSRF_TTL
            logger.debug(f"Got XSRF token: {token[:20]}...")
            return token
        else:
            # Sometimes the token appears in other formats
            match2 = re.search(r'at=([A-Za-z0-9_\-]+:[0-9]+)', resp_text)
            if match2:
                token = match2.group(1)
                _xsrf_cache["token"] = token
                _xsrf_cache["expires"] = time.time() + _XSRF_TTL
                return token
            logger.warning(f"XSRF token not found in response (status {resp.status_code})")
            raise RuntimeError(
                f"Could not extract XSRF token from GSC. "
                f"Status: {resp.status_code}. Body preview: {resp_text[:300]}"
            )
    except httpx.RequestError as e:
        raise RuntimeError(f"Network error getting XSRF token: {e}") from e


def _parse_batchexecute_response(text: str) -> list[dict]:
    """
    Parse the batchexecute streaming response.

    Google batchexecute uses a chunked streaming format (NOT standard HTTP chunked):
      DECIMAL_BYTECOUNT\\n
      [JSON_ARRAY]\\n
      DECIMAL_BYTECOUNT\\n
      [JSON_ARRAY]\\n
      ...

    Each JSON array item follows the "wrb.fr" envelope:
      ["wrb.fr", "RPC_ID", "data_json_string", null, null, null, "seq"]

    Returns list of {"rpc_id": str, "data": parsed_data} dicts.
    """
    # Strip anti-XSSI prefix
    text = re.sub(r"^\)\]\}'\n?", "", text.strip())

    results = []

    # Split on chunk-size lines (lines that are only digits, optionally with whitespace)
    chunks = re.split(r"(?m)^\d+\s*$", text)

    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue

        try:
            outer = json.loads(chunk)
        except json.JSONDecodeError:
            continue  # skip non-JSON chunks (e.g. trailing newlines)

        if not isinstance(outer, list):
            continue

        # Each item in the outer array is a response envelope item
        for item in outer:
            if not isinstance(item, list) or len(item) < 2:
                continue

            # wrb.fr envelope: ["wrb.fr", "RPC_ID", "data_json_str", null, ...]
            if item[0] == "wrb.fr" and len(item) >= 3:
                rpc_id = item[1]
                raw_data = item[2]  # JSON string or null

                if raw_data is None:
                    data = None
                elif isinstance(raw_data, str):
                    try:
                        data = json.loads(raw_data)
                    except json.JSONDecodeError:
                        data = raw_data
                else:
                    data = raw_data

                results.append({"rpc_id": rpc_id, "data": data})

    return results


async def _batchexecute(
    rpc_id: str,
    args: list,
    cookies: Optional[dict[str, str]] = None,
) -> dict:
    """
    Execute a single batchexecute RPC call.

    Args:
        rpc_id: The GSC RPC method ID (e.g., "OLiH4d")
        args: Python list of arguments (will be JSON-serialized)
        cookies: Pre-fetched Google cookies dict

    Returns:
        Parsed data dict from the RPC response

    Raises:
        RuntimeError: On auth failure, rate limit, or parse error
    """
    if cookies is None:
        cookies = get_google_cookies()

    headers = _build_headers(cookies)
    xsrf = _get_xsrf_token(cookies)

    args_json = json.dumps(args)
    f_req = json.dumps([[[ rpc_id, args_json, None, "1"]]])
    body = f"f.req={urllib.parse.quote(f_req)}&at={urllib.parse.quote(xsrf)}"

    params = {
        "rpcids": rpc_id,
        "source-path": "/search-console/performance/search-analytics",
        "f.sid": "-1",
        "bl": "boq_searchconsoleuiserver_20240101.00_p0",
        "hl": "en",
        "soc-app": "1",
        "soc-platform": "1",
        "soc-device": "1",
        "_reqid": "1",
        "rt": "c",
    }

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        resp = await client.post(BE_URL, headers=headers, content=body, params=params)

    if resp.status_code == 401:
        raise RuntimeError(
            "Google session expired. Please re-open Chrome and log in to Google, "
            "then try again. The MCP server will pick up fresh cookies automatically."
        )
    if resp.status_code == 403:
        raise RuntimeError(
            "Access denied by Google (403). Your session cookies may be stale. "
            "Re-open Chrome, visit search.google.com/search-console, and try again."
        )
    if resp.status_code == 429:
        raise RuntimeError("Rate limited by Google. Please wait a moment and try again.")

    if resp.status_code not in (200, 400):
        raise RuntimeError(
            f"Unexpected HTTP {resp.status_code} from batchexecute. "
            f"Body preview: {resp.text[:300]}"
        )

    results = _parse_batchexecute_response(resp.text)
    if not results:
        raise RuntimeError(
            f"Empty response from batchexecute ({rpc_id}). "
            f"Body preview: {resp.text[:300]}"
        )

    # Return the first matching result
    for r in results:
        if r["rpc_id"] == rpc_id:
            return r["data"]
    # Fallback: return the first result
    return results[0]["data"]


# ─── Public API ───────────────────────────────────────────────────────────────

async def _scrape_sites_from_html(cookies: dict[str, str]) -> list[dict]:
    """
    Scrape the GSC welcome page to extract the list of verified properties.
    
    Fetches https://search.google.com/search-console/welcome and parses the HTML
    to find property URLs embedded in the page data.
    
    Returns:
        List of dicts: [{"siteUrl": str, "permissionLevel": str}, ...]
    """
    headers = _build_headers(cookies)
    
    # The welcome page contains the full property list
    url = "https://search.google.com/search-console/welcome"
    
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
    
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to fetch GSC welcome page: HTTP {resp.status_code}")
    
    html = resp.text
    logger.debug(f"Fetched GSC welcome page ({len(html)} bytes)")
    
    sites = []
    
    # Strategy 1: Look for WIZ_global_data which contains GSC property data
    wiz_pattern = re.compile(r'AF_initDataCallback\(\{[^}]*key:\s*[\'"]([^\'"]+)[\'"][^}]*data:([^\n]+)\}\);', re.MULTILINE)
    wiz_matches = wiz_pattern.findall(html)
    
    for key, data_str in wiz_matches:
        try:
            data_str = data_str.rstrip().rstrip(',').rstrip()
            data = json.loads(data_str)
            _extract_sites_from_data(data, sites)
        except (json.JSONDecodeError, TypeError) as e:
            logger.debug(f"Failed to parse AF_initDataCallback data for key {key}: {e}")
            continue
    
    # Strategy 2: Look for site URLs in the HTML
    # Pattern: "https://example.com/" or "sc-domain:example.com"
    site_pattern = re.compile(r'(?:"|\')((?:https?://[a-zA-Z0-9\-\.]+/)|(?:sc-domain:[a-zA-Z0-9\-\.]+))(?:"|\')')
    matches = site_pattern.findall(html)
    
    # Common Google/third-party domains to exclude (not user properties)
    exclude_domains = {
        'google.com', 'gstatic.com', 'googleapis.com', 'googleusercontent.com',
        'youtube.com', 'googleblog.com', 'googletagmanager.com', 'twitter.com',
        'facebook.com', 'linkedin.com', 'instagram.com', 'github.com', 'reddit.com'
    }
    
    seen = set()
    for match in matches:
        # Filter out common false positives
        domain_part = match.replace('https://', '').replace('http://', '').replace('sc-domain:', '').rstrip('/')
        if any(excluded in domain_part for excluded in exclude_domains):
            continue
        if match not in seen:
            seen.add(match)
            sites.append({
                "siteUrl": match,
                "permissionLevel": "siteOwner"
            })
    
    # Deduplicate by siteUrl
    unique_sites = []
    seen_urls = set()
    for site in sites:
        url = site.get("siteUrl", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_sites.append(site)
    
    logger.debug(f"Extracted {len(unique_sites)} unique properties from HTML")
    return unique_sites


async def list_sites(cookies: Optional[dict[str, str]] = None) -> list[dict]:
    """
    List all verified properties in Google Search Console.

    Strategy:
      1. Scrape the GSC overview page HTML to extract property list
      2. Try pPDvCb with [0, ""] — fires on GSC page init, may return property list
      3. Try oGVhvf with [""] — similar init RPC
      4. Try SM7Bqb with [[1, []]] — returns known sites (empty if cold session)

    Returns:
        List of dicts: [{"siteUrl": str, "permissionLevel": str}, ...]
    """
    if cookies is None:
        cookies = get_google_cookies()

    # Strategy 1: Scrape the GSC overview page HTML
    try:
        sites = await _scrape_sites_from_html(cookies)
        if sites:
            logger.debug(f"HTML scraping: found {len(sites)} sites")
            return sites
    except Exception as e:
        logger.debug(f"HTML scraping failed: {e}")

    # Strategy 2-4: Try initialization RPCs that fire at GSC page load
    init_rpcs = [
        ("pPDvCb", [0, ""]),
        ("oGVhvf", [""]),
        (RPC_LIST_SITES, [[1, []]]),
    ]

    for rpc_id, args in init_rpcs:
        try:
            data = await _batchexecute(rpc_id, args, cookies)
            if data is None or data == [] or data == "":
                logger.debug(f"  {rpc_id}: returned empty")
                continue
            sites = []
            _extract_sites_from_data(data, sites)
            if sites:
                logger.debug(f"  {rpc_id}: found {len(sites)} sites")
                return sites
            logger.debug(f"  {rpc_id}: data={str(data)[:200]}, no sites extracted")
        except Exception as e:
            logger.debug(f"  {rpc_id} failed: {e}")

    # Fallback: return error with instructions
    raise RuntimeError(
        "Could not list GSC properties automatically. "
        "Please provide site_url directly (e.g. 'https://example.com/'). "
        "You can find your properties at search.google.com/search-console."
    )


def _extract_sites_from_data(data, sites: list) -> None:
    """Recursively scan response data for site URL strings."""
    if isinstance(data, str):
        # Check if it looks like a site URL
        if data.startswith("http") or data.startswith("sc-domain:"):
            if data not in [s.get("siteUrl") for s in sites]:
                sites.append({"siteUrl": data, "permissionLevel": "siteOwner"})
    elif isinstance(data, list):
        for item in data:
            _extract_sites_from_data(item, sites)
    elif isinstance(data, dict):
        for v in data.values():
            _extract_sites_from_data(v, sites)


async def get_site_summary(
    site_url: str,
    cookies: Optional[dict[str, str]] = None,
) -> dict:
    """
    Get a summary/overview for a specific GSC property.

    Args:
        site_url: Verified property URL (e.g. "https://example.com/" or "sc-domain:example.com")

    Returns:
        Raw summary data dict from GSC
    """
    if cookies is None:
        cookies = get_google_cookies()

    data = await _batchexecute(RPC_SITE_SUMMARY, [site_url], cookies)
    return {"siteUrl": site_url, "data": data}


def _date_to_timestamp_ms(date_str: str) -> int:
    """Convert YYYY-MM-DD to milliseconds since epoch (UTC midnight)."""
    import datetime
    dt = datetime.datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc)
    return int(dt.timestamp() * 1000)


def _filter_rows_by_date(
    rows: list[dict], start_date: Optional[str], end_date: Optional[str],
) -> list[dict]:
    """Filter time-series rows to only include dates within [start_date, end_date]."""
    filtered = []
    for row in rows:
        d = row.get("date", "")
        if start_date and d < start_date:
            continue
        if end_date and d > end_date:
            continue
        filtered.append(row)
    return filtered


def _build_date_filter(start_date: Optional[str], end_date: Optional[str]) -> list | None:
    """
    Build the date filter array for batchexecute RPCs.

    When both dates are provided, returns [start_ms, end_ms] which replaces
    the period code in the RPC args. Returns None if no dates specified.
    """
    if not start_date and not end_date:
        return None
    import datetime
    today = datetime.date.today()
    if start_date and not end_date:
        end_date = (today - datetime.timedelta(days=3)).isoformat()
    if end_date and not start_date:
        start_date = (today - datetime.timedelta(days=30)).isoformat()
    return [_date_to_timestamp_ms(start_date), _date_to_timestamp_ms(end_date)]


async def query_search_analytics(
    site_url: str,
    dimensions: Optional[list[str]] = None,
    date_period: int = DATE_PERIOD_DEFAULT,
    search_type: str = "WEB",
    row_limit: int = 100,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    cookies: Optional[dict[str, str]] = None,
) -> dict:
    """
    Query Search Analytics performance data from Google Search Console.

    Uses batchexecute RPCs discovered from live GSC session interception:
    - OLiH4d: date-level time series (clicks/impressions per day)
    - nDAfwb: dimension breakdown (top queries, pages, countries, devices)

    Args:
        site_url:    Verified property URL (e.g., "https://example.com/")
        dimensions:  List of dimension names.
                     Use ["date"] for daily time series.
                     Use ["query"], ["page"], ["country"], ["device"] for breakdowns.
                     Default: ["query"]
        date_period: Internal GSC period code. 27 = default (~28 days), 32 = ~3 months.
        search_type: "WEB" (default), "IMAGE", "VIDEO", "NEWS"
        row_limit:   Approximate max rows (controlled by GSC server)
        start_date:  Optional start date in YYYY-MM-DD format
        end_date:    Optional end date in YYYY-MM-DD format
        cookies:     Pre-fetched Google cookies dict

    Returns:
        Dict with: site_url, dimensions, rows (list of dicts), row_count, raw
    """
    if cookies is None:
        cookies = get_google_cookies()

    if dimensions is None:
        dimensions = ["query"]

    dim_codes = []
    for d in dimensions:
        d_lower = d.lower()
        if d_lower in DIMENSIONS:
            dim_codes.extend(DIMENSIONS[d_lower])
        else:
            raise ValueError(
                f"Unknown dimension: {d!r}. "
                f"Valid options: {list(DIMENSIONS.keys())}"
            )

    query_opts = [
        dim_codes,                          # [0] dimensions
        None,                               # [1] row filter
        [[None, None, None, 3]],            # [2] filter constant
        [[6, [search_type]]],               # [3] search type
        None, None, None, None, None, None, # [4-9] nulls
        1,                                  # [10]
        None, None,                         # [11-12]
        2,                                  # [13] sort
    ]

    is_date_query = (dimensions == ["date"])

    if is_date_query:
        rpc_id = RPC_PERFORMANCE
        period = date_period
        ts_query_opts = [
            [1],                                # [0] dim=1 -> date series
            None,
            [[None, None, None, 3]],
            [[6, [search_type]]],
            None, None, None, None, None, None,
            1, None, None, 2,
        ]
        args = [site_url, period, None, None, None, ts_query_opts, None, None, [None, 2]]
    else:
        rpc_id = RPC_PERF_TABLE
        period = 32
        args = [site_url, period, None, None, None, query_opts]

    logger.debug(f"Querying GSC {rpc_id}: {site_url}, dims={dimensions}")
    raw = await _batchexecute(rpc_id, args, cookies)

    if raw is None:
        logger.warning(f"{rpc_id} returned None for {site_url} dims={dimensions}")
        return {
            "site_url": site_url, "dimensions": dimensions, "search_type": search_type,
            "rows": [], "row_count": 0, "raw": None,
            "note": f"No data returned by GSC ({rpc_id}). The site may have no data for this period.",
        }

    # Parse based on RPC type
    if is_date_query:
        rows = _parse_olih4d_time_series(raw)
        if rows and (start_date or end_date):
            rows = _filter_rows_by_date(rows, start_date, end_date)
    else:
        rows = _parse_ndafwb_breakdown(raw, dimensions)

    return {
        "site_url": site_url,
        "dimensions": dimensions,
        "search_type": search_type,
        "rows": rows,
        "row_count": len(rows),
        "raw": raw,
    }
async def scrape_all_queries_from_html(
    site_url: str,
    search_type: str = "WEB",
    cookies: Optional[dict[str, str]] = None,
) -> dict:
    """
    Scrape ALL queries from the GSC performance page HTML.

    The GSC web interface embeds all query data in JavaScript arrays in the HTML source.
    This bypasses the RPC pagination limitation (which only returns 1 row per request).

    Args:
        site_url: Verified property URL
        search_type: "WEB" (default), "IMAGE", "VIDEO", "NEWS"
        cookies: Pre-fetched Google cookies dict

    Returns:
        Dict with: site_url, search_type, rows (list of query dicts), row_count
    """
    if cookies is None:
        cookies = get_google_cookies()

    headers = _build_headers(cookies)

    encoded_url = urllib.parse.quote(site_url, safe='')
    url = (
        f"https://search.google.com/search-console/performance/search-analytics"
        f"?resource_id={encoded_url}"
        f"&metrics=CLICKS,IMPRESSIONS,CTR,POSITION"
        f"&breakdown=query"
    )

    logger.debug(f"Fetching GSC performance page HTML: {url}")

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)

    if resp.status_code != 200:
        raise RuntimeError(f"Failed to fetch GSC performance page: HTTP {resp.status_code}")

    html = resp.text
    logger.debug(f"Fetched GSC performance page ({len(html)} bytes)")

    import re

    queries = []

    # Find all AF_initDataCallback blocks and look for query data (dimension code [2])
    all_blocks = re.findall(
        r"AF_initDataCallback\(\{[^}]*key:\s*['\"]([^'\"]+)['\"][^}]*data:(.+?), sideChannel",
        html, re.DOTALL,
    )

    for ds_key, data_str in all_blocks:
        try:
            data = json.loads(data_str)
        except (json.JSONDecodeError, TypeError):
            continue

        if not isinstance(data, list) or len(data) < 2:
            continue

        request_echo = str(data[0]) if data[0] else ""
        if "[2]" not in request_echo:
            continue

        logger.debug(f"Found query data in {ds_key}")

        if not isinstance(data[1], list) or not data[1]:
            continue

        # The HTML data has the same nDAfwb structure as the RPC response
        query_rows = _parse_ndafwb_breakdown(data, ["query"])
        if query_rows:
            seen = set()
            for row in query_rows:
                q = row.get("query", "")
                if q and q not in seen:
                    seen.add(q)
                    queries.append(row)
            break

    if not queries:
        logger.warning("Could not find query data in any HTML data block")

    logger.debug(f"Extracted {len(queries)} queries from HTML")

    return {
        "site_url": site_url,
        "search_type": search_type,
        "rows": queries,
        "row_count": len(queries),
        "source": "html_scraping",
    }



def _parse_olih4d_time_series(raw) -> list[dict]:
    """
    Parse OLiH4d (date time series) response.

    Observed structure:
      [request_echo, [[date_entries]]]

    Each date_entry:
      [timestamp_ms, [clicks, impressions, ctr_float, position_float], None, ..., timestamp_ms]
    """
    import datetime

    if not isinstance(raw, list) or len(raw) < 2:
        return []

    rows = []
    # The data is at raw[1][0] — first element after the request echo
    try:
        date_entries = raw[1][0] if isinstance(raw[1], list) and raw[1] else []
    except (IndexError, TypeError):
        return []

    for entry in date_entries:
        if not isinstance(entry, list) or len(entry) < 2:
            continue
        ts_ms = entry[0]
        metrics = entry[1]
        if not isinstance(ts_ms, (int, float)) or not isinstance(metrics, list):
            continue

        # Convert timestamp to date string
        try:
            date_str = datetime.datetime.fromtimestamp(ts_ms / 1000, tz=datetime.timezone.utc).strftime("%Y-%m-%d")
        except (OSError, ValueError, OverflowError):
            date_str = str(ts_ms)

        clicks = int(metrics[0]) if len(metrics) > 0 and isinstance(metrics[0], (int, float)) else 0
        impressions = int(metrics[1]) if len(metrics) > 1 and isinstance(metrics[1], (int, float)) else 0
        ctr_raw = metrics[2] if len(metrics) > 2 else 0
        pos_raw = metrics[3] if len(metrics) > 3 else 0

        try:
            ctr = round(float(ctr_raw) * 100, 2) if isinstance(ctr_raw, (int, float)) else 0.0
        except (ValueError, TypeError):
            ctr = 0.0
        try:
            position = round(float(pos_raw), 1) if isinstance(pos_raw, (int, float)) else 0.0
        except (ValueError, TypeError):
            position = 0.0

        rows.append({
            "date": date_str,
            "clicks": clicks,
            "impressions": impressions,
            "ctr": ctr,
            "position": position,
        })

    return rows


def _extract_metric_value(metric_array: list) -> float | None:
    """
    Extract the numeric value from a GSC metric array.

    Layout:
      - Integer metrics (clicks/impressions): value at index [1]
      - Ratio metrics (CTR/position): value at high indices (43-44), index [1] is None
      - Index [8] always holds the metric type code (5/6/7/8) — must not be confused
        with the actual value.

    Strategy: check index [1] first; if None/0, scan indices 9+ from the end
    (skipping index 8 which is the type code).
    """
    if not isinstance(metric_array, list) or len(metric_array) < 2:
        return None

    val = metric_array[1]
    if isinstance(val, (int, float)):
        if val != 0:
            return val
        # val is 0 — could be a genuine 0 for clicks/impressions, or it could mean
        # the real value is elsewhere (for CTR/position). Check high indices.
        for i in range(len(metric_array) - 1, 8, -1):
            v = metric_array[i]
            if isinstance(v, (int, float)):
                return v
        return 0.0

    # val at [1] is None — scan high indices for the actual value
    for i in range(len(metric_array) - 1, 8, -1):
        v = metric_array[i]
        if isinstance(v, (int, float)):
            return v
    return 0.0


def _extract_dim_value(dim_info: list, dim_name: str) -> str | None:
    """
    Extract a human-readable dimension value from the complex dim_info array.

    GSC nDAfwb stores dimension values at different positions depending on type:
      - query: index 0 (plain string)
      - page:  index 40 (URL string)
      - country: index 17 (dict like {"519508101": ["ind"]})
      - device/search_type: index 0 (plain string like "WEB", "MOBILE")
    """
    if not isinstance(dim_info, list) or not dim_info:
        return None

    if dim_name == "query":
        val = dim_info[0] if dim_info else None
        return val if isinstance(val, str) else None

    if dim_name == "page":
        if len(dim_info) > 40 and isinstance(dim_info[40], str):
            return dim_info[40]
        for v in reversed(dim_info):
            if isinstance(v, str) and (v.startswith("http") or v.startswith("/")):
                return v
        return None

    if dim_name == "country":
        if len(dim_info) > 17 and isinstance(dim_info[17], dict):
            for vals in dim_info[17].values():
                if isinstance(vals, list) and vals and isinstance(vals[0], str):
                    return vals[0].upper()
        for v in dim_info:
            if isinstance(v, dict):
                for vals in v.values():
                    if isinstance(vals, list) and vals and isinstance(vals[0], str):
                        return vals[0].upper()
        return None

    if dim_name == "device":
        if isinstance(dim_info[0], str):
            return dim_info[0]
        return None

    val = dim_info[0] if dim_info else None
    return val if isinstance(val, (str, int)) else str(val) if val is not None else None


def _parse_single_row(row_data: list, dimensions: list[str]) -> dict | None:
    """Parse a single nDAfwb row: [dim_info, metric1, metric2, metric3, metric4]."""
    if not isinstance(row_data, list) or len(row_data) < 2:
        return None

    dim_info = row_data[0]
    if not isinstance(dim_info, list) or len(dim_info) == 0:
        return None

    dim_values: dict[str, str | int] = {}
    for dim_name in dimensions:
        val = _extract_dim_value(dim_info, dim_name)
        if val is not None:
            dim_values[dim_name] = val

    if not dim_values:
        return None

    metrics = {"clicks": 0, "impressions": 0, "ctr": 0.0, "position": 0.0}

    for metric_array in row_data[1:]:
        if not isinstance(metric_array, list) or len(metric_array) < 9:
            continue
        metric_type = metric_array[8]
        if not isinstance(metric_type, int):
            continue
        value = _extract_metric_value(metric_array)

        if metric_type == 5:
            metrics["clicks"] = int(value) if value is not None else 0
        elif metric_type == 6:
            metrics["impressions"] = int(value) if value is not None else 0
        elif metric_type == 7:
            metrics["ctr"] = round(float(value) * 100, 2) if value is not None else 0.0
        elif metric_type == 8:
            metrics["position"] = round(float(value), 1) if value is not None else 0.0

    return {**dim_values, **metrics}


def _parse_ndafwb_breakdown(raw, dimensions: list[str]) -> list[dict]:
    """
    Parse nDAfwb (dimension breakdown) response into structured rows.

    Response shapes observed:
      Shape A: raw[1][0] = [ [row], [row], ... ]  where each row = [dim, m1, m2, m3, m4]
      Shape B: raw[1][0] = [ [[row]], [[row]], ... ]  (extra wrapper layer)
      Shape C: raw[1] = [ [row], [row], ... ]  (no intermediate nesting)

    Metric format: [None, value, None, ..., metric_type_at_idx_8]
    metric_type: 5=clicks, 6=impressions, 7=ctr, 8=position
    """
    if raw is None:
        return []

    rows = []

    try:
        if not isinstance(raw, list) or len(raw) < 2 or not isinstance(raw[1], list):
            return _parse_ndafwb_fallback(raw, dimensions)

        candidates = raw[1][0] if len(raw[1]) > 0 and isinstance(raw[1][0], list) else raw[1]

        if not isinstance(candidates, list):
            return _parse_ndafwb_fallback(raw, dimensions)

        for item in candidates:
            if not isinstance(item, list) or len(item) == 0:
                continue

            # Unwrap nested wrappers: [[row_data]] -> [row_data]
            row_data = item
            while (isinstance(row_data, list) and len(row_data) == 1
                   and isinstance(row_data[0], list) and isinstance(row_data[0][0], list)):
                row_data = row_data[0]

            parsed = _parse_single_row(row_data, dimensions)
            if parsed:
                rows.append(parsed)

    except (IndexError, TypeError, KeyError) as e:
        logger.debug(f"Error parsing nDAfwb response: {e}")
        if not rows:
            return _parse_ndafwb_fallback(raw, dimensions)

    return rows


def _parse_ndafwb_fallback(raw, dimensions: list[str]) -> list[dict]:
    """
    Fallback parser using heuristic scan (old method).
    Used when the new structured parser fails.
    """
    if raw is None:
        return []

    rows = []

    def scan_for_rows(node):
        if isinstance(node, list):
            if len(node) >= 2 + len(dimensions):
                # Check if last 4 elements look like [clicks, impressions, ctr, position]
                tail = node[-4:]
                head = node[:len(dimensions)]
                metrics_ok = (
                    len(tail) == 4 and
                    isinstance(tail[0], (int, float)) and
                    isinstance(tail[1], (int, float)) and
                    isinstance(tail[2], float) and
                    isinstance(tail[3], float)
                )
                dims_ok = all(isinstance(v, (str, int)) for v in head)
                if metrics_ok and dims_ok:
                    row = {}
                    for i, dim_name in enumerate(dimensions):
                        row[dim_name] = head[i]
                    row.update({
                        "clicks": int(tail[0]),
                        "impressions": int(tail[1]),
                        "ctr": round(tail[2] * 100, 2),
                        "position": round(tail[3], 1),
                    })
                    rows.append(row)
                    return

            for item in node:
                scan_for_rows(item)
        elif isinstance(node, dict):
            for v in node.values():
                scan_for_rows(v)

    scan_for_rows(raw)
    return rows


async def get_coverage_stats(
    site_url: str,
    cookies: Optional[dict[str, str]] = None,
) -> dict:
    """
    Get index coverage stats for a GSC property.

    Uses the czrWJf batchexecute RPC.

    Args:
        site_url: Verified property URL

    Returns:
        Dict with raw coverage data from GSC
    """
    if cookies is None:
        cookies = get_google_cookies()

    args = [site_url, 9]  # 9 = observed constant for this RPC
    raw = await _batchexecute(RPC_COVERAGE, args, cookies)
    return {"site_url": site_url, "raw": raw}


async def get_stats_panel(
    site_url: str,
    cookies: Optional[dict[str, str]] = None,
) -> dict:
    """
    Get additional stats panel data (B2IOAd RPC).

    Args:
        site_url: Verified property URL

    Returns:
        Dict with raw stats data
    """
    if cookies is None:
        cookies = get_google_cookies()

    args = [site_url, [[7]]]  # [[7]] = observed constant
    raw = await _batchexecute(RPC_STATS_PANEL, args, cookies)
    return {"site_url": site_url, "raw": raw}


async def get_sitemaps(
    site_url: str,
    cookies: Optional[dict[str, str]] = None,
) -> dict:
    """
    Get submitted sitemaps for a GSC property.

    Uses the xDwXKd batchexecute RPC (discovered via Playwright interception).

    Response structure:
      [[[submitted_stat, indexed_stat, error_stat, [sitemap_list]]]]
      submitted_stat = [null, count]
      sitemap_list   = [[path, full_url], ...]

    Args:
        site_url: Verified property URL

    Returns:
        Dict with submitted, indexed, errors counts and sitemap URL list
    """
    if cookies is None:
        cookies = get_google_cookies()

    raw = await _batchexecute(RPC_SITEMAPS, [site_url, 7], cookies)

    result: dict = {
        "site_url": site_url,
        "submitted": None,
        "indexed": None,
        "errors": None,
        "sitemaps": [],
        "raw": raw,
    }

    try:
        # raw = [[[stat1, stat2, stat3, [sitemap_list]]]]
        # stat = [null, count]
        inner = raw[0][0]  # [stat1, stat2, stat3, [sitemap_list]]
        if len(inner) >= 1 and isinstance(inner[0], list):
            result["submitted"] = inner[0][1] if len(inner[0]) > 1 else None
        if len(inner) >= 2 and isinstance(inner[1], list):
            result["indexed"] = inner[1][1] if len(inner[1]) > 1 else None
        if len(inner) >= 3 and isinstance(inner[2], list):
            result["errors"] = inner[2][1] if len(inner[2]) > 1 else None
        if len(inner) >= 4 and isinstance(inner[3], list):
            for sm in inner[3]:
                if isinstance(sm, list) and len(sm) >= 2:
                    result["sitemaps"].append({
                        "path": sm[0],
                        "url": sm[1],
                    })
    except (IndexError, TypeError, KeyError):
        pass  # Return partial result with raw data

    return result


async def get_insights(
    site_url: str,
    cookies: Optional[dict[str, str]] = None,
) -> dict:
    """
    Get Search Console Insights / notifications for a GSC property.

    Uses the oGVhvf batchexecute RPC (discovered via Playwright interception).

    Response structure:
      [[[[priority, counts, null, "@CALLOUT_TYPE@", [year,month,day], null, bool], ...]]]

    Known callout types:
      @BRANDED-CALLOUT@
      @INSIGHTS-SAN-FILTERED-BY-PAGE-CALLOUT@
      @INSIGHTS-SAN-FILTERED-BY-QUERY-CALLOUT@
      @INSIGHTS-SAN-FILTERED-BY-COUNTRY-CALLOUT@
      @INSIGHTS-SAN-FILTERED-BY-SEARCH-TYPE-CALLOUT@

    Args:
        site_url: Verified property URL

    Returns:
        Dict with parsed callouts list and raw data
    """
    if cookies is None:
        cookies = get_google_cookies()

    raw = await _batchexecute(RPC_INSIGHTS, [site_url], cookies)

    result: dict = {
        "site_url": site_url,
        "callouts": [],
        "raw": raw,
    }

    try:
        # raw = [[[[priority, counts, null, "@CALLOUT_TYPE@", [year,month,day], null, bool], ...]]]
        callout_list = raw[0][0][0]
        for item in callout_list:
            if not isinstance(item, list) or len(item) < 4:
                continue
            priority = item[0]
            counts = item[1]  # e.g. [1, 2]
            callout_type = item[3] if len(item) > 3 else None
            date_parts = item[4] if len(item) > 4 else None
            date_str = None
            if isinstance(date_parts, list) and len(date_parts) >= 3:
                try:
                    date_str = f"{date_parts[0]}-{date_parts[1]:02d}-{date_parts[2]:02d}"
                except (TypeError, ValueError):
                    date_str = str(date_parts)

            result["callouts"].append({
                "priority": priority,
                "counts": counts,
                "type": callout_type,
                "date": date_str,
            })
    except (IndexError, TypeError, KeyError):
        pass  # Return partial result with raw data

    return result