# Active Context

## Current Work Focus
Building the complete `gsc-bing-mcp` Python MCP server package from scratch.

## Session Summary (2026-02-18)
Completed full research and architecture planning. Now in implementation phase.

## Key Decisions Made This Session

### Authentication Strategy
- **Google GSC**: `rookiepy` cookie extraction + SAPISIDHASH (NO Google Cloud, NO OAuth, NO API key)
- **Bing Webmaster**: Official free API key (from bing.com/webmasters → Settings → API Access)
- **No Playwright**: Eliminated as too heavy (300MB+ Chrome dependency)
- **No OAuth fallback**: User explicitly rejected this — keep it simple

### Distribution Strategy
- PyPI package: `gsc-bing-mcp`
- Users install via `uvx gsc-bing-mcp` — zero-install experience
- Bing API key passed via `BING_API_KEY` env var in MCP config (no separate setup script)
- Publisher maintains nothing server-side

### Why SAPISIDHASH Over Cookie-Based Bing
- Bing's official API key is truly free, never expires, 30-second setup
- Using Bing cookies would be unstable internal API
- This hybrid gives best of both worlds: zero setup for Google, stable API for Bing

## Next Steps (Implementation Order)
1. Create package folder `gsc_bing_mcp/` with `__init__.py` files
2. `extractors/chrome_cookies.py` — rookiepy wrapper + TTL cache
3. `extractors/sapisidhash.py` — SAPISIDHASH hash generator
4. `clients/gsc_client.py` — 4 GSC API methods
5. `clients/bing_client.py` — 4 Bing API methods
6. `server.py` — FastMCP server with all 10 @mcp.tool() tools
7. `pyproject.toml` — PyPI packaging config
8. `requirements.txt` + `README.md`
9. Update Cline MCP settings

## Important Patterns to Follow
- All async functions (FastMCP supports async tools)
- Type hints on all tool parameters (FastMCP auto-generates schema)
- Docstrings on all tools (become MCP tool descriptions)
- Graceful error handling with user-friendly messages
- Cookie cache TTL = 300 seconds (5 min)

## Known Risks / Watchpoints
- SAPISIDHASH might need `__Secure-3PAPISID` instead of `SAPISID` on newer Chrome
- GSC internal API endpoints could theoretically change (not official)
- rookiepy may fail if Chrome is open with DB locked — add helpful error message
- Test with actual Chrome session before declaring complete

## Files Created So Far
- `memory-bank/projectbrief.md` ✅
- `memory-bank/productContext.md` ✅
- `memory-bank/systemPatterns.md` ✅
- `memory-bank/techContext.md` ✅
- `memory-bank/activeContext.md` ✅ (this file)
- `memory-bank/progress.md` (next)
