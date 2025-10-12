import sys
import os
from mcp.server.fastmcp import FastMCP  # Import FastMCP, the quickstart server base
mcp = FastMCP("Strava")  # Initialize an MCP server instance with a descriptive name
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import requests
import urllib.parse

@mcp.tool("strava://auth/url")
def get_auth_url(client_id: int | None = None):
    """Return the Strava OAuth authorization URL. If client_id is not provided,
    read it from the STRAVA_CLIENT_ID environment variable."""
    if client_id is None:
        client_id_env = os.getenv("STRAVA_CLIENT_ID")
        if not client_id_env:
            return {"error": "STRAVA_CLIENT_ID environment variable is not set"}
        try:
            client_id = int(client_id_env)
        except ValueError:
            return {"error": "STRAVA_CLIENT_ID must be an integer"}

    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": "https://developers.strava.com/oauth2-redirect/",
        "approval_prompt": "force",
        "scope": "read,activity:read_all",
    }
    # Always return whole URL and not part of it
    return "https://www.strava.com/oauth/authorize?" + urllib.parse.urlencode(params)

@mcp.tool("strava://auth/refresh")
def refresh_access_token(
    refresh_token: str,
    client_id: int | None = None,
    client_secret: str | None = None,
) -> dict:
    """Refresh an access token using a refresh token."""
    if not refresh_token:
        return {"error": "refresh token is required"}
    
    if client_id is None:
        client_id_env = os.getenv("STRAVA_CLIENT_ID")
        if not client_id_env:
            return {"error": "STRAVA_CLIENT_ID environment variable is not set"}
        try:
            client_id = int(client_id_env)
        except ValueError:
            return {"error": "STRAVA_CLIENT_ID must be an integer"}

    if client_secret is None:
        client_secret_env = os.getenv("STRAVA_CLIENT_SECRET")
        if not client_secret_env:
            return {"error": "STRAVA_CLIENT_SECRET environment variable is not set"}
        try:
            client_secret = str(client_secret_env)
        except ValueError:
            return {"error": "STRAVA_CLIENT_SECRET must be a string"}

    resp = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
    )
    
    try:
        resp.raise_for_status()
    except requests.HTTPError:
        return {"error": "token refresh failed", "status_code": resp.status_code, "response": resp.text}
    except Exception as e:
        return {"error": "token refresh failed", "status_code": resp.status_code, "response": resp.text, "error": str(e)}

    tokens = resp.json()
    print(tokens)  # Print tokens for debugging (optional)
    
    return {
        "access_token": tokens.get("access_token"),
        "refresh_token": tokens.get("refresh_token"),
        "expires_at": tokens.get("expires_at"),
        "expires_in": tokens.get("expires_in")
    }

@mcp.tool("strava://athlete/stats")
def get_athlete_stats(
    code: str,
    client_id: int | None = None,
    client_secret: str | None = None,
) -> dict:
    """Exchange an authorization code for access + refresh tokens and get athlete activities."""
    if not code:
        return {"error": "authorization code is required"}

    if client_id is None:
        client_id_env = os.getenv("STRAVA_CLIENT_ID")
        if not client_id_env:
            return {"error": "STRAVA_CLIENT_ID environment variable is not set"}
        try:
            client_id = int(client_id_env)
        except ValueError:
            return {"error": "STRAVA_CLIENT_ID must be an integer"}

    if client_secret is None:
        client_secret_env = os.getenv("STRAVA_CLIENT_SECRET")
        if not client_secret_env:
            return {"error": "STRAVA_CLIENT_SECRET environment variable is not set"}
        try:
            client_secret = str(client_secret_env)
        except ValueError:
            return {"error": "STRAVA_CLIENT_SECRET must be a string"}

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
    except Exception as e:
        return {"error": "token request failed", "status_code": resp.status_code, "response": resp.text, "error": str(e)}

    tokens = resp.json()
    # Print tokens for debugging (optional)
    print(tokens)

    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")

    # return {"tokens": tokens, "access_token": access_token, "refresh_token": refresh_token}

    url = "https://www.strava.com/api/v3/athlete/activities?per_page=60"
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {access_token}"
    }

    response = requests.get(url, headers=headers)

    return response.json()

@mcp.tool("strava://athlete/stats-with-token")
def get_athlete_stats_with_token(access_token: str) -> dict:
    """Get athlete activities using an existing access token."""
    if not access_token:
        return {"error": "access token is required"}
    
    url = "https://www.strava.com/api/v3/athlete/activities?per_page=60"
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {access_token}"
    }

    response = requests.get(url, headers=headers)
    
    try:
        response.raise_for_status()
    except requests.HTTPError:
        return {"error": "API request failed", "status_code": response.status_code, "response": response.text}
    except Exception as e:
        return {"error": "API request failed", "status_code": response.status_code, "response": response.text, "error": str(e)}

    return response.json()


if __name__ == "__main__":
    mcp.run(transport="stdio")  # Run the server, using standard input/output for communication