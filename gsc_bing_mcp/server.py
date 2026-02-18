"""
GSC & Bing Webmaster MCP Server  (v0.2.0)
-------------------------------------------
An MCP server that pulls search performance data from:
  - Google Search Console (using your existing Chrome browser session — no API key needed)
  - Bing Webmaster Tools (using a free API key from bing.com/webmasters)

Authentication:
  Google: Reads SAPISID cookie from Chrome → generates SAPISIDHASH (same as yt-dlp)
          Uses batchexecute (Google's internal RPC protocol — no GCP project needed!)
  Bing:   Uses BING_API_KEY environment variable

Transport: stdio (runs locally on user's machine, launched by Cline/Claude Desktop)

Tools (23 total):
  GSC:  gsc_list_sites, gsc_performance_trend, gsc_top_queries,
        gsc_top_pages, gsc_search_analytics, gsc_site_summary,
        gsc_list_sitemaps, gsc_insights, gsc_all_queries,
        gsc_index_coverage, gsc_query_pages
  Bing: bing_list_sites, bing_search_analytics, bing_crawl_stats,
        bing_keyword_stats, bing_url_info, bing_page_stats,
        bing_submit_url, bing_submit_url_batch, bing_crawl_issues,
        bing_url_submission_quota, bing_link_counts
  Util: refresh_google_session
"""

import json
import logging
import sys
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
        "Google auth uses your Chrome browser session — just be logged in to Google in Chrome "
        "(Chrome, Brave, or Edge). No API key or GCP setup required. "
        "Bing auth uses the BING_API_KEY environment variable. "
        "Site URLs must match exactly as they appear in each tool "
        "(e.g., 'https://example.com/' with trailing slash, or 'sc-domain:example.com' for GSC domain properties). "
        "Note: GSC data has a ~2-3 day lag. For best results use gsc_performance_trend "
        "which returns daily data, or gsc_top_queries/gsc_top_pages for dimension breakdowns. "
        "GSC tools now support optional start_date/end_date params (YYYY-MM-DD). "
        "Use gsc_all_queries for HTML-based extraction of all queries. "
        "Use bing_submit_url / bing_submit_url_batch to request Bing indexing."
    ),
)


# ─── GSC Tools ────────────────────────────────────────────────────────────────

@mcp.tool()
async def gsc_list_sites() -> str:
    """
    List all verified properties/sites in your Google Search Console account.

    Uses your Chrome browser session (no API key required).
    If auto-detection fails, use site URLs you know are verified in GSC.

    No parameters required.
    """
    try:
        sites = await gsc_client.list_sites()
        if not sites:
            return "No verified sites found. Try providing the site_url directly in other tools."

        result = []
        for site in sites:
            url = site.get("siteUrl", "")
            prop_type = "Domain property" if url.startswith("sc-domain:") else "URL prefix"
            result.append({
                "siteUrl": url,
                "permissionLevel": site.get("permissionLevel", "siteOwner"),
                "propertyType": prop_type,
            })
        return json.dumps(result, indent=2)

    except RuntimeError as e:
        return (
            f"❌ {e}\n\n"
            "Tip: You can still use other GSC tools by providing the site_url directly. "
            "Check your verified properties at search.google.com/search-console"
        )
    except Exception as e:
        logger.exception("Unexpected error in gsc_list_sites")
        return f"❌ Unexpected error: {e}"


@mcp.tool()
async def gsc_performance_trend(
    site_url: str,
    search_type: str = "WEB",
    start_date: str = "",
    end_date: str = "",
) -> str:
    """
    Get daily performance trend data for a GSC property.

    Returns clicks, impressions, CTR, and average position for each day
    over the recent period (~last 17 days based on GSC data availability).

    This is the most reliable GSC tool — returns clean, structured daily data.

    Args:
        site_url: The verified property URL exactly as it appears in GSC
                  (e.g., "https://example.com/" or "sc-domain:example.com")
        search_type: Search type filter — "WEB" (default), "IMAGE", "VIDEO", "NEWS"
        start_date: Optional start date in YYYY-MM-DD format (default: ~17 days ago)
        end_date: Optional end date in YYYY-MM-DD format (default: ~3 days ago, due to GSC lag)
    """
    try:
        result = await gsc_client.query_search_analytics(
            site_url=site_url,
            dimensions=["date"],
            search_type=search_type,
            start_date=start_date or None,
            end_date=end_date or None,
        )

        rows = result.get("rows", [])
        if not rows:
            note = result.get("note", "")
            return (
                f"No performance data found for {site_url}. {note}\n"
                "Ensure the site is verified in Google Search Console and has received traffic."
            )

        # Calculate totals
        total_clicks = sum(r.get("clicks", 0) for r in rows)
        total_impressions = sum(r.get("impressions", 0) for r in rows)
        avg_ctr = round(total_clicks / total_impressions * 100, 2) if total_impressions > 0 else 0.0
        avg_position = round(
            sum(r.get("position", 0) * r.get("impressions", 0) for r in rows) /
            max(total_impressions, 1), 1
        )

        return json.dumps({
            "site": site_url,
            "search_type": search_type,
            "summary": {
                "total_clicks": total_clicks,
                "total_impressions": total_impressions,
                "avg_ctr_pct": avg_ctr,
                "avg_position": avg_position,
                "days_with_data": len(rows),
            },
            "daily_data": rows,
        }, indent=2)

    except RuntimeError as e:
        return f"❌ Error: {e}"
    except Exception as e:
        logger.exception("Unexpected error in gsc_performance_trend")
        return f"❌ Unexpected error: {e}"


@mcp.tool()
async def gsc_top_queries(
    site_url: str,
    limit: int = 25,
    search_type: str = "WEB",
    start_date: str = "",
    end_date: str = "",
) -> str:
    """
    Get the top search queries driving traffic to your site in Google Search Console.

    Returns queries with clicks, impressions, CTR, and average position.
    
    Set limit=0 to return all available query rows returned by GSC.

    Args:
        site_url: The verified property URL (e.g., "https://example.com/")
        limit: Number of top queries to return (default 25, use 0 for all queries)
        search_type: "WEB" (default), "IMAGE", "VIDEO", "NEWS"
        start_date: Optional start date in YYYY-MM-DD format
        end_date: Optional end date in YYYY-MM-DD format
    """
    try:
        result = await gsc_client.query_search_analytics(
            site_url=site_url,
            dimensions=["query"],
            search_type=search_type,
            start_date=start_date or None,
            end_date=end_date or None,
        )

        rows = result.get("rows", [])
        if not rows:
            return (
                f"No query data found for {site_url}.\n"
                "The site may have no search traffic or data may not be available yet. "
                "Use gsc_performance_trend to see daily aggregate data."
            )

        # Sort by clicks (descending) then impressions (descending)
        rows_sorted = sorted(
            rows,
            key=lambda r: (r.get("clicks", 0), r.get("impressions", 0)),
            reverse=True
        )
        
        # Apply limit (0 means return all)
        if limit > 0:
            rows_sorted = rows_sorted[:limit]

        return json.dumps({
            "site": site_url,
            "search_type": search_type,
            "top_queries": rows_sorted,
            "total_shown": len(rows_sorted),
            "total_available": len(rows),
            "source": "batchexecute",
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
    search_type: str = "WEB",
    start_date: str = "",
    end_date: str = "",
) -> str:
    """
    Get the top pages driving organic search traffic from Google Search Console.

    Returns pages with clicks, impressions, CTR, and average position.
    Set limit=0 to return all available page rows.
    Note: Sites with very low traffic may return aggregate totals rather than
    individual page breakdowns.

    Args:
        site_url: The verified property URL (e.g., "https://example.com/")
        limit: Number of top pages to return (default 25, use 0 for all pages)
        search_type: "WEB" (default), "IMAGE", "VIDEO", "NEWS"
        start_date: Optional start date in YYYY-MM-DD format
        end_date: Optional end date in YYYY-MM-DD format
    """
    try:
        result = await gsc_client.query_search_analytics(
            site_url=site_url,
            dimensions=["page"],
            search_type=search_type,
            start_date=start_date or None,
            end_date=end_date or None,
        )

        rows = result.get("rows", [])
        if not rows:
            note = result.get("note", "")
            return (
                f"No page data found for {site_url}. {note}\n"
                "Note: GSC only shows page breakdowns when a site has enough traffic. "
                "Use gsc_performance_trend to see daily aggregate data."
            )

        rows_sorted = sorted(rows, key=lambda r: r.get("clicks", 0), reverse=True)
        if limit > 0:
            rows_sorted = rows_sorted[:limit]

        return json.dumps({
            "site": site_url,
            "search_type": search_type,
            "top_pages": rows_sorted,
            "total_shown": len(rows_sorted),
            "total_available": len(rows),
        }, indent=2)

    except RuntimeError as e:
        return f"❌ Error: {e}"
    except Exception as e:
        logger.exception("Unexpected error in gsc_top_pages")
        return f"❌ Unexpected error: {e}"


@mcp.tool()
async def gsc_search_analytics(
    site_url: str,
    dimension: str = "query",
    search_type: str = "WEB",
    start_date: str = "",
    end_date: str = "",
) -> str:
    """
    Get search analytics data from Google Search Console with dimension grouping.

    Returns performance data grouped by the specified dimension.
    For daily trends, use gsc_performance_trend instead.

    Args:
        site_url: The verified property URL (e.g., "https://example.com/")
        dimension: Grouping dimension — one of:
                   "query" (default) — top search queries
                   "page"   — top landing pages
                   "country" — traffic by country
                   "device"  — traffic by device (desktop/mobile/tablet)
        search_type: "WEB" (default), "IMAGE", "VIDEO", "NEWS"
        start_date: Optional start date in YYYY-MM-DD format
        end_date: Optional end date in YYYY-MM-DD format
    """
    valid_dims = ["query", "page", "country", "device"]
    dim = dimension.lower().strip()
    if dim not in valid_dims:
        return f"❌ Invalid dimension '{dimension}'. Valid options: {valid_dims}"

    try:
        result = await gsc_client.query_search_analytics(
            site_url=site_url,
            dimensions=[dim],
            search_type=search_type,
            start_date=start_date or None,
            end_date=end_date or None,
        )

        rows = result.get("rows", [])
        if not rows:
            note = result.get("note", "")
            return (
                f"No data found for {site_url} with dimension={dim}. {note}\n"
                "Use gsc_performance_trend to see daily aggregate traffic data."
            )

        rows_sorted = sorted(rows, key=lambda r: r.get("clicks", 0), reverse=True)[:100]

        return json.dumps({
            "site": site_url,
            "dimension": dim,
            "search_type": search_type,
            "data": rows_sorted,
            "total_rows": len(rows_sorted),
        }, indent=2)

    except (ValueError, RuntimeError) as e:
        return f"❌ Error: {e}"
    except Exception as e:
        logger.exception("Unexpected error in gsc_search_analytics")
        return f"❌ Unexpected error: {e}"


@mcp.tool()
async def gsc_site_summary(site_url: str) -> str:
    """
    Get a coverage and indexing summary for a GSC property.

    Returns counts of indexed pages, pages with errors, warnings,
    and other coverage statistics from Google Search Console.

    Args:
        site_url: The verified property URL (e.g., "https://example.com/")
    """
    try:
        summary = await gsc_client.get_site_summary(site_url)
        raw = summary.get("data")

        if raw is None:
            return f"No summary data available for {site_url}."

        # Parse the gydQ5d response structure:
        # [[[count, [count, warnings, errors]], ...], False, 0, "site_url"]
        coverage_items = []
        if isinstance(raw, list) and len(raw) >= 1 and isinstance(raw[0], list):
            for item in raw[0]:
                if isinstance(item, list) and len(item) >= 2:
                    total = item[0]
                    details = item[1] if isinstance(item[1], list) else [item[1]]
                    valid = details[0] if len(details) > 0 else 0
                    warnings = details[1] if len(details) > 1 else 0
                    errors = details[2] if len(details) > 2 else 0
                    coverage_items.append({
                        "total_urls": total,
                        "valid": valid,
                        "warnings": warnings,
                        "errors": errors,
                    })

        if coverage_items:
            # Summarize across all coverage categories
            total_valid = sum(c["valid"] for c in coverage_items)
            total_warnings = sum(c["warnings"] for c in coverage_items)
            total_errors = sum(c["errors"] for c in coverage_items)

            return json.dumps({
                "site": site_url,
                "coverage_summary": {
                    "total_valid_pages": total_valid,
                    "total_warnings": total_warnings,
                    "total_errors": total_errors,
                    "coverage_categories": len(coverage_items),
                },
                "coverage_breakdown": coverage_items,
                "raw_data": str(raw)[:500],
            }, indent=2)

        return json.dumps({
            "site": site_url,
            "data": str(raw)[:800],
        }, indent=2)

    except RuntimeError as e:
        return f"❌ Error: {e}"
    except Exception as e:
        logger.exception("Unexpected error in gsc_site_summary")
        return f"❌ Unexpected error: {e}"


@mcp.tool()
async def gsc_list_sitemaps(site_url: str) -> str:
    """
    List all submitted sitemaps for a GSC property.

    Returns submitted sitemap URLs along with submitted, indexed, and error counts.

    Args:
        site_url: The verified property URL (e.g., "https://example.com/")
    """
    try:
        result = await gsc_client.get_sitemaps(site_url)

        sitemaps = result.get("sitemaps", [])
        submitted = result.get("submitted")
        indexed = result.get("indexed")
        errors = result.get("errors")

        return json.dumps({
            "site": site_url,
            "stats": {
                "submitted": submitted,
                "indexed": indexed,
                "errors": errors,
            },
            "sitemaps": sitemaps,
            "total": len(sitemaps),
        }, indent=2)

    except RuntimeError as e:
        return f"❌ Error: {e}"
    except Exception as e:
        logger.exception("Unexpected error in gsc_list_sitemaps")
        return f"❌ Unexpected error: {e}"


@mcp.tool()
async def gsc_insights(site_url: str) -> str:
    """
    Get Search Console Insights and notifications for a GSC property.

    Returns callouts/notifications such as branded query trends, filter alerts,
    and other Search Console insights surfaced by Google.

    Args:
        site_url: The verified property URL (e.g., "https://example.com/")
    """
    try:
        result = await gsc_client.get_insights(site_url)

        callouts = result.get("callouts", [])

        if not callouts:
            return json.dumps({
                "site": site_url,
                "message": "No insights or notifications found for this property.",
                "callouts": [],
            }, indent=2)

        # Make callout types human-readable
        type_labels = {
            "@BRANDED-CALLOUT@": "Branded query trend",
            "@INSIGHTS-SAN-FILTERED-BY-PAGE-CALLOUT@": "Data filtered by page",
            "@INSIGHTS-SAN-FILTERED-BY-QUERY-CALLOUT@": "Data filtered by query",
            "@INSIGHTS-SAN-FILTERED-BY-COUNTRY-CALLOUT@": "Data filtered by country",
            "@INSIGHTS-SAN-FILTERED-BY-SEARCH-TYPE-CALLOUT@": "Data filtered by search type",
        }

        formatted = []
        for c in callouts:
            callout_type = c.get("type", "")
            formatted.append({
                "type": callout_type,
                "label": type_labels.get(callout_type, callout_type),
                "priority": c.get("priority"),
                "date": c.get("date"),
                "counts": c.get("counts"),
            })

        return json.dumps({
            "site": site_url,
            "insights_count": len(formatted),
            "insights": formatted,
        }, indent=2)

    except RuntimeError as e:
        return f"❌ Error: {e}"
    except Exception as e:
        logger.exception("Unexpected error in gsc_insights")
        return f"❌ Unexpected error: {e}"


@mcp.tool()
async def gsc_all_queries(
    site_url: str,
    search_type: str = "WEB",
) -> str:
    """
    Extract ALL search queries from Google Search Console by scraping the
    performance page HTML. This bypasses the RPC pagination limitation and
    can return significantly more queries than gsc_top_queries.

    Args:
        site_url: The verified property URL (e.g., "https://example.com/")
        search_type: "WEB" (default), "IMAGE", "VIDEO", "NEWS"
    """
    try:
        result = await gsc_client.scrape_all_queries_from_html(
            site_url=site_url,
            search_type=search_type,
        )

        rows = result.get("rows", [])
        if not rows:
            return (
                f"No queries extracted from HTML for {site_url}.\n"
                "The site may have no search traffic, or the HTML structure may have changed. "
                "Try gsc_top_queries as a fallback."
            )

        rows_sorted = sorted(
            rows,
            key=lambda r: (r.get("clicks", 0), r.get("impressions", 0)),
            reverse=True,
        )

        return json.dumps({
            "site": site_url,
            "search_type": search_type,
            "queries": rows_sorted,
            "total": len(rows_sorted),
            "source": "html_scraping",
        }, indent=2)

    except RuntimeError as e:
        return f"❌ Error: {e}"
    except Exception as e:
        logger.exception("Unexpected error in gsc_all_queries")
        return f"❌ Unexpected error: {e}"


@mcp.tool()
async def gsc_index_coverage(site_url: str) -> str:
    """
    Get detailed index coverage statistics for a GSC property.

    Returns counts of indexed pages, pages with errors, warnings, excluded URLs,
    and other coverage categories from Google Search Console's index report.

    Args:
        site_url: The verified property URL (e.g., "https://example.com/")
    """
    try:
        result = await gsc_client.get_coverage_stats(site_url)
        raw = result.get("raw")

        if raw is None:
            return f"No index coverage data available for {site_url}."

        coverage_items = []
        if isinstance(raw, list):
            for item in raw if not isinstance(raw[0], list) else (raw[0] if raw else []):
                if isinstance(item, list) and len(item) >= 2:
                    total = item[0] if isinstance(item[0], (int, float)) else 0
                    details = item[1] if isinstance(item[1], list) else [item[1]]
                    valid = details[0] if len(details) > 0 and isinstance(details[0], (int, float)) else 0
                    warnings = details[1] if len(details) > 1 and isinstance(details[1], (int, float)) else 0
                    errors = details[2] if len(details) > 2 and isinstance(details[2], (int, float)) else 0
                    coverage_items.append({
                        "total_urls": total,
                        "valid": valid,
                        "warnings": warnings,
                        "errors": errors,
                    })

        if coverage_items:
            total_valid = sum(c["valid"] for c in coverage_items)
            total_warnings = sum(c["warnings"] for c in coverage_items)
            total_errors = sum(c["errors"] for c in coverage_items)

            return json.dumps({
                "site": site_url,
                "coverage_summary": {
                    "total_valid_pages": total_valid,
                    "total_warnings": total_warnings,
                    "total_errors": total_errors,
                    "categories": len(coverage_items),
                },
                "coverage_breakdown": coverage_items,
            }, indent=2)

        return json.dumps({
            "site": site_url,
            "raw_data": str(raw)[:800],
        }, indent=2)

    except RuntimeError as e:
        return f"❌ Error: {e}"
    except Exception as e:
        logger.exception("Unexpected error in gsc_index_coverage")
        return f"❌ Unexpected error: {e}"


@mcp.tool()
async def gsc_query_pages(
    site_url: str,
    search_type: str = "WEB",
    limit: int = 50,
) -> str:
    """
    Get query-to-page correlations from Google Search Console.

    Shows which pages rank for which queries, with clicks, impressions, CTR,
    and average position for each query+page combination.

    Args:
        site_url: The verified property URL (e.g., "https://example.com/")
        search_type: "WEB" (default), "IMAGE", "VIDEO", "NEWS"
        limit: Max rows to return (default 50, use 0 for all)
    """
    try:
        result = await gsc_client.query_search_analytics(
            site_url=site_url,
            dimensions=["query", "page"],
            search_type=search_type,
        )

        rows = result.get("rows", [])
        if not rows:
            return (
                f"No query-page data found for {site_url}.\n"
                "The site may have insufficient traffic for multi-dimension breakdowns."
            )

        rows_sorted = sorted(
            rows,
            key=lambda r: (r.get("clicks", 0), r.get("impressions", 0)),
            reverse=True,
        )

        if limit > 0:
            rows_sorted = rows_sorted[:limit]

        return json.dumps({
            "site": site_url,
            "search_type": search_type,
            "query_pages": rows_sorted,
            "total_shown": len(rows_sorted),
            "total_available": len(rows),
        }, indent=2)

    except RuntimeError as e:
        return f"❌ Error: {e}"
    except Exception as e:
        logger.exception("Unexpected error in gsc_query_pages")
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

        # Handle case where Bing returns a list instead of dict
        if isinstance(stats, list):
            if len(stats) == 0:
                return f"No crawl stats found for {site_url}."
            stats = stats[0]  # Take first item

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


@mcp.tool()
async def bing_url_info(
    site_url: str,
    page_url: str,
) -> str:
    """
    Get detailed information about a specific URL from Bing Webmaster Tools.

    Returns crawl date, HTTP status code, indexed status, and other URL details.

    Args:
        site_url: The site URL as it appears in Bing Webmaster Tools
                  (e.g., "https://example.com/")
        page_url: The specific page URL to inspect
                  (e.g., "https://example.com/about")
    """
    try:
        info = await bing_client.get_url_info(site_url=site_url, page_url=page_url)

        if not info:
            return f"No URL info found for {page_url} in Bing."

        result = {
            "site": site_url,
            "url": page_url,
            "crawlDate": info.get("CrawlDate", info.get("crawlDate", "")),
            "httpStatusCode": info.get("HttpStatusCode", info.get("httpStatusCode", 0)),
            "isIndexed": info.get("IsIndexed", info.get("isIndexed", False)),
            "lastCrawled": info.get("LastCrawled", info.get("lastCrawled", "")),
        }

        for key in ("InLinks", "InternalLinks", "FetchedDate", "DiscoveredDate"):
            val = info.get(key) or info.get(key[0].lower() + key[1:])
            if val is not None:
                result[key] = val

        return json.dumps(result, indent=2)

    except RuntimeError as e:
        return f"❌ Error: {e}"
    except Exception as e:
        logger.exception("Unexpected error in bing_url_info")
        return f"❌ Unexpected error: {e}"


@mcp.tool()
async def bing_page_stats(
    site_url: str,
    limit: int = 100,
) -> str:
    """
    Get top page statistics from Bing Webmaster Tools.

    Returns the top pages with impressions, clicks, and average click position.

    Args:
        site_url: The site URL as it appears in Bing Webmaster Tools
                  (e.g., "https://example.com/")
        limit: Maximum number of pages to return (default 100)
    """
    try:
        rows = await bing_client.get_page_stats(site_url=site_url)

        if not rows:
            return f"No page stats found for {site_url} in Bing."

        formatted = []
        for row in rows:
            formatted.append({
                "url": row.get("Url", row.get("url", "")),
                "impressions": row.get("Impressions", row.get("impressions", 0)),
                "clicks": row.get("Clicks", row.get("clicks", 0)),
                "avgClickPosition": row.get("AvgClickPosition", row.get("avgClickPosition", 0)),
            })

        formatted.sort(key=lambda x: x.get("clicks", 0), reverse=True)
        formatted = formatted[:limit]

        return json.dumps({
            "site": site_url,
            "pages": formatted,
            "total": len(formatted),
        }, indent=2)

    except RuntimeError as e:
        return f"❌ Error: {e}"
    except Exception as e:
        logger.exception("Unexpected error in bing_page_stats")
        return f"❌ Unexpected error: {e}"


@mcp.tool()
async def bing_submit_url(
    site_url: str,
    url: str,
) -> str:
    """
    Submit a single URL to Bing for indexing.

    Use this to request Bing to crawl and index a specific page.
    Check your submission quota first with bing_url_submission_quota.

    Args:
        site_url: The site URL as it appears in Bing Webmaster Tools
                  (e.g., "https://example.com/")
        url: The page URL to submit for indexing
             (e.g., "https://example.com/new-page")
    """
    try:
        await bing_client.submit_url(site_url=site_url, url=url)
        return json.dumps({
            "status": "submitted",
            "site": site_url,
            "url": url,
            "message": f"URL {url} has been submitted to Bing for indexing.",
        }, indent=2)

    except RuntimeError as e:
        return f"❌ Error: {e}"
    except Exception as e:
        logger.exception("Unexpected error in bing_submit_url")
        return f"❌ Unexpected error: {e}"


@mcp.tool()
async def bing_submit_url_batch(
    site_url: str,
    urls: str,
) -> str:
    """
    Submit multiple URLs to Bing for indexing in a single batch.

    Use this to request Bing to crawl and index multiple pages at once.
    Check your submission quota first with bing_url_submission_quota.

    Args:
        site_url: The site URL as it appears in Bing Webmaster Tools
                  (e.g., "https://example.com/")
        urls: Comma-separated list of page URLs to submit
              (e.g., "https://example.com/page1,https://example.com/page2")
    """
    try:
        url_list = [u.strip() for u in urls.split(",") if u.strip()]
        if not url_list:
            return "❌ No valid URLs provided. Pass comma-separated URLs."

        await bing_client.submit_url_batch(site_url=site_url, urls=url_list)
        return json.dumps({
            "status": "submitted",
            "site": site_url,
            "urls_submitted": url_list,
            "count": len(url_list),
            "message": f"{len(url_list)} URLs submitted to Bing for indexing.",
        }, indent=2)

    except RuntimeError as e:
        return f"❌ Error: {e}"
    except Exception as e:
        logger.exception("Unexpected error in bing_submit_url_batch")
        return f"❌ Unexpected error: {e}"


@mcp.tool()
async def bing_crawl_issues(site_url: str) -> str:
    """
    Get crawl issues and errors for a site from Bing Webmaster Tools.

    Returns a list of crawl issues Bing encountered when crawling your site,
    including HTTP errors, DNS issues, robots.txt blocks, and more.

    Args:
        site_url: The site URL as it appears in Bing Webmaster Tools
                  (e.g., "https://example.com/")
    """
    try:
        issues = await bing_client.get_crawl_issues(site_url=site_url)

        if not issues:
            return json.dumps({
                "site": site_url,
                "message": "No crawl issues found — your site is healthy!",
                "issues": [],
                "total": 0,
            }, indent=2)

        formatted = []
        for issue in issues:
            formatted.append({
                "url": issue.get("Url", issue.get("url", "")),
                "issueCode": issue.get("IssueCode", issue.get("issueCode", "")),
                "severity": issue.get("Severity", issue.get("severity", "")),
                "lastCrawled": issue.get("LastCrawled", issue.get("lastCrawled", "")),
                "httpCode": issue.get("HttpCode", issue.get("httpCode", 0)),
            })

        return json.dumps({
            "site": site_url,
            "issues": formatted,
            "total": len(formatted),
        }, indent=2)

    except RuntimeError as e:
        return f"❌ Error: {e}"
    except Exception as e:
        logger.exception("Unexpected error in bing_crawl_issues")
        return f"❌ Unexpected error: {e}"


@mcp.tool()
async def bing_url_submission_quota(site_url: str) -> str:
    """
    Check your daily URL submission quota in Bing Webmaster Tools.

    Shows how many URLs you can still submit today for indexing.

    Args:
        site_url: The site URL as it appears in Bing Webmaster Tools
                  (e.g., "https://example.com/")
    """
    try:
        quota = await bing_client.get_url_submission_quota(site_url=site_url)

        if not quota:
            return f"No quota information available for {site_url}."

        return json.dumps({
            "site": site_url,
            "dailyQuota": quota.get("DailyQuota", quota.get("dailyQuota", 0)),
            "monthlyQuota": quota.get("MonthlyQuota", quota.get("monthlyQuota", 0)),
        }, indent=2)

    except RuntimeError as e:
        return f"❌ Error: {e}"
    except Exception as e:
        logger.exception("Unexpected error in bing_url_submission_quota")
        return f"❌ Unexpected error: {e}"


@mcp.tool()
async def bing_link_counts(site_url: str) -> str:
    """
    Get inbound link counts for a site from Bing Webmaster Tools.

    Returns the number of inbound links Bing has discovered pointing to your site.

    Args:
        site_url: The site URL as it appears in Bing Webmaster Tools
                  (e.g., "https://example.com/")
    """
    try:
        data = await bing_client.get_link_counts(site_url=site_url)

        if not data:
            return f"No link data found for {site_url} in Bing."

        if isinstance(data, list):
            return json.dumps({
                "site": site_url,
                "links": data,
                "total_entries": len(data),
            }, indent=2)

        return json.dumps({
            "site": site_url,
            "linkData": data,
        }, indent=2)

    except RuntimeError as e:
        return f"❌ Error: {e}"
    except Exception as e:
        logger.exception("Unexpected error in bing_link_counts")
        return f"❌ Unexpected error: {e}"


# ─── Utility Tools ────────────────────────────────────────────────────────────

@mcp.tool()
async def refresh_google_session() -> str:
    """
    Force refresh the cached Google Chrome cookies.

    Use this if you've recently logged back in to Google in Chrome
    and GSC tools are still showing authentication errors.
    Also clears the cached XSRF token.

    No parameters required.
    """
    try:
        clear_cookie_cache()
        # Clear XSRF cache too
        from .clients.gsc_client import _xsrf_cache
        _xsrf_cache["token"] = None
        _xsrf_cache["expires"] = 0.0

        from .extractors.chrome_cookies import get_google_cookies
        cookies = get_google_cookies(force_refresh=True)
        return (
            f"✅ Google session refreshed. "
            f"Found {len(cookies)} cookies from Chrome. "
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
