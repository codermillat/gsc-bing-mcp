"""
GSC & Bing Webmaster MCP Server
---------------------------------
An MCP server that pulls search performance data from:
  - Google Search Console (using your existing Chrome browser session — no API key needed)
  - Bing Webmaster Tools (using a free API key from bing.com/webmasters)

Authentication:
  Google: Reads SAPISID cookie from Chrome → generates SAPISIDHASH (same as yt-dlp)
  Bing:   Uses BING_API_KEY environment variable

Transport: stdio (runs locally on user's machine, launched by Cline/Claude Desktop)

Tools (10 total):
  GSC:  gsc_list_sites, gsc_search_analytics, gsc_top_queries,
        gsc_top_pages, gsc_list_sitemaps, gsc_inspect_url
  Bing: bing_list_sites, bing_search_analytics, bing_crawl_stats,
        bing_keyword_stats
"""

import json
import logging
import sys
from datetime import date, timedelta
from typing import Optional

from mcp.server.fastmcp import FastMCP

from .clients import gsc_client, bing_client
from .extractors.chrome_cookies import clear_cookie_cache

# Configure logging (stderr so it doesn't interfere with stdio MCP protocol)
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)

logger = logging.getLogger(__name__)

# Create the FastMCP server
mcp = FastMCP(
    name="GSC & Bing Webmaster",
    instructions=(
        "Access Google Search Console and Bing Webmaster Tools data. "
        "Google auth uses your Chrome browser session (just be logged in to Google in Chrome). "
        "Bing auth uses the BING_API_KEY environment variable. "
        "Site URLs must match exactly as they appear in each respective tool "
        "(e.g., 'https://example.com/' with trailing slash, or 'sc-domain:example.com' for GSC domain properties)."
    ),
)


# ─── Helper Utilities ─────────────────────────────────────────────────────────

def _default_date_range() -> tuple[str, str]:
    """Returns (start_date, end_date) for the last 28 days."""
    today = date.today()
    end = today - timedelta(days=3)   # GSC data has ~3 day lag
    start = end - timedelta(days=27)  # 28 days total
    return start.isoformat(), end.isoformat()


def _format_gsc_rows(rows: list[dict], dimensions: list[str]) -> list[dict]:
    """Format GSC API rows into clean dicts."""
    result = []
    for row in rows:
        item: dict = {}
        keys = row.get("keys", [])
        for i, dim in enumerate(dimensions):
            item[dim] = keys[i] if i < len(keys) else None
        item["clicks"] = row.get("clicks", 0)
        item["impressions"] = row.get("impressions", 0)
        item["ctr"] = round(row.get("ctr", 0) * 100, 2)  # Convert to percentage
        item["position"] = round(row.get("position", 0), 1)
        result.append(item)
    return result


# ─── GSC Tools ────────────────────────────────────────────────────────────────

@mcp.tool()
async def gsc_list_sites() -> str:
    """
    List all verified properties/sites in your Google Search Console account.

    Returns a list of sites with their URLs and permission levels.
    Use the siteUrl from this list in other gsc_* tools.

    No parameters required.
    """
    try:
        sites = await gsc_client.list_sites()
        if not sites:
            return "No verified sites found in your Google Search Console account."

        result = []
        for site in sites:
            result.append({
                "siteUrl": site.get("siteUrl", ""),
                "permissionLevel": site.get("permissionLevel", ""),
            })
        return json.dumps(result, indent=2)

    except RuntimeError as e:
        return f"❌ Error: {e}"
    except Exception as e:
        logger.exception("Unexpected error in gsc_list_sites")
        return f"❌ Unexpected error: {e}"


@mcp.tool()
async def gsc_search_analytics(
    site_url: str,
    start_date: str,
    end_date: str,
    dimensions: str = "query",
    row_limit: int = 100,
) -> str:
    """
    Get search analytics data from Google Search Console.

    Returns clicks, impressions, CTR, and average position for the given dimensions.

    Args:
        site_url: The verified property URL exactly as it appears in GSC
                  (e.g., "https://example.com/" or "sc-domain:example.com")
        start_date: Start date in YYYY-MM-DD format (e.g., "2024-01-01")
        end_date: End date in YYYY-MM-DD format (e.g., "2024-01-31")
        dimensions: Comma-separated dimensions to group by.
                    Options: query, page, country, device, date, searchAppearance
                    Default: "query"
                    Example: "query,page" or "date,device"
        row_limit: Maximum rows to return (1-1000, default 100)
    """
    try:
        dims = [d.strip() for d in dimensions.split(",") if d.strip()]
        if not dims:
            dims = ["query"]

        row_limit = max(1, min(row_limit, 1000))

        data = await gsc_client.query_search_analytics(
            site_url=site_url,
            start_date=start_date,
            end_date=end_date,
            dimensions=dims,
            row_limit=row_limit,
        )

        rows = data.get("rows", [])
        if not rows:
            return (
                f"No data found for {site_url} between {start_date} and {end_date}. "
                "Note: GSC data has a ~3-day lag. Try a date range ending 3+ days ago."
            )

        formatted = _format_gsc_rows(rows, dims)
        return json.dumps({
            "site": site_url,
            "period": f"{start_date} to {end_date}",
            "dimensions": dims,
            "total_rows": len(formatted),
            "data": formatted,
        }, indent=2)

    except RuntimeError as e:
        return f"❌ Error: {e}"
    except Exception as e:
        logger.exception("Unexpected error in gsc_search_analytics")
        return f"❌ Unexpected error: {e}"


@mcp.tool()
async def gsc_top_queries(
    site_url: str,
    limit: int = 25,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> str:
    """
    Get the top search queries driving traffic to your site in Google Search Console.

    Returns queries sorted by clicks (highest first) with impressions, CTR, and position.

    Args:
        site_url: The verified property URL (e.g., "https://example.com/")
        limit: Number of top queries to return (default 25, max 200)
        start_date: Start date YYYY-MM-DD (default: 28 days ago)
        end_date: End date YYYY-MM-DD (default: 3 days ago to account for data lag)
    """
    try:
        if not start_date or not end_date:
            start_date, end_date = _default_date_range()

        limit = max(1, min(limit, 200))

        data = await gsc_client.query_search_analytics(
            site_url=site_url,
            start_date=start_date,
            end_date=end_date,
            dimensions=["query"],
            row_limit=limit,
        )

        rows = data.get("rows", [])
        if not rows:
            return f"No query data found for {site_url} in the selected date range."

        formatted = _format_gsc_rows(rows, ["query"])
        # Already sorted by clicks descending by GSC API
        return json.dumps({
            "site": site_url,
            "period": f"{start_date} to {end_date}",
            "top_queries": formatted,
        }, indent=2)

    except RuntimeError as e:
        return f"❌ Error: {e}"
    except Exception as e:
        logger.exception("Unexpected error in gsc_top_queries")
        return f"❌ Unexpected error: {e}"


@mcp.tool()
async def gsc_top_pages(
    site_url: str,
    limit: int = 25,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> str:
    """
    Get the top pages driving traffic to your site in Google Search Console.

    Returns pages sorted by clicks (highest first) with impressions, CTR, and position.

    Args:
        site_url: The verified property URL (e.g., "https://example.com/")
        limit: Number of top pages to return (default 25, max 200)
        start_date: Start date YYYY-MM-DD (default: 28 days ago)
        end_date: End date YYYY-MM-DD (default: 3 days ago)
    """
    try:
        if not start_date or not end_date:
            start_date, end_date = _default_date_range()

        limit = max(1, min(limit, 200))

        data = await gsc_client.query_search_analytics(
            site_url=site_url,
            start_date=start_date,
            end_date=end_date,
            dimensions=["page"],
            row_limit=limit,
        )

        rows = data.get("rows", [])
        if not rows:
            return f"No page data found for {site_url} in the selected date range."

        formatted = _format_gsc_rows(rows, ["page"])
        return json.dumps({
            "site": site_url,
            "period": f"{start_date} to {end_date}",
            "top_pages": formatted,
        }, indent=2)

    except RuntimeError as e:
        return f"❌ Error: {e}"
    except Exception as e:
        logger.exception("Unexpected error in gsc_top_pages")
        return f"❌ Unexpected error: {e}"


@mcp.tool()
async def gsc_list_sitemaps(site_url: str) -> str:
    """
    List all sitemaps submitted for a site in Google Search Console.

    Returns sitemap URLs with their status, submission date, and any errors/warnings.

    Args:
        site_url: The verified property URL (e.g., "https://example.com/")
    """
    try:
        sitemaps = await gsc_client.list_sitemaps(site_url)

        if not sitemaps:
            return f"No sitemaps found for {site_url}. Submit sitemaps at search.google.com/search-console"

        result = []
        for sm in sitemaps:
            result.append({
                "path": sm.get("path", ""),
                "lastSubmitted": sm.get("lastSubmitted", ""),
                "lastDownloaded": sm.get("lastDownloaded", ""),
                "isPending": sm.get("isPending", False),
                "isSitemapsIndex": sm.get("isSitemapsIndex", False),
                "warnings": sm.get("warnings", 0),
                "errors": sm.get("errors", 0),
                "type": sm.get("type", ""),
                "urlCount": sum(
                    c.get("submitted", 0)
                    for c in sm.get("contents", [])
                ),
            })

        return json.dumps({
            "site": site_url,
            "sitemaps": result,
            "total": len(result),
        }, indent=2)

    except RuntimeError as e:
        return f"❌ Error: {e}"
    except Exception as e:
        logger.exception("Unexpected error in gsc_list_sitemaps")
        return f"❌ Unexpected error: {e}"


@mcp.tool()
async def gsc_inspect_url(site_url: str, url: str) -> str:
    """
    Inspect a specific URL's indexing status in Google Search Console.

    Returns crawl status, index status, last crawl date, mobile usability,
    and any coverage issues.

    Args:
        site_url: The verified property URL (e.g., "https://example.com/")
        url: The specific page URL to inspect (must be within site_url)
             e.g., "https://example.com/blog/post-1"
    """
    try:
        data = await gsc_client.inspect_url(site_url, url)
        result = data.get("inspectionResult", {})

        index_result = result.get("indexStatusResult", {})
        mobile_result = result.get("mobileUsabilityResult", {})
        rich_result = result.get("richResultsResult", {})

        summary = {
            "url": url,
            "coverageState": index_result.get("coverageState", "UNKNOWN"),
            "robotsTxtState": index_result.get("robotsTxtState", "UNKNOWN"),
            "indexingState": index_result.get("indexingState", "UNKNOWN"),
            "lastCrawlTime": index_result.get("lastCrawlTime", ""),
            "pageFetchState": index_result.get("pageFetchState", "UNKNOWN"),
            "crawledAs": index_result.get("crawledAs", ""),
            "googleCanonical": index_result.get("googleCanonical", ""),
            "userCanonical": index_result.get("userCanonical", ""),
            "referringUrls": index_result.get("referringUrls", [])[:5],
            "mobileUsability": mobile_result.get("verdict", "UNKNOWN"),
            "mobileIssues": [i.get("issueType") for i in mobile_result.get("issues", [])],
            "richResultsVerdict": rich_result.get("verdict", "UNKNOWN"),
        }

        return json.dumps(summary, indent=2)

    except RuntimeError as e:
        return f"❌ Error: {e}"
    except Exception as e:
        logger.exception("Unexpected error in gsc_inspect_url")
        return f"❌ Unexpected error: {e}"


# ─── Bing Tools ───────────────────────────────────────────────────────────────

@mcp.tool()
async def bing_list_sites() -> str:
    """
    List all sites/properties in your Bing Webmaster Tools account.

    Returns a list of sites with their URLs.
    Requires BING_API_KEY environment variable.

    No parameters required.
    """
    try:
        sites = await bing_client.get_user_sites()

        if not sites:
            return (
                "No sites found in your Bing Webmaster Tools account. "
                "Add and verify sites at bing.com/webmasters"
            )

        result = [
            {"url": site.get("Url") or site.get("url", "")}
            for site in sites
        ]
        return json.dumps(result, indent=2)

    except RuntimeError as e:
        return f"❌ Error: {e}"
    except Exception as e:
        logger.exception("Unexpected error in bing_list_sites")
        return f"❌ Unexpected error: {e}"


@mcp.tool()
async def bing_search_analytics(
    site_url: str,
    start_date: str,
    end_date: str,
    limit: int = 100,
) -> str:
    """
    Get search performance data from Bing Webmaster Tools for a site.

    Returns impressions, clicks, and average click position by date.

    Args:
        site_url: The site URL as it appears in Bing Webmaster Tools
                  (e.g., "https://example.com/")
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        limit: Maximum number of rows to return (default 100)
    """
    try:
        rows = await bing_client.get_search_analytics(
            site_url=site_url,
            start_date=start_date,
            end_date=end_date,
            max_count=min(limit, 500),
        )

        if not rows:
            return f"No Bing search analytics found for {site_url} in the selected date range."

        formatted = []
        for row in rows:
            formatted.append({
                "date": row.get("Date", row.get("date", "")),
                "impressions": row.get("Impressions", row.get("impressions", 0)),
                "clicks": row.get("Clicks", row.get("clicks", 0)),
                "avgClickPosition": row.get("AvgClickPosition", row.get("avgClickPosition", 0)),
            })

        return json.dumps({
            "site": site_url,
            "period": f"{start_date} to {end_date}",
            "data": formatted,
            "total_rows": len(formatted),
        }, indent=2)

    except RuntimeError as e:
        return f"❌ Error: {e}"
    except Exception as e:
        logger.exception("Unexpected error in bing_search_analytics")
        return f"❌ Unexpected error: {e}"


@mcp.tool()
async def bing_crawl_stats(site_url: str) -> str:
    """
    Get crawl statistics for a site in Bing Webmaster Tools.

    Returns information about how many pages Bing has crawled,
    crawl errors, blocked URLs, and DNS/connection issues.

    Args:
        site_url: The site URL as it appears in Bing Webmaster Tools
                  (e.g., "https://example.com/")
    """
    try:
        stats = await bing_client.get_crawl_stats(site_url)

        if not stats:
            return f"No crawl stats found for {site_url}."

        # Normalize field names (Bing API uses PascalCase)
        result = {
            "site": site_url,
            "crawledPages": stats.get("CrawledPages", stats.get("crawledPages", 0)),
            "inIndex": stats.get("InIndex", stats.get("inIndex", 0)),
            "crawlErrors": stats.get("CrawlErrors", stats.get("crawlErrors", 0)),
            "dnsErrors": stats.get("DnsErrors", stats.get("dnsErrors", 0)),
            "connectionTimeouts": stats.get("ConnectionTimeouts", stats.get("connectionTimeouts", 0)),
            "robotsExcluded": stats.get("RobotsExcluded", stats.get("robotsExcluded", 0)),
            "httpErrors": stats.get("HttpErrors", stats.get("httpErrors", 0)),
        }

        return json.dumps(result, indent=2)

    except RuntimeError as e:
        return f"❌ Error: {e}"
    except Exception as e:
        logger.exception("Unexpected error in bing_crawl_stats")
        return f"❌ Unexpected error: {e}"


@mcp.tool()
async def bing_keyword_stats(
    site_url: str,
    start_date: str,
    end_date: str,
    limit: int = 100,
) -> str:
    """
    Get keyword/query performance statistics from Bing Webmaster Tools.

    Returns the top keywords driving traffic from Bing with impressions,
    clicks, and average click position.

    Args:
        site_url: The site URL as it appears in Bing Webmaster Tools
                  (e.g., "https://example.com/")
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        limit: Maximum number of keywords to return (default 100)
    """
    try:
        rows = await bing_client.get_keyword_stats(
            site_url=site_url,
            start_date=start_date,
            end_date=end_date,
            max_count=min(limit, 500),
        )

        if not rows:
            return f"No keyword data found for {site_url} in the selected date range."

        formatted = []
        for row in rows:
            formatted.append({
                "query": row.get("Query", row.get("query", "")),
                "impressions": row.get("Impressions", row.get("impressions", 0)),
                "clicks": row.get("Clicks", row.get("clicks", 0)),
                "avgClickPosition": row.get("AvgClickPosition", row.get("avgClickPosition", 0)),
            })

        # Sort by clicks descending
        formatted.sort(key=lambda x: x.get("clicks", 0), reverse=True)

        return json.dumps({
            "site": site_url,
            "period": f"{start_date} to {end_date}",
            "keywords": formatted,
            "total": len(formatted),
        }, indent=2)

    except RuntimeError as e:
        return f"❌ Error: {e}"
    except Exception as e:
        logger.exception("Unexpected error in bing_keyword_stats")
        return f"❌ Unexpected error: {e}"


# ─── Utility Tool ─────────────────────────────────────────────────────────────

@mcp.tool()
async def refresh_google_session() -> str:
    """
    Force refresh the cached Google Chrome cookies.

    Use this if you've recently logged back in to Google in Chrome
    and GSC tools are still showing authentication errors.

    No parameters required.
    """
    try:
        clear_cookie_cache()
        # Try to re-extract cookies to verify
        from .extractors.chrome_cookies import get_google_cookies
        cookies = get_google_cookies(force_refresh=True)
        return (
            f"✅ Google session refreshed successfully. "
            f"Found {len(cookies)} cookies for google.com. "
            "GSC tools are ready to use."
        )
    except RuntimeError as e:
        return f"❌ Could not refresh session: {e}"
    except Exception as e:
        return f"❌ Unexpected error: {e}"


# ─── Entry Point ──────────────────────────────────────────────────────────────

def main() -> None:
    """Entry point for uvx / pip installation."""
    mcp.run()


if __name__ == "__main__":
    main()
