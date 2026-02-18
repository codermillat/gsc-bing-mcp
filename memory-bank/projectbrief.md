# Project Brief: GSC & Bing Webmaster MCP Server

## Project Name
`gsc-bing-mcp` — Google Search Console + Bing Webmaster Tools MCP Server

## Core Goal
Build an MCP (Model Context Protocol) server that allows AI agents (Claude, Cline) to pull search performance stats from Google Search Console and Bing Webmaster Tools — **without requiring API keys, OAuth apps, Google Cloud accounts, credit cards, or Playwright/browser automation**.

## Key Constraints
- ❌ No Google Cloud account required
- ❌ No credit card or billing required
- ❌ No API keys for Google (uses existing browser session)
- ❌ No Playwright or browser automation (no heavy Chrome launch)
- ✅ User just needs to be logged in to Google in Chrome
- ✅ Bing requires only a free API key from their dashboard (30-second setup)
- ✅ Ultra lightweight (~15MB RAM, 3 Python packages)
- ✅ Runs locally on each user's machine (no server to maintain)
- ✅ Published to PyPI, distributed via `uvx` (zero-install for users)

## Target Users
Developers, SEOs, and marketers who want AI agents to analyze their search performance data without complex API setup.

## Distribution Model
- Published to PyPI as `gsc-bing-mcp`
- Users install via `uvx gsc-bing-mcp` (auto-managed by uv)
- Publisher maintains nothing server-side — all runs locally per user
- Updates pushed via `python -m build && twine upload`

## Project Location
`/Users/mdmillathosen/Desktop/GSC - MCP/`
