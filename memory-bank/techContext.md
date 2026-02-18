# Tech Context

## Technology Stack

### Runtime
- **Python 3.11+** (required for modern type hints and FastMCP)
- **uv / uvx** — package manager for distribution (users need this)

### Core Dependencies (3 packages only)
| Package | Version | Purpose |
|---------|---------|---------|
| `mcp` | >=1.0.0 | FastMCP framework for MCP server (stdio transport) |
| `rookiepy` | >=0.5.0 | Rust-based Chrome cookie extractor (cross-platform, AES-GCM) |
| `httpx` | >=0.27.0 | Async HTTP client for batchexecute + Bing API calls |

---

## Google Search Console Authentication (v0.2.0)

### Overview
GSC uses Google's internal `batchexecute` RPC protocol. Authentication requires:
1. Chrome session cookies (extracted by `rookiepy`)
2. SAPISIDHASH header (computed from `SAPISID` cookie)
3. XSRF token (auto-fetched from a probe request)

### SAPISIDHASH
```python
import hashlib, time
unix_ts = int(time.time())
sha1 = hashlib.sha1(f"{unix_ts} {SAPISID} https://search.google.com".encode()).hexdigest()
header = f"SAPISIDHASH {unix_ts}_{sha1}"
```

### XSRF Token
- POST to batchexecute WITHOUT `&at=` → get 400 response
- Parse body for `"xsrf","TOKEN"` pattern
- Cache for 1 hour; re-fetch on next failure

### batchexecute Endpoint
```
POST https://search.google.com/_/SearchConsoleAggReportUi/data/batchexecute
Content-Type: application/x-www-form-urlencoded;charset=UTF-8
Authorization: SAPISIDHASH {ts}_{sha1}
Body: f.req=[[["rpcId","argsJsonString",null,"1"]]]&at=XSRF_TOKEN
```

### Response Format
Chunked streaming format:
```
DECIMAL_BYTECOUNT\n
[JSON_ARRAY]\n
```
Each JSON array item: `["wrb.fr", "RPC_ID", "data_json_string", null, null, null, "seq"]`

### RPC IDs
| ID | Purpose | Args Pattern |
|----|---------|-------------|
| `OLiH4d` | Date time series | `["url", period, date_filter, null, null, [query_opts], null, null, [null, 2]]` |
| `gydQ5d` | Site summary/coverage | `["url"]` |
| `nDAfwb` | Dimension breakdown | `["url", period, date_filter, null, null, [query_opts]]` |
| `czrWJf` | Index coverage stats | `["url", 9]` |
| `SM7Bqb` | List sites | `[[1, []]]` (returns [] without localStorage) |
| `B2IOAd` | Stats panel | `["url", [[7]]]` |
| `mKtLlc` | Property summary | `["url"]` |
| `xDwXKd` | Sitemaps list | `["url", 7]` |
| `oGVhvf` | Insights/callouts | `["url"]` |

### Dimension Codes (nDAfwb) — v0.2.0+
```python
DIMENSIONS = {
    "query": [2],
    "page": [3],   # was [4] — [4] is country
    "country": [4],
    "device": [4], # no dedicated device code; falls back to country
    "search_appearance": [7],
    "date": [8],
}
```
Dimension values: query at dim_info[0], page URL at dim_info[40], country at dim_info[17] (dict `{"519508101": ["code"]}`). Use `_extract_dim_value(dim_info, dim_name)`.

### Date Range Support (v0.2.0)
- GSC batchexecute does **not** accept custom date range in RPC (args[2] date filter returns empty).
- **Client-side filtering**: Fetch full OLiH4d with period=27, then filter rows by start_date/end_date in `_filter_rows_by_date()`.

### nDAfwb Parser (v0.2.0+)
Response shapes: A `raw[1][0]` list of rows; B/C with extra nesting. Unwrap then `_parse_single_row(row_data, dimensions)`.
- **Metric extraction**: `_extract_metric_value()` — value at [1] for integers; for CTR/position (type 7/8) scan indices > 8 only (index 8 is type code, not value).
- **Metric type**: In `_parse_single_row()`, require `isinstance(metric_array[8], int)` before comparing to 5/6/7/8.

---

## rookiepy Cookie Extraction

### Field Names
```python
{
    "name": str,
    "value": str,
    "domain": str,
    "path": str,
    "secure": bool,
    "http_only": bool,
    "same_site": int,   # -1/0=None, 1=Lax, 2=Strict
    "expires": str,     # epoch seconds as STRING
}
```

### Multi-Browser Auto-Detection
```python
# Priority: Chrome → Brave → Edge
# Env overrides: BROWSER=chrome/brave/edge, CHROME_PROFILE=/path
```

---

## Bing Webmaster API

### Authentication
- Free API key from `bing.com/webmasters` → Settings → API Access
- Query param: `?apikey={key}`
- Env var: `BING_API_KEY`

### Endpoints Used (v0.2.0)
```
Base: https://ssl.bing.com/webmaster/api.svc/json/

GET  GetUserSites              — List all sites
GET  GetRankAndTrafficStats    — Search performance by date
GET  GetKeywordStats           — Keyword performance
GET  GetCrawlStats             — Crawl statistics
GET  GetUrlInfo                — URL inspection
GET  GetPageStats              — Top pages with traffic
POST SubmitUrl                 — Submit single URL for indexing
POST SubmitUrlBatch            — Submit batch of URLs for indexing
GET  GetCrawlIssues            — Crawl issues/errors
GET  GetUrlSubmissionQuota     — URL submission quota
GET  GetLinkCounts             — Inbound link counts
```

---

## Distribution

### Package Structure
```
gsc_bing_mcp/
├── __init__.py              # __version__ = "0.2.1"
├── server.py                # FastMCP server — 23 tools
├── clients/
│   ├── __init__.py
│   ├── gsc_client.py        # batchexecute RPC + HTML scraping (gsc_all_queries)
│   └── bing_client.py       # Bing API client (11 endpoints)
└── extractors/
    ├── __init__.py
    ├── chrome_cookies.py     # rookiepy wrapper + multi-browser
    └── sapisidhash.py        # SAPISIDHASH generator
```

### User Install & MCP Config
```bash
uvx gsc-bing-mcp   # or: pip install gsc-bing-mcp && gsc-bing-mcp
```

```json
{
  "mcpServers": {
    "gsc-bing-mcp": {
      "command": "uvx",
      "args": ["gsc-bing-mcp"],
      "env": {
        "BING_API_KEY": "your-bing-api-key-here"
      }
    }
  }
}
```

### Optional Env Vars
```bash
BROWSER=brave           # override browser (chrome/brave/edge)
CHROME_PROFILE=/path    # override profile path
BING_API_KEY=xxx        # Bing API key
```

---

## Platform Notes

### macOS
- Chrome: `~/Library/Application Support/Google/Chrome/`
- rookiepy reads macOS Keychain for AES decryption key automatically

### Windows
- Chrome: `%LOCALAPPDATA%\Google\Chrome\User Data\`
- rookiepy uses Windows DPAPI

### Linux
- Chrome: `~/.config/google-chrome/`
- rookiepy uses Gnome Keyring or kwallet
