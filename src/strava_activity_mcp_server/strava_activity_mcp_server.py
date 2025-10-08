import sys
import os
from mcp.server.fastmcp import FastMCP  # Import FastMCP, the quickstart server base
mcp = FastMCP("Strava")  # Initialize an MCP server instance with a descriptive name
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import requests
import urllib.parse

@mcp.tool("strava://auth/url")

def get_auth_url(client_id):
    """Return the Strava OAuth authorization URL. Open this URL in a browser to get the code."""
    return str(f"https://www.strava.com/oauth/authorize?client_id={client_id}&response_type=code&redirect_uri=https://developers.strava.com/oauth2-redirect/&approval_prompt=force&scope=read,activity:read_all")



@mcp.tool("strava://auth/token")
def exchange_code_for_token(
    code: str,
    client_id: int,
    client_secret: str,
) -> dict:
    """Exchange an authorization code for access + refresh tokens."""
    if not code:
        return {"error": "authorization code is required"}
    if not client_secret:
        return {"error": "client_secret is required"}

    resp = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
        },
    )
    try:
        resp.raise_for_status()
    except requests.HTTPError:
        return {"error": "token request failed", "status_code": resp.status_code, "response": resp.text}

    tokens = resp.json()
    # Print tokens for debugging (optional)
    print(tokens)

    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")

    return {"tokens": tokens, "access_token": access_token, "refresh_token": refresh_token}


def refresh_access_token(
    refresh_token: str,
    client_id: int,
    client_secret: str,
) -> dict:
    """Refresh an access token using a refresh token."""
    if not refresh_token:
        return {"error": "refresh_token is required"}

    resp = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
    )
    try:
        resp.raise_for_status()
    except requests.HTTPError:
        return {"error": "refresh request failed", "status_code": resp.status_code, "response": resp.text}

    new_tokens = resp.json()
    # Print new tokens for debugging (optional)
    print(new_tokens)
    return new_tokens


@mcp.tool("strava://athlete/stats")
def get_athlete_stats(token: str) -> object:
    """Retrieve athlete activities using an access token."""
    url = "https://www.strava.com/api/v3/athlete/activities?per_page=60"
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {token}"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    # Return the parsed JSON (dict or list) instead of a JSON string so the return type matches.
    return response.json()

if __name__ == "__main__":
    mcp.run(transport="stdio")  # Run the server, using standard input/output for communication