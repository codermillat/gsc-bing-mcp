"""
Bing Webmaster Tools API Client
---------------------------------
Makes authenticated requests to the official Bing Webmaster Tools API.
Uses a free API key generated from bing.com/webmasters → Settings → API Access.

API Base: https://ssl.bing.com/webmaster/api.svc/json
Docs: https://learn.microsoft.com/en-us/bingwebmaster/
"""

import os
import logging
from typing import Optional
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

BING_API_BASE = "https://ssl.bing.com/webmaster/api.svc/json"

# Default timeout for API requests (seconds)
REQUEST_TIMEOUT = 30.0

# User-Agent for Bing API requests
USER_AGENT = (
    "Mozilla/5.0 (compatible; gsc-bing-mcp/1.0; "
    "+https://github.com/codermillat/gsc-bing-mcp)"
)


def get_bing_api_key() -> str:
    """
    Get the Bing Webmaster API key from environment variable.

    Returns:
        The API key string

    Raises:
        RuntimeError: If BING_API_KEY environment variable is not set
    """
    key = os.environ.get("BING_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "BING_API_KEY environment variable is not set. "
            "To get your free API key:\n"
            "1. Go to https://www.bing.com/webmasters\n"
            "2. Click Settings → API Access\n"
            "3. Click 'Generate API Key'\n"
            "4. Add it to your MCP config: "
            '{"env": {"BING_API_KEY": "your-key-here"}}'
        )
    return key


def _handle_response_error(response: httpx.Response, context: str) -> None:
    """Raise descriptive errors based on HTTP status codes."""
    if response.status_code == 200:
        return

    if response.status_code == 401:
        raise RuntimeError(
            f"Bing API key is invalid or expired ({context}). "
            "Please regenerate your API key at bing.com/webmasters → Settings → API Access."
        )
    if response.status_code == 403:
        raise RuntimeError(
            f"Access denied for Bing API ({context}). "
            "Make sure your API key has access to this site."
        )
    if response.status_code == 429:
        raise RuntimeError(
            f"Bing API rate limit exceeded ({context}). "
            "Please wait a moment and try again."
        )
    if response.status_code == 404:
        raise RuntimeError(
            f"Bing Webmaster resource not found ({context}). "
            "Check that the site URL is added and verified in Bing Webmaster Tools."
        )

    # Try to parse Bing error response
    try:
        error_data = response.json()
        error_msg = error_data.get("Message") or error_data.get("message") or response.text[:200]
    except Exception:
        error_msg = response.text[:200]

    raise RuntimeError(
        f"Bing Webmaster API error {response.status_code} ({context}): {error_msg}"
    )


async def get_user_sites() -> list[dict]:
    """
    List all sites/properties in Bing Webmaster Tools.

    Returns:
        List of site dicts with keys: Url, Favicon, followed
    """
    api_key = get_bing_api_key()

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.get(
            f"{BING_API_BASE}/GetUserSites",
            params={"apikey": api_key},
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )

    _handle_response_error(response, "get_user_sites")
    data = response.json()
    return data.get("d", []) or []


async def get_search_analytics(
    site_url: str,
    start_date: str,
    end_date: str,
    page: int = 0,
    max_count: int = 100,
) -> list[dict]:
    """
    Get search performance data from Bing for a site.

    Args:
        site_url: The site URL (e.g., "https://example.com/")
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        page: Page number for pagination (0-indexed)
        max_count: Max rows per page

    Returns:
        List of stats dicts with keys: Date, Impressions, Clicks, AvgClickPosition
    """
    api_key = get_bing_api_key()

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.get(
            f"{BING_API_BASE}/GetRankAndTrafficStats",
            params={
                "apikey": api_key,
                "siteUrl": site_url,
                "startDate": start_date,
                "endDate": end_date,
                "page": page,
                "count": max_count,
            },
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )

    _handle_response_error(response, f"get_search_analytics for {site_url}")
    data = response.json()
    return data.get("d", []) or []


async def get_crawl_stats(site_url: str) -> dict:
    """
    Get crawl statistics and errors for a site in Bing.

    Args:
        site_url: The site URL (e.g., "https://example.com/")

    Returns:
        Dict with crawl stats: CrawledPages, TotalCrawledUrls, etc.
    """
    api_key = get_bing_api_key()

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.get(
            f"{BING_API_BASE}/GetCrawlStats",
            params={
                "apikey": api_key,
                "siteUrl": site_url,
            },
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )

    _handle_response_error(response, f"get_crawl_stats for {site_url}")
    data = response.json()
    return data.get("d") or {}


async def get_keyword_stats(
    site_url: str,
    start_date: str,
    end_date: str,
    page: int = 0,
    max_count: int = 100,
) -> list[dict]:
    """
    Get keyword/query performance statistics from Bing for a site.

    Args:
        site_url: The site URL (e.g., "https://example.com/")
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        page: Page number for pagination (0-indexed)
        max_count: Max rows per page

    Returns:
        List of keyword dicts with keys: Query, Impressions, Clicks, AvgClickPosition
    """
    api_key = get_bing_api_key()

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.get(
            f"{BING_API_BASE}/GetKeywordStats",
            params={
                "apikey": api_key,
                "siteUrl": site_url,
                "startDate": start_date,
                "endDate": end_date,
                "page": page,
                "count": max_count,
            },
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )

    _handle_response_error(response, f"get_keyword_stats for {site_url}")
    data = response.json()
    return data.get("d", []) or []


async def get_url_info(site_url: str, page_url: str) -> dict:
    """
    Get detailed information about a specific URL in Bing.

    Args:
        site_url: The site URL (e.g., "https://example.com/")
        page_url: The specific page URL to inspect

    Returns:
        Dict with URL info: CrawlDate, HttpStatusCode, indexed, etc.
    """
    api_key = get_bing_api_key()

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.get(
            f"{BING_API_BASE}/GetUrlInfo",
            params={
                "apikey": api_key,
                "siteUrl": site_url,
                "url": page_url,
            },
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )

    _handle_response_error(response, f"get_url_info for {page_url}")
    data = response.json()
    return data.get("d") or {}
