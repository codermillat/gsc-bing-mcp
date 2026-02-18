# Progress

## ✅ COMPLETED — v0.2.0

### PyPI: https://pypi.org/project/gsc-bing-mcp/
### GitHub: https://github.com/codermillat/gsc-bing-mcp

---

## What Works (v0.2.0)

### GSC Tools (12 total) — batchexecute RPC (no OAuth, no GCP)
| Tool | RPC | Status |
|------|-----|--------|
| `gsc_list_sites` | HTML scraping | ✅ Working — includes propertyType |
| `gsc_performance_trend` | OLiH4d | ✅ Working — + date range support |
| `gsc_top_queries` | nDAfwb dim=[2] | ✅ Working — + date range, limit=0 for all |
| `gsc_top_pages` | nDAfwb dim=[4] | ✅ Working — + date range, limit=0 for all |
| `gsc_search_analytics` | nDAfwb multi-dim | ✅ Working — + date range |
| `gsc_site_summary` | gydQ5d | ✅ Working |
| `gsc_list_sitemaps` | xDwXKd | ✅ Working |
| `gsc_insights` | oGVhvf | ✅ Working |
| `gsc_all_queries` | HTML scraping | ✅ **NEW** — scrapes all queries from performance page |
| `gsc_index_coverage` | czrWJf | ✅ **NEW** — detailed index coverage stats |
| `gsc_query_pages` | nDAfwb [2,4] | ✅ **NEW** — query-to-page correlations |
| `refresh_google_session` | — | ✅ Working |

### Bing Tools (10 total)
| Tool | Endpoint | Status |
|------|----------|--------|
| `bing_list_sites` | GetUserSites | ✅ Working |
| `bing_search_analytics` | GetRankAndTrafficStats | ✅ Working |
| `bing_keyword_stats` | GetKeywordStats | ✅ Working |
| `bing_crawl_stats` | GetCrawlStats | ✅ Working |
| `bing_url_info` | GetUrlInfo | ✅ **NEW** — URL inspection |
| `bing_page_stats` | GetPageStats | ✅ **NEW** — top pages with traffic |
| `bing_submit_url` | SubmitUrl | ✅ **NEW** — submit URL for indexing |
| `bing_submit_url_batch` | SubmitUrlBatch | ✅ **NEW** — batch submit URLs |
| `bing_crawl_issues` | GetCrawlIssues | ✅ **NEW** — crawl errors/issues |
| `bing_url_submission_quota` | GetUrlSubmissionQuota | ✅ **NEW** — check quota |
| `bing_link_counts` | GetLinkCounts | ✅ **NEW** — inbound link data |

### Infrastructure
- SAPISIDHASH auth (SHA1 based, no OAuth) ✅
- rookiepy Chrome cookie extraction ✅
- Multi-browser auto-detect: Chrome → Brave → Edge ✅
- Env var overrides: `BROWSER`, `CHROME_PROFILE` ✅
- XSRF token auto-fetch from 400 error ✅
- batchexecute response parser (chunked streaming + wrb.fr) ✅
- 5-minute in-memory cache for cookies + XSRF ✅
- Robust nDAfwb parser with multi-shape unwrapping ✅
- Date range support on GSC performance tools ✅

## Current MCP Config (Cline)
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
| 0.1.0 | 2026-02-18 | Initial release — used wrong GSC API (404s) |
| 0.1.1 | 2026-02-18 | First batchexecute attempt (incomplete) |
| 0.1.2 | 2026-02-18 | Full batchexecute rewrite — real data working |
| 0.1.4 | 2026-02-18 | HTML scraping for gsc_list_sites |
| 0.1.5 | 2026-02-18 | Fixed bing_crawl_stats list handling |
| 0.1.6 | 2026-02-18 | Fixed query/page data extraction |
| 0.2.0 | 2026-02-18 | **Major: 22 tools, date range, new Bing endpoints, robust parser** |

---

## Known Limitations
- `nDAfwb` on very low-traffic sites may only return aggregate totals
- Chrome must not have Cookies SQLite DB locked (close Chrome or use separate profile)
- SAPISIDHASH is an internal Google technique — could break if Google changes auth
- Bing API key must be manually obtained from bing.com/webmasters
- GSC data has ~2-3 day lag

## What's Left to Build (Future)

### v0.3.0 Ideas
- `gsc_inspect_url` — URL inspection RPC (not yet discovered)
- Firefox cookie support as fallback
- Multi-account Google support (profile selector)
- Export to CSV/JSON option
- Bing feed management tools (SubmitFeed, GetFeeds)
- Bing keyword research tools (GetRelatedKeywords)
