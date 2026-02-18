# Active Context

## Current Work Focus
v0.2.1 — Bugfix release. 23 tools total (11 GSC + 11 Bing + 1 util). MCP verified live with gsc_list_sites, gsc_top_queries, gsc_top_pages, gsc_all_queries.

## Session Summary (2026-02-18 — v0.2.0 → v0.2.1)

### v0.2.1 Bugfixes (2026-02-18)
- **Device dimension**: `_extract_dim_value()` no longer short-circuits on falsy strings — check `isinstance(dim_info[0], str)` only (avoids skipping valid values like `"0"`).
- **Metric type validation**: In `_parse_single_row()`, validate `metric_array[8]` is `int` before comparing to 5/6/7/8; skip invalid entries to avoid silent data loss.
- **gsc_index_coverage loop**: Replaced invalid `for item in raw if ... else ...` with `items_to_iterate = ... ; for item in items_to_iterate:` (valid Python).

### v0.2.0 Major Changes (2026-02-18)
- **Dimension codes**: page=[3], country=[4] (were incorrectly swapped; page was [4] returning country data).
- **Dimension value extraction**: Added `_extract_dim_value()` — query at dim_info[0], page at dim_info[40], country at dim_info[17] (dict format).
- **Metric extraction**: `_extract_metric_value()` skips index 8 (metric type code) when scanning for CTR/position to avoid returning 7.0/8.0 as values.
- **Date range**: Client-side filtering only; GSC batchexecute does not accept custom date range in request — fetch full OLiH4d then filter rows by start_date/end_date.
- **gsc_all_queries**: Scans all AF_initDataCallback blocks for dimension code [2], uses `_parse_ndafwb_breakdown(data, ["query"])` on the matching block (e.g. ds:17).

#### New GSC Tools (+3)
- `gsc_all_queries` — All queries from performance page HTML (ds:17 block).
- `gsc_index_coverage` — Index coverage via czrWJf.
- `gsc_query_pages` — Query-to-page via nDAfwb [query, page].

#### New Bing Tools (+7)
- `bing_url_info`, `bing_page_stats`, `bing_submit_url`, `bing_submit_url_batch`, `bing_crawl_issues`, `bing_url_submission_quota`, `bing_link_counts`.

#### Existing Tool Improvements
- `gsc_list_sites` — Includes `propertyType` (Domain property vs URL prefix).
- All GSC performance tools support optional `start_date`/`end_date` (client-side filter for trends).

### MCP Verification (2026-02-18)
- **gsc_list_sites**: 16 properties with propertyType.
- **gsc_top_queries** (nextgenlearning.dev): 20 shown, 387 total; correct CTR/position.
- **gsc_top_pages** (nextgenlearning.dev): 10 shown, 305 total; real page URLs.
- **gsc_all_queries** (nextgenlearning.dev): 387 queries, source html_scraping.
- **gsc_all_queries** (kitovo.app): 529 queries, receipt/invoice-themed.
