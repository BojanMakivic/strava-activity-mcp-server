# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project follows Semantic Versioning.

## [1.0.4] - 2026-03-31

### Changed
- Expanded README with a Windows-first credential setup guide using user environment variables for `STRAVA_CLIENT_ID` and `STRAVA_CLIENT_SECRET`.
- Added explicit MCP client configuration guidance for `mcp.json` / `config.json` with a safer default that avoids embedding secrets in client JSON.
- Clarified interpolation behavior (`${VAR}`) and documented fallback behavior when MCP clients do not expand variables.
- Corrected `strava.session.start` output documentation to describe sanitized `token_status` metadata behavior.

### Security
- Documented a safer operational pattern for Msty and similar MCP clients: keep real credentials out of per-tool JSON `env` blocks when client logging can expose env values.

## [1.0.1] - 2026-03-29

### Changed
- Hardened token handling across auth and refresh flows to reduce secret exposure in MCP client contexts.
- Updated analytics defaults to favor compact summary responses for better LLM context compatibility.
- Reduced default analytics `per_page` from 100 to 50 to lower oversized payload risk.
- Updated README tool contracts to document sanitized outputs and summary-first behavior.

### Added
- Internal token-status helper metadata for non-sensitive auth diagnostics.
- Summary-first response mode with optional capped detailed output for:
  - `strava.athlete.fetch-all`
  - `strava.trimp.banister`
  - `strava://trimp/account-report`

### Security
- Removed plaintext token debug printing in OAuth/refresh flows.
- Stopped returning raw token values from normal load/refresh-style outputs.
- Kept first-time OAuth bootstrap flow while shifting day-to-day usage toward local token refresh without token echo.

### Fixed
- Standardized pagination/orchestration behavior and clearer stop conditions for multipage fetches.
