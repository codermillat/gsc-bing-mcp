# gsc-bing-mcp

An MCP (Model Context Protocol) server that gives AI agents (Claude, Cline) direct access to your **Google Search Console** and **Bing Webmaster Tools** search performance data.

**Zero API keys for Google** — uses your existing Chrome browser session.  
**30-second setup for Bing** — just copy one free key from your dashboard.

---

## ✨ Features

| Capability | Tool |
|-----------|------|
| List all your GSC properties | `gsc_list_sites` |
| Search analytics (clicks, impressions, CTR, position) | `gsc_search_analytics` |
| Top queries by clicks | `gsc_top_queries` |
| Top pages by clicks | `gsc_top_pages` |
| Sitemap status | `gsc_list_sitemaps` |
| URL indexing inspection | `gsc_inspect_url` |
| List Bing sites | `bing_list_sites` |
| Bing search performance | `bing_search_analytics` |
| Bing crawl statistics | `bing_crawl_stats` |
| Bing keyword stats | `bing_keyword_stats` |
| Refresh Google session | `refresh_google_session` |

---

## 🔐 How Authentication Works

### Google Search Console (Zero Setup)
This server reads your Chrome browser's cookies directly from disk — the same way tools like [yt-dlp](https://github.com/yt-dlp/yt-dlp) work.

1. Your Chrome stores session cookies after you log in to Google
2. This server reads those cookies using [rookiepy](https://github.com/thewh1teagle/rookie) (a Rust library, ultra lightweight)
3. Generates a `SAPISIDHASH` authorization header (SHA1 of timestamp + SAPISID cookie)
4. Makes requests to GSC's API — the exact same endpoints your browser uses

**Requirements:** Just be logged in to Google in Chrome. That's it.

### Bing Webmaster Tools (Free API Key)
Bing provides a free, never-expiring API key from your account:
1. Go to [bing.com/webmasters](https://www.bing.com/webmasters)
2. Click **Settings → API Access**
3. Click **Generate API Key**
4. Copy the key and paste it into your MCP config (see setup below)

---

## 🚀 Installation & Setup

### Prerequisites
- Chrome browser with Google account logged in
- Python 3.11+ **or** [uv](https://docs.astral.sh/uv/) (recommended — no Python management needed)

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

For **Cline** (VS Code), open your MCP settings file and add:

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

## 💬 Example Questions You Can Ask

Once set up, ask your AI agent:

```
"What are my top 10 search queries in GSC for the last 30 days?"
"Show me which pages are getting the most impressions on Google"
"What's my average position for 'python tutorial' in Search Console?"
"List all my verified sites in Google Search Console"
"Are there any sitemap errors on my site?"
"Check if https://example.com/blog/post-1 is indexed by Google"
"What are my top Bing keywords this month?"
"Show me Bing crawl errors for my site"
"Compare my GSC vs Bing clicks for site:example.com"
```

---

## 🛠️ Tool Reference

### Google Search Console Tools

#### `gsc_list_sites`
List all verified properties in your GSC account.
- No parameters required

#### `gsc_search_analytics`
Full search analytics with custom dimensions and date ranges.
- `site_url` — e.g., `"https://example.com/"` or `"sc-domain:example.com"`
- `start_date` — `"YYYY-MM-DD"`
- `end_date` — `"YYYY-MM-DD"`
- `dimensions` — comma-separated: `"query"`, `"page"`, `"country"`, `"device"`, `"date"` (default: `"query"`)
- `row_limit` — max rows (default: 100)

#### `gsc_top_queries`
Top queries by clicks (quickest way to see what drives traffic).
- `site_url` — your site
- `limit` — number of queries (default: 25)
- `start_date`, `end_date` — optional (defaults to last 28 days)

#### `gsc_top_pages`
Top pages by clicks.
- Same parameters as `gsc_top_queries`

#### `gsc_list_sitemaps`
List submitted sitemaps with status and error counts.
- `site_url` — your site

#### `gsc_inspect_url`
Inspect a URL's indexing status, crawl date, mobile usability, and rich results.
- `site_url` — the GSC property
- `url` — the specific URL to inspect

### Bing Webmaster Tools

#### `bing_list_sites`
List all sites in your Bing Webmaster account.
- No parameters required

#### `bing_search_analytics`
Daily search performance data from Bing.
- `site_url`, `start_date`, `end_date`, `limit`

#### `bing_crawl_stats`
Crawl statistics including errors and blocked URLs.
- `site_url`

#### `bing_keyword_stats`
Top keywords from Bing sorted by clicks.
- `site_url`, `start_date`, `end_date`, `limit`

### Utility

#### `refresh_google_session`
Force-refresh the cached Chrome cookies. Use if you recently re-logged in to Google.
- No parameters required

---

## ⚠️ Troubleshooting

### "Google session cookies not found"
- Make sure you're logged in to Google in Chrome
- Open Chrome, go to google.com, sign in if needed
- Call `refresh_google_session` tool, then retry

### "Chrome's cookie database is locked"
- Chrome may be in the middle of writing. Wait a few seconds and retry.
- On macOS, this sometimes happens right after Chrome opens/closes.

### "Permission denied reading Chrome cookies" (macOS)
- Grant Full Disk Access to your terminal or IDE:
  - System Settings → Privacy & Security → Full Disk Access → Add Terminal / VS Code

### "BING_API_KEY environment variable is not set"
- Make sure you added `"BING_API_KEY"` to the `env` section of your MCP config
- Restart Cline/Claude Desktop after updating the config

### GSC data shows "No data found"
- GSC has a ~3-day data lag — use end dates at least 3 days in the past
- Check that the `site_url` matches exactly as shown in GSC (including trailing slash)

---

## 📦 Dependencies

| Package | Purpose | Size |
|---------|---------|------|
| `mcp` | MCP protocol server (FastMCP) | ~5MB |
| `rookiepy` | Chrome cookie reader (Rust-based) | ~2MB |
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
# Edit version in pyproject.toml, then:
pip install build twine
python -m build
twine upload dist/*
```

Users will automatically get the update next time `uvx` runs.

---

## 📝 License

MIT — free for personal and commercial use.
