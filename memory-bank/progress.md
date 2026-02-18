# Progress

## ✅ COMPLETED — v0.2.1

### PyPI: https://pypi.org/project/gsc-bing-mcp/
### GitHub: https://github.com/codermillat/gsc-bing-mcp

---

## What Works (v0.2.1)

### Tool Count: 23 total (11 GSC + 11 Bing + 1 util)

### GSC Tools (11) — batchexecute RPC (no OAuth, no GCP)
| Tool | RPC / Source | Status |
|------|----------------|--------|
| `gsc_list_sites` | HTML scraping | ✅ Working — includes propertyType |
| `gsc_performance_trend` | OLiH4d | ✅ Working — + client-side date range |
| `gsc_top_queries` | nDAfwb dim=[2] | ✅ Working — + date range, limit=0 for all |
| `gsc_top_pages` | nDAfwb dim=[3] | ✅ Working — + date range, limit=0; real URLs |
| `gsc_search_analytics` | nDAfwb multi-dim | ✅ Working — + date range |
| `gsc_site_summary` | gydQ5d | ✅ Working |
| `gsc_list_sitemaps` | xDwXKd | ✅ Working |
| `gsc_insights` | oGVhvf | ✅ Working |
| `gsc_all_queries` | HTML (ds:17) | ✅ Working — all queries from performance page |
| `gsc_index_coverage` | czrWJf | ✅ Working — index coverage stats |
| `gsc_query_pages` | nDAfwb [2,3] | ✅ Working — query-to-page |
| `refresh_google_session` | — | ✅ Working |

### Bing Tools (11)
| Tool | Endpoint | Status |
|------|----------|--------|
| `bing_list_sites` | GetUserSites | ✅ Working |
| `bing_search_analytics` | GetRankAndTrafficStats | ✅ Working |
| `bing_keyword_stats` | GetKeywordStats | ✅ Working |
| `bing_crawl_stats` | GetCrawlStats | ✅ Working |
| `bing_url_info` | GetUrlInfo | ✅ Working |
| `bing_page_stats` | GetPageStats | ✅ Working |
| `bing_submit_url` | SubmitUrl | ✅ Working |
| `bing_submit_url_batch` | SubmitUrlBatch | ✅ Working |
| `bing_crawl_issues` | GetCrawlIssues | ✅ Working |
| `bing_url_submission_quota` | GetUrlSubmissionQuota | ✅ Working |
| `bing_link_counts` | GetLinkCounts | ✅ Working |

### Infrastructure
- SAPISIDHASH auth, rookiepy Chrome cookie extraction ✅
- Multi-browser: Chrome → Brave → Edge; env overrides BROWSER, CHROME_PROFILE ✅
- XSRF token auto-fetch; batchexecute chunked parser ✅
- nDAfwb: correct dimension codes (query=2, page=3, country=4), _extract_dim_value, metric_type int check ✅
- Date range: client-side filter on OLiH4d results ✅
- gsc_all_queries: scan HTML for [2] block, reuse _parse_ndafwb_breakdown ✅

## Current MCP Config (Cursor/Cline)
```json
"gsc-bing-mcp": {
  "command": "uvx",
  "args": ["gsc-bing-mcp"],
  "env": { "BING_API_KEY": "your-bing-api-key-here" }
}
```

---

## Version History
| Version | Date | Notes |
|---------|------|-------|
| 0.1.0 | 2026-02-18 | Initial release |
| 0.1.1 | 2026-02-18 | Batchexecute attempt |
| 0.1.2–0.1.6 | 2026-02-18 | Iterative fixes |
| 0.2.0 | 2026-02-18 | **Major: 23 tools, dimension/parser fixes, date range, new Bing** |
| 0.2.1 | 2026-02-18 | **Bugfix: device falsy check, metric_type validation, index_coverage loop syntax** |

---

## Known Limitations
- nDAfwb on very low-traffic sites may return limited rows
- Chrome cookie DB must not be locked (close Chrome or use separate profile)
- SAPISIDHASH is internal; could break if Google changes auth
- Bing requires free API key from bing.com/webmasters
- GSC data ~2–3 day lag

## What's Left to Build (Future)
- gsc_inspect_url (if RPC discovered)
- Firefox cookie fallback
- Multi-account / profile selector
- Export CSV/JSON
- Bing feed / keyword research tools
