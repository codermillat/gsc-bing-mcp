# Active Context

## Current Work Focus
v0.2.0 — Major enhancement: 22 tools total (12 GSC + 10 Bing), date range support, robust parser, new Bing endpoints.

## Session Summary (2026-02-18 — v0.2.0 Release)

### What Changed

#### Infrastructure Fixes
- Fixed version mismatch (`__init__.py` was `0.1.1`, now synced to `0.2.0`)
- Rewrote `_parse_ndafwb_breakdown()` with robust multi-row extraction
- Added `_extract_metric_value()` helper that scans arrays for actual values instead of fragile index-based access
- Added `_parse_single_row()` for clean row parsing with proper unwrapping of nested shapes

#### Date Range Support
- Added `start_date` / `end_date` optional params to `query_search_analytics()`
- Added `_date_to_timestamp_ms()` and `_build_date_filter()` helpers
- Propagated date range params to all 4 GSC performance tools:
  - `gsc_performance_trend`, `gsc_top_queries`, `gsc_top_pages`, `gsc_search_analytics`

#### New GSC Tools (+3)
- `gsc_all_queries` — Scrapes ALL queries from GSC performance page HTML (bypasses RPC pagination)
- `gsc_index_coverage` — Detailed index coverage stats via `czrWJf` RPC
- `gsc_query_pages` — Query-to-page correlations via multi-dimension `nDAfwb` breakdown

#### New Bing Tools (+7)
- `bing_url_info` — URL inspection (crawl date, HTTP status, indexed status)
- `bing_page_stats` — Top pages with traffic metrics
- `bing_submit_url` — Submit single URL for indexing
- `bing_submit_url_batch` — Submit multiple URLs for indexing
- `bing_crawl_issues` — Crawl issues and errors
- `bing_url_submission_quota` — Check daily URL submission quota
- `bing_link_counts` — Inbound link data

#### Existing Tool Improvements
- `gsc_top_pages` — Now supports `limit=0` to return all pages
- `gsc_list_sites` — Now includes `propertyType` (Domain property vs URL prefix)
