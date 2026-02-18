"""
Google Search Console API Client
----------------------------------
Makes authenticated requests to Google's Search Console API using
SAPISIDHASH authentication (from Chrome browser session — no API key needed).

API Base: https://searchconsole.googleapis.com
Docs (internal): Uses the same endpoints as the GSC web dashboard.
"""

import logging
from typing import Optional
from urllib.parse import quote

import httpx

from ..extractors.sapisidhash import get_gsc_auth_headers

logger = logging.getLogger(__name__)

GSC_BASE = "https://searchconsole.googleapis.com"
WEBMASTERS_BASE = "https://www.googleapis.com/webmasters/v3"

# Default timeout for API requests (seconds)
REQUEST_TIMEOUT = 30.0


def _handle_response_error(response: httpx.Response, context: str) -> None:
    """Raise descriptive errors based on HTTP status codes."""
    if response.status_code == 200:
        return

    if response.status_code == 401:
        raise RuntimeError(
            f"Google session expired ({context}). "
            "Please log in to Google in Chrome and try again."
        )
    if response.status_code == 403:
        raise RuntimeError(
            f"Access denied for {context}. "
            "Make sure you have access to this Search Console property "
            "in your Google account."
        )
    if response.status_code == 429:
        raise RuntimeError(
            f"Rate limited by Google ({context}). "
            "Please wait a moment and try again."
        )
    if response.status_code == 404:
        raise RuntimeError(
            f"Resource not found ({context}). "
            "Check that the site URL is correct and verified in Search Console."
        )

    raise RuntimeError(
        f"Google API error {response.status_code} ({context}): {response.text[:200]}"
    )


async def list_sites() -> list[dict]:
    """
    List all verified sites/properties in Google Search Console.

    Returns:
        List of site dicts with keys: siteUrl, permissionLevel
    """
    headers = get_gsc_auth_headers()

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.get(
            f"{GSC_BASE}/webmasters/v3/sites",
            headers=headers,
        )

    _handle_response_error(response, "list_sites")
    data = response.json()
    return data.get("siteEntry", [])


async def query_search_analytics(
    site_url: str,
    start_date: str,
    end_date: str,
    dimensions: Optional[list[str]] = None,
    row_limit: int = 100,
    start_row: int = 0,
    dimension_filter_groups: Optional[list[dict]] = None,
    aggregation_type: str = "auto",
) -> dict:
    """
    Query Search Analytics data for a site.

    Args:
        site_url: The site URL (e.g., "https://example.com/" or "sc-domain:example.com")
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        dimensions: List of dimensions (query, page, country, device, date, searchAppearance)
        row_limit: Max rows to return (max 25000)
        start_row: Pagination start row (0-indexed)
        dimension_filter_groups: Optional filters
        aggregation_type: "auto", "byPage", or "byProperty"

    Returns:
        Dict with keys: rows (list of data rows), responseAggregationType
    """
    if dimensions is None:
        dimensions = ["query"]

    headers = get_gsc_auth_headers()
    encoded_url = quote(site_url, safe="")

    payload: dict = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": dimensions,
        "rowLimit": min(row_limit, 25000),
        "startRow": start_row,
        "aggregationType": aggregation_type,
    }

    if dimension_filter_groups:
        payload["dimensionFilterGroups"] = dimension_filter_groups

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.post(
            f"{GSC_BASE}/webmasters/v3/sites/{encoded_url}/searchAnalytics/query",
            headers=headers,
            json=payload,
        )

    _handle_response_error(response, f"search_analytics for {site_url}")
    return response.json()


async def list_sitemaps(site_url: str, sitemap_index: Optional[str] = None) -> list[dict]:
    """
    List all sitemaps submitted for a site.

    Args:
        site_url: The site URL (e.g., "https://example.com/")
        sitemap_index: Optional: filter to a specific sitemap index URL

    Returns:
        List of sitemap dicts with keys: path, lastSubmitted, isPending, isSitemapsIndex,
        lastDownloaded, warnings, errors, contents
    """
    headers = get_gsc_auth_headers()
    encoded_url = quote(site_url, safe="")

    params: dict = {}
    if sitemap_index:
        params["sitemapIndex"] = sitemap_index

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.get(
            f"{GSC_BASE}/webmasters/v3/sites/{encoded_url}/sitemaps",
            headers=headers,
            params=params,
        )

    _handle_response_error(response, f"list_sitemaps for {site_url}")
    data = response.json()
    return data.get("sitemap", [])


async def inspect_url(site_url: str, inspection_url: str) -> dict:
    """
    Inspect a URL's indexing status in Google Search Console.

    Args:
        site_url: The verified property URL (e.g., "https://example.com/")
        inspection_url: The specific URL to inspect (must be within site_url)

    Returns:
        Dict with inspectionResult containing:
        - indexStatusResult: coverage state, last crawl, crawl allowed, etc.
        - ampResult: AMP validity (if applicable)
        - mobileUsabilityResult: mobile issues
        - richResultsResult: structured data results
    """
    headers = get_gsc_auth_headers()

    payload = {
        "inspectionUrl": inspection_url,
        "siteUrl": site_url,
        "languageCode": "en",
    }

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.post(
            f"{GSC_BASE}/v1/urlInspection/index:inspect",
            headers=headers,
            json=payload,
        )

    _handle_response_error(response, f"inspect_url {inspection_url}")
    return response.json()
