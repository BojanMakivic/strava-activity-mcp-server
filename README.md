# strava-mcp-server
MCP server that retrieves user activity data from Strava.

.venv\Scripts\activate

uv init --build-backend "hatchling"

uv add mcp["cli"]

uv run mcp dev scr/strava_mcp_server/strava_mcp_server.py
