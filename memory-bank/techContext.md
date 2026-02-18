# Tech Context

## Technology Stack

### Runtime
- **Python 3.11+** (required for modern type hints and FastMCP)
- **uv / uvx** — package manager for distribution (users need this)

### Core Dependencies (3 packages only)
| Package | Version | Purpose |
|---------|---------|---------|
| `mcp` | latest | FastMCP framework for MCP server (stdio transport) |
| `rookiepy` | latest | Rust-based Chrome cookie extractor (cross-platform, handles AES-GCM decryption) |
| `httpx` | latest | Async HTTP client for API calls to GSC and Bing |

### Why These Specific Packages

**`mcp` (FastMCP):**
- Official Python MCP SDK from Anthropic/MCP team
- `@mcp.tool()` decorator auto-generates JSON schema from Python type hints
- `mcp.run()` starts stdio transport — works out of box with Cline, Claude Desktop
- No additional web server needed

**`rookiepy`:**
- Written in Rust — extremely fast, low memory footprint (~2MB)
- Handles Chrome's AES-256-GCM cookie encryption on macOS (reads key from Keychain)
- Cross-platform: macOS, Windows, Linux
- API: `rookiepy.chrome(["google.com"])` → list of cookie dicts
- Cookie dict format: `{"name": str, "value": str, "domain": str, "path": str, ...}`
- Alternative considered: `browser-cookie3` (pure Python, less reliable on macOS AES decryption)

**`httpx`:**
- Modern async HTTP client (replaces `requests` for async use)
- Used with `httpx.AsyncClient` for all API calls
- Handles cookies, headers, JSON natively
- `async with httpx.AsyncClient() as client:` pattern

## Authentication Details

### Google Search Console — SAPISIDHASH
- **No Google Cloud project needed**
- Uses Chrome's existing session cookies
- Cookies extracted: `SAPISID`, `__Secure-1PSID`, `__Secure-3PAPISID`, `SID`, `HSID`, `SSID`, `APISID`
- SAPISIDHASH formula: `SHA1(f"{unix_ts} {SAPISID} {origin}")`
- Header: `Authorization: SAPISIDHASH {unix_ts}_{sha1_hex}`
- Origin: `https://search.google.com`
- Cookie lifetime: weeks to months
- Same technique as: yt-dlp, ytmusicapi, gpt4free

### Bing Webmaster — Official API Key
- **No Azure/Microsoft account needed beyond existing Bing account**
- Generated from: `bing.com/webmasters` → Settings → API Access → Generate
- Stored as env var: `BING_API_KEY`
- Used as query param: `?apikey={key}`
- Lifetime: Never expires (only if user regenerates)
- Official documented API: `ssl.bing.com/webmaster/api.svc/json/`

## Distribution

### PyPI Package Structure
```
pyproject.toml:
  name = "gsc-bing-mcp"
  [project.scripts]
  gsc-bing-mcp = "gsc_bing_mcp.server:main"
```

### User MCP Config (Cline/Claude Desktop)
```json
{
  "mcpServers": {
    "gsc-bing-mcp": {
      "command": "uvx",
      "args": ["gsc-bing-mcp"],
      "env": {
        "BING_API_KEY": "your-key-here"
      }
    }
  }
}
```

## Platform Notes

### macOS
- Chrome user data: `~/Library/Application Support/Google/Chrome/`
- rookiepy reads Keychain for AES decryption key automatically
- System Python may conflict — users should use uv which manages its own Python

### Windows
- Chrome user data: `%LOCALAPPDATA%\Google\Chrome\User Data\`
- rookiepy uses Windows DPAPI for cookie decryption

### Linux
- Chrome user data: `~/.config/google-chrome/`
- rookiepy uses Gnome Keyring or kwallet

## Development Setup
```bash
cd "/Users/mdmillathosen/Desktop/GSC - MCP"
python -m venv .venv
source .venv/bin/activate
pip install mcp rookiepy httpx build twine
```

## Publishing
```bash
python -m build          # creates dist/
twine upload dist/*      # uploads to PyPI
```
