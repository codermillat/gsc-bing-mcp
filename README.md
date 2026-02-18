# gsc-bing-mcp

An MCP (Model Context Protocol) server that gives AI agents (Claude, Cline) direct access to your **Google Search Console** and **Bing Webmaster Tools** search performance data.

**Zero API keys for Google** — uses your existing Chrome browser session.  
**30-second setup for Bing** — just copy one free key from your dashboard.

> **v0.2.1** — 23 tools total (11 GSC + 11 Bing + 1 utility)

---

## ✨ Features

### Google Search Console Tools (11)

| Tool | Description |
|------|-------------|
| `gsc_list_sites` | List all verified GSC properties |
| `gsc_performance_trend` | Daily clicks, impressions, CTR, position trend |
| `gsc_top_queries` | Top search queries by clicks |
| `gsc_top_pages` | Top landing pages by clicks |
| `gsc_search_analytics` | Analytics grouped by query, page, country, or device |
| `gsc_site_summary` | Coverage & indexing summary |
| `gsc_list_sitemaps` | Submitted sitemaps with status and error counts |
| `gsc_insights` | Search Console notifications and callouts |
| `gsc_all_queries` | All queries from performance page HTML (bypasses pagination) |
| `gsc_index_coverage` | Detailed index coverage statistics |
| `gsc_query_pages` | Query-to-page correlation data |

### Bing Webmaster Tools (11)

| Tool | Description |
|------|-------------|
| `bing_list_sites` | List all Bing Webmaster properties |
| `bing_search_analytics` | Daily impressions, clicks, and position |
| `bing_keyword_stats` | Top keywords by clicks |
| `bing_crawl_stats` | Crawl statistics, errors, and blocked URLs |
| `bing_url_info` | Crawl date, HTTP status, and indexing info for a URL |
| `bing_page_stats` | Top pages with impressions and clicks |
| `bing_submit_url` | Submit a single URL to Bing for indexing |
| `bing_submit_url_batch` | Submit multiple URLs to Bing in one batch |
| `bing_crawl_issues` | Crawl errors and issues Bing encountered |
| `bing_url_submission_quota` | Remaining daily URL submission quota |
| `bing_link_counts` | Inbound link counts discovered by Bing |

### Utility (1)

| Tool | Description |
|------|-------------|
| `refresh_google_session` | Force-refresh cached Chrome cookies |

---

## 🔐 How Authentication Works

### Google Search Console — Zero Setup

This server reads your Chrome browser's cookies directly from disk — the same way tools like [yt-dlp](https://github.com/yt-dlp/yt-dlp) and [ytmusicapi](https://github.com/sigma67/ytmusicapi) work.

1. Chrome stores session cookies after you log in to Google
2. This server reads those cookies using [rookiepy](https://github.com/thewh1teagle/rookie) (a Rust-based library, ultra lightweight)
3. Computes a `SAPISIDHASH` authorization header (`SHA1(timestamp + SAPISID + origin)`)
4. Makes requests to GSC's internal API — the exact same endpoints your browser uses

**Requirements:** Just be logged in to Google in Chrome. That's it. Chrome doesn't need to be running.

#### Multi-Browser Support
The server auto-detects browsers in priority order: **Chrome → Brave → Edge**

Override with environment variables:
```
BROWSER=brave           # force a specific browser
CHROME_PROFILE=/path    # override the profile directory path
```

### Bing Webmaster Tools — Free API Key

Bing provides a free, never-expiring API key from your account:
1. Go to [bing.com/webmasters](https://www.bing.com/webmasters)
2. Click **Settings → API Access**
3. Click **Generate API Key**
4. Copy the key and paste it into your MCP config (see setup below)

---

## 🚀 Installation & Setup

### Prerequisites
- Chrome (or Brave/Edge) browser with Google account logged in
- Python 3.11+ **or** [uv](https://docs.astral.sh/uv/) (recommended — no Python management needed)

---

### Option A: Install with `uvx` (Recommended — Zero Python Setup)

**Step 1: Install uv** (one-time, ~10 seconds)

```bash
# macOS / Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell):
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Step 2: Get your Bing API key** (2 minutes)
1. Go to [bing.com/webmasters](https://www.bing.com/webmasters) → Settings → API Access
2. Click **Generate API Key** and copy it

**Step 3: Add to your MCP config** (30 seconds)

For **Cline** (VS Code), open your MCP settings and add:

```json
{
  "mcpServers": {
    "gsc-bing-mcp": {
      "command": "uvx",
      "args": ["gsc-bing-mcp"],
      "env": {
        "BING_API_KEY": "paste-your-bing-key-here"
      }
    }
  }
}
```

For **Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "gsc-bing-mcp": {
      "command": "uvx",
      "args": ["gsc-bing-mcp"],
      "env": {
        "BING_API_KEY": "paste-your-bing-key-here"
      }
    }
  }
}
```

**Step 4: Done!** Restart Cline/Claude Desktop and start asking questions.

---

### Option B: Install with pip

```bash
pip install gsc-bing-mcp
```

Then in your MCP config:

```json
{
  "mcpServers": {
    "gsc-bing-mcp": {
      "command": "gsc-bing-mcp",
      "env": {
        "BING_API_KEY": "paste-your-bing-key-here"
      }
    }
  }
}
```

---

### Option C: Run from source (developers)

```bash
git clone https://github.com/codermillat/gsc-bing-mcp
cd gsc-bing-mcp
pip install -e .
```

MCP config:
```json
{
  "mcpServers": {
    "gsc-bing-mcp": {
      "command": "python",
      "args": ["-m", "gsc_bing_mcp.server"],
      "env": {
        "BING_API_KEY": "paste-your-bing-key-here"
      }
    }
  }
}
```

---

### Optional Environment Variables

| Variable | Description |
|----------|-------------|
| `BING_API_KEY` | Your Bing Webmaster API key (required for Bing tools) |
| `BROWSER` | Force browser: `chrome`, `brave`, or `edge` |
| `CHROME_PROFILE` | Override Chrome profile directory path |

---

## 💬 Example Questions You Can Ask

```
"What are my top 10 search queries in GSC for the last 30 days?"
"Show me the daily click trend for my site this month"
"Which pages are getting the most impressions on Google?"
"What's my average position for 'python tutorial' in Search Console?"
"List all my verified sites in Google Search Console"
"Give me all search queries for my site — not just the top 25"
"Show index coverage issues — how many pages are excluded?"
"Are there any sitemap errors on my site?"
"What are my top Bing keywords this month?"
"Show me Bing crawl errors for my site"
"Submit https://example.com/new-post to Bing for indexing"
"How many inbound links has Bing found for my site?"
"Compare my GSC vs Bing clicks for site:example.com"
"Which queries are sending traffic to which pages on my site?"
```

---

## 🛠️ Tool Reference

### Google Search Console Tools

#### `gsc_list_sites`
List all verified properties in your GSC account, including property type (Domain vs URL prefix).
- No parameters required

---

#### `gsc_performance_trend`
Daily performance trend data (clicks, impressions, CTR, position). Most reliable GSC tool — returns clean, structured daily data.
- `site_url` — e.g., `"https://example.com/"` or `"sc-domain:example.com"`
- `search_type` — `"WEB"` (default), `"IMAGE"`, `"VIDEO"`, `"NEWS"`
- `start_date` *(optional)* — `"YYYY-MM-DD"` (default: ~17 days ago)
- `end_date` *(optional)* — `"YYYY-MM-DD"` (default: ~3 days ago, due to GSC lag)

---

#### `gsc_top_queries`
Top queries by clicks. Set `limit=0` to return all available queries.
- `site_url` — your site
- `limit` — number of queries (default: 25, use `0` for all)
- `search_type` — `"WEB"` (default), `"IMAGE"`, `"VIDEO"`, `"NEWS"`
- `start_date`, `end_date` *(optional)* — date range

---

#### `gsc_top_pages`
Top pages by clicks. Set `limit=0` to return all pages.
- Same parameters as `gsc_top_queries`

---

#### `gsc_search_analytics`
Search analytics grouped by a single dimension.
- `site_url` — your site
- `dimension` — `"query"` (default), `"page"`, `"country"`, or `"device"`
- `search_type` — `"WEB"` (default), `"IMAGE"`, `"VIDEO"`, `"NEWS"`
- `start_date`, `end_date` *(optional)* — date range

---

#### `gsc_site_summary`
Coverage and indexing summary for a GSC property (indexed pages, errors, warnings, excluded URLs).
- `site_url` — your site

---

#### `gsc_list_sitemaps`
List all submitted sitemaps with status, submitted count, indexed count, and error counts.
- `site_url` — your site

---

#### `gsc_insights`
Search Console insights and notifications (branded query trends, filter alerts, callouts).
- `site_url` — your site

---

#### `gsc_all_queries`
Extract ALL search queries from GSC by scraping the performance page HTML. Bypasses the RPC pagination limitation — can return significantly more queries than `gsc_top_queries`.
- `site_url` — your site
- `search_type` — `"WEB"` (default), `"IMAGE"`, `"VIDEO"`, `"NEWS"`

---

#### `gsc_index_coverage`
Detailed index coverage statistics (indexed pages, errors, warnings, excluded URLs by category).
- `site_url` — your site

---

#### `gsc_query_pages`
Query-to-page correlations — shows which pages rank for which queries, with clicks, impressions, CTR, and position.
- `site_url` — your site
- `search_type` — `"WEB"` (default), `"IMAGE"`, `"VIDEO"`, `"NEWS"`
- `limit` — max rows (default: 50, use `0` for all)

---

### Bing Webmaster Tools

#### `bing_list_sites`
List all sites/properties in your Bing Webmaster account.
- No parameters required

---

#### `bing_search_analytics`
Daily search performance from Bing (impressions, clicks, average click position).
- `site_url` — site URL as it appears in Bing Webmaster Tools
- `start_date` — `"YYYY-MM-DD"`
- `end_date` — `"YYYY-MM-DD"`
- `limit` — max rows (default: 100)

---

#### `bing_keyword_stats`
Top keywords driving traffic from Bing, sorted by clicks.
- `site_url`, `start_date`, `end_date`, `limit`

---

#### `bing_crawl_stats`
Crawl statistics including errors, blocked URLs, DNS/connection issues.
- `site_url`

---

#### `bing_url_info`
Detailed information about a specific URL (crawl date, HTTP status, indexed status).
- `site_url` — the site in Bing Webmaster Tools
- `page_url` — the specific URL to inspect

---

#### `bing_page_stats`
Top pages with impressions, clicks, and average click position.
- `site_url`
- `limit` — max pages (default: 100)

---

#### `bing_submit_url`
Submit a single URL to Bing for indexing. Check quota first with `bing_url_submission_quota`.
- `site_url`
- `url` — the page URL to submit

---

#### `bing_submit_url_batch`
Submit multiple URLs to Bing in a single batch request.
- `site_url`
- `urls` — comma-separated list of URLs

---

#### `bing_crawl_issues`
Crawl issues and errors Bing encountered (HTTP errors, DNS, robots.txt blocks, etc.).
- `site_url`

---

#### `bing_url_submission_quota`
Check your remaining daily URL submission quota.
- `site_url`

---

#### `bing_link_counts`
Inbound link counts discovered by Bing for your site.
- `site_url`

---

### Utility

#### `refresh_google_session`
Force-refresh the cached Chrome cookies. Use if you recently re-logged in to Google and tools are failing.
- No parameters required

---

## ⚠️ Troubleshooting

### "Google session cookies not found"
- Make sure you're logged in to Google in Chrome
- Open Chrome, go to google.com, sign in if needed
- Call `refresh_google_session`, then retry

### "Chrome's cookie database is locked"
- Chrome may be writing to the DB. Wait a few seconds and retry.
- On macOS, this sometimes happens right after Chrome opens or closes.

### "Permission denied reading Chrome cookies" (macOS)
- Grant Full Disk Access to your terminal or IDE:
  - **System Settings → Privacy & Security → Full Disk Access** → Add Terminal / VS Code

### "BING_API_KEY environment variable is not set"
- Add `"BING_API_KEY"` to the `env` section of your MCP config
- Restart Cline/Claude Desktop after updating the config

### GSC data shows "No data found"
- GSC has a ~2–3 day data lag — use `end_date` at least 3 days in the past
- Verify `site_url` matches exactly as shown in GSC (including trailing slash)

### Using Brave or Edge instead of Chrome?
- Set `BROWSER=brave` or `BROWSER=edge` in the `env` section of your MCP config

---

## 📦 Dependencies

| Package | Purpose | Size |
|---------|---------|------|
| `mcp` | MCP protocol server (FastMCP) | ~5MB |
| `rookiepy` | Chrome/Brave/Edge cookie reader (Rust-based) | ~2MB |
| `httpx` | Async HTTP client | ~3MB |

**Total: ~10MB installed, ~15MB RAM at runtime**

No Playwright. No Chrome binary. No browser automation.

---

## 🔒 Privacy & Security

- **All data stays local** — this server runs on your machine and makes API calls directly from your computer
- **No data sent to any third party** — your cookies and search data never leave your machine
- **Cookies read-only** — this server only reads cookies, never modifies them
- **No logging of sensitive data** — cookie values are never logged

---

## 📡 How to Publish Updates (Developers)

```bash
# Edit version in pyproject.toml and gsc_bing_mcp/__init__.py, then:
pip install build twine
python -m build
twine upload dist/*
```

Users will automatically get the update next time `uvx` runs.

---

## 📝 License

MIT — free for personal and commercial use.
