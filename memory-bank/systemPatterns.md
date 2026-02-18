# System Patterns

## Architecture Overview

```
AI Agent (Claude/Cline)
     │ MCP Protocol (stdio)
     ▼
FastMCP Server (server.py)
     ├── GSC Tools → gsc_client.py → SAPISIDHASH auth → search.google.com (batchexecute)
     └── Bing Tools → bing_client.py → API key auth → ssl.bing.com/webmaster/api.svc/json
                              ↑                              ↑
                    extractors/chrome_cookies.py    BING_API_KEY env var
                    extractors/sapisidhash.py
```

## Key Design Patterns

### 1. Cookie Extraction with TTL Cache
- `rookiepy.chrome(["google.com"])` reads Chrome's SQLite cookie DB from disk
- Results cached for 5 minutes to avoid repeated disk reads
- Chrome does NOT need to be running — reads the file directly
- Chrome MUST be closed or the SQLite DB may be locked (handled gracefully)

### 2. SAPISIDHASH Authentication
- Formula: `SHA1(f"{timestamp} {SAPISID} {origin}")`
- Authorization header: `SAPISIDHASH {timestamp}_{hex_digest}`
- Origin for GSC: `https://search.google.com`
- Timestamp is Unix seconds (not milliseconds, despite some docs saying ms — use seconds)
- Additional required cookies in Cookie header: `SAPISID`, `__Secure-1PSID`, `__Secure-3PAPISID`, `SID`, `HSID`, `SSID`, `APISID`

### 3. Bing API Pattern
- Base URL: `https://ssl.bing.com/webmaster/api.svc/json/`
- All requests: GET with `?apikey={key}` query param
- Key sourced from `os.environ["BING_API_KEY"]`

### 4. MCP Transport: stdio
- FastMCP with `mcp.run()` — stdio transport (default)
- Launched by MCP client (Cline/Claude Desktop) as subprocess
- Each user runs their own local instance

### 5. Error Handling Pattern
- Cookie not found → Clear message: "Please ensure you are logged in to Google in Chrome"
- API 401 → "Session expired. Please log in to Google in Chrome and try again."
- API 429 → "Rate limited. Please wait a moment and try again."
- Missing Bing key → "Please set BING_API_KEY in your MCP server environment config"

## Project Structure
```
gsc_bing_mcp/
├── __init__.py
├── server.py              # FastMCP entry point, all @mcp.tool() registrations
├── extractors/
│   ├── __init__.py
│   ├── chrome_cookies.py  # rookiepy wrapper + TTL cache
│   └── sapisidhash.py     # SAPISIDHASH generator + GSC header builder
├── clients/
│   ├── __init__.py
│   ├── gsc_client.py      # GSC API methods
│   └── bing_client.py     # Bing Webmaster API methods
pyproject.toml             # PyPI package config
requirements.txt           # mcp, rookiepy, httpx
README.md
```

## GSC API (batchexecute — no official API key)
```
POST https://search.google.com/_/SearchConsoleAggReportUi/data/batchexecute
     Body: f.req=[[["rpcId","argsJson",null,"1"]]]&at=XSRF_TOKEN
     → All GSC data via RPCs: OLiH4d (trends), nDAfwb (queries/pages/country), gydQ5d, xDwXKd, oGVhvf, czrWJf, etc.
     → Site list via HTML scraping of search-console welcome page
```

## Bing API Endpoints Used
```
GET https://ssl.bing.com/webmaster/api.svc/json/GetUserSites?apikey={key}
    → Lists all sites

GET https://ssl.bing.com/webmaster/api.svc/json/GetRankAndTrafficStats?siteUrl={url}&apikey={key}
    → Traffic and ranking data

GET https://ssl.bing.com/webmaster/api.svc/json/GetCrawlStats?siteUrl={url}&apikey={key}
    → Crawl statistics

GET https://ssl.bing.com/webmaster/api.svc/json/GetKeyword?siteUrl={url}&query={q}&apikey={key}
    → Keyword data
```

## Cookie Cache Design
```python
_cookie_cache = {
    "google": {"data": None, "expires": 0},
    "bing": {"data": None, "expires": 0}
}
CACHE_TTL = 300  # 5 minutes
```
