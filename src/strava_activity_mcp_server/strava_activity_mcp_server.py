import sys
import os
from mcp.server.fastmcp import FastMCP  # Import FastMCP, the quickstart server base
mcp = FastMCP("Strava")  # Initialize an MCP server instance with a descriptive name
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import requests
import urllib.parse
import json
from typing import Any, Dict

TOKEN_STORE_FILENAME = "C:/Users/bma/strava_mcp_tokens.json"

def _get_token_store_path() -> str:
    home_dir = os.path.expanduser("~")
    return os.path.join(home_dir, TOKEN_STORE_FILENAME)

def _save_tokens_to_disk(tokens: Dict[str, Any]) -> dict:
    try:
        path = _get_token_store_path()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(tokens, f)
        return {"ok": True, "path": path}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def _load_tokens_from_disk() -> dict:
    try:
        path = _get_token_store_path()
        if not os.path.exists(path):
            return {"ok": False, "error": "token store not found", "path": path}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {"ok": True, "tokens": data, "path": path}
    except Exception as e:
        return {"ok": False, "error": str(e)}

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
    
    # Persist tokens for later refresh usage
    _save_tokens_to_disk({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": tokens.get("expires_at"),
        "expires_in": tokens.get("expires_in"),
        "athlete": tokens.get("athlete"),
        "token_type": tokens.get("token_type"),
        "scope": tokens.get("scope"),
    })

    # return {"tokens": tokens, "access_token": access_token, "refresh_token": refresh_token}

    url = "https://www.strava.com/api/v3/athlete/activities?per_page=60"
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {access_token}"
    }

    response = requests.get(url, headers=headers)
    return {
        "activities": response.json(),
        "tokens": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": tokens.get("expires_at"),
            "expires_in": tokens.get("expires_in"),
        }
    }

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

@mcp.tool("strava://auth/save")
def save_tokens(tokens: dict | None = None) -> dict:
    """Save tokens to local disk at ~/.strava_mcp_tokens.json. If tokens is not provided, no-op with error."""
    if not tokens or not isinstance(tokens, dict):
        return {"error": "tokens dict is required"}
    result = _save_tokens_to_disk(tokens)
    if not result.get("ok"):
        return {"error": "failed to save tokens", **result}
    return {"ok": True, "path": result.get("path")}


@mcp.tool("strava://auth/load")
def load_tokens() -> dict:
    """Load tokens from local disk at ~/.strava_mcp_tokens.json."""
    result = _load_tokens_from_disk()
    if not result.get("ok"):
        return {"error": result.get("error"), "path": result.get("path")}
    return {"ok": True, "tokens": result.get("tokens"), "path": result.get("path")}

if __name__ == "__main__":
    mcp.run(transport="stdio")  # Run the server, using standard input/output for communication