# Progress

## ✅ COMPLETED — v0.1.0 Published

### What Works
- Full MCP server with 11 tools (6 GSC + 4 Bing + 1 utility)
- SAPISIDHASH authentication (no OAuth, no API keys for Google)
- rookiepy Chrome cookie extraction (cross-platform)
- 5-minute in-memory cookie cache
- httpx async HTTP client for both GSC and Bing APIs
- FastMCP stdio transport
- PyPI package published: https://pypi.org/project/gsc-bing-mcp/0.1.0/
- GitHub repo: https://github.com/codermillat/gsc-bing-mcp
- Cline MCP settings updated to use `uvx gsc-bing-mcp` (PyPI)
- Bing API key configured in Cline MCP settings

### Current Cline MCP Config
```json
"gsc-bing-mcp": {
  "command": "uvx",
  "args": ["gsc-bing-mcp"],
  "env": { "BING_API_KEY": "caafd6505af04f9c90edca8b73ddfc3e" }
}
```

## ⚠️ Security Action Needed
- **Regenerate PyPI token** — the token used for upload was exposed in chat history
  - Go to: https://pypi.org/manage/account/token/
  - Delete old token "gsc-bing-mcp-upload"
  - Create new token scoped to project "gsc-bing-mcp" (now safe since project exists)
  - Update ~/.pypirc with new token (for future version uploads)

## Known Limitations
- Google auth breaks if Chrome is open (SQLite WAL lock) — user must close Chrome
- Cookie expiry: ~1 hour Google session cookies; user must be logged in
- SAPISIDHASH is an internal Google API technique — could break if Google changes auth
- Bing API key must be manually obtained from bing.com/webmasters

## Future Improvements
- v0.2.0: Add error recovery when Chrome is open (suggest closing Chrome)
- v0.2.0: Add `gsc_index_coverage` tool for index coverage reports
- v0.2.0: Add `bing_submit_url` tool for URL submission
- v0.3.0: Support Firefox cookies as fallback
- v0.3.0: Support multiple Google accounts
