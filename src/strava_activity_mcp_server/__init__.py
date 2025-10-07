from .strava_activity_mcp_server import mcp
def main() -> None:
    """Run the MCP server."""
    mcp.run()