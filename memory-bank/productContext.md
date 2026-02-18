# Product Context

## Why This Project Exists
AI agents (Claude, Cline) need access to web analytics data to help users understand their search performance. Existing solutions require:
- Complex Google Cloud OAuth setup (credit card, billing account, app registration)
- Heavy browser automation tools (Playwright, 300MB+ Chrome download)
- Constant re-authentication (short-lived tokens)

This MCP server solves all of these by using the user's existing Chrome browser session.

## Problems It Solves

### Problem 1: Complex Auth Setup
**Current**: Users need Google Cloud project + OAuth app + billing account + consent screen
**Solution**: Read cookies from Chrome's local SQLite database using `rookiepy` — zero setup if already logged in

### Problem 2: Heavy Dependencies
**Current**: Playwright requires downloading a full Chrome binary (~300MB), uses 500MB+ RAM
**Solution**: `rookiepy` (Rust-based, ~2MB) reads cookie files directly — no browser launch needed

### Problem 3: Token Expiry (Google access tokens expire in 1 hour)
**Current**: OAuth access tokens expire hourly, requiring complex refresh logic
**Solution**: Chrome session cookies last weeks/months. SAPISIDHASH uses SAPISID cookie which is long-lived. When expired, user just needs to be logged in to Chrome normally.

### Problem 4: No Server to Maintain
**Current**: Remote MCP servers require infrastructure, hosting, uptime monitoring
**Solution**: stdio transport runs locally on each user's machine. Publisher pushes code to PyPI; no server involvement.

## How It Works

### Google Search Console Auth (SAPISIDHASH)
1. `rookiepy.chrome(["google.com"])` reads Chrome's encrypted cookie SQLite DB
2. Extracts `SAPISID` cookie (long-lived, weeks/months)
3. Computes `SAPISIDHASH = SHA1(timestamp + " " + SAPISID + " " + origin)`
4. Uses this as `Authorization` header for GSC internal API calls
5. Same mechanism used by yt-dlp, ytmusicapi, and other popular tools

### Bing Webmaster Auth (Official API Key)
1. User generates free API key from bing.com/webmasters → Settings → API Access
2. Key stored in `BING_API_KEY` environment variable in MCP config
3. Passed as `?apikey=` query parameter to official Bing Webmaster API
4. Key never expires, 100% stable official API

## User Experience Goals
1. **Zero friction for Google**: Just be logged in to Chrome
2. **Minimal friction for Bing**: 30-second one-time key generation
3. **No re-auth ever**: Cookies last months; Bing key never expires
4. **Works offline from GSC/Bing web UI**: All direct API calls
5. **Installable in 3 minutes total**
