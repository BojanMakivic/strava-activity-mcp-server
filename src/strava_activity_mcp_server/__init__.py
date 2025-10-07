from .strava_mcp_server import mcp
def main() -> None:
    """Run the MCP server."""
    mcp.run()