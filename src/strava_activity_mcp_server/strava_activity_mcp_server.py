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
    return "https://www.strava.com/oauth/authorize?" + urllib.parse.urlencode(params)



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
def _get_env_client_credentials() -> tuple[int | None, str | None]:
    """Read client id and secret from environment and return (client_id, client_secret).

    client_id will be returned as int if present and valid, otherwise None.
    """
    client_id = None
    client_secret = os.getenv("STRAVA_CLIENT_SECRET")
    client_id_env = os.getenv("STRAVA_CLIENT_ID")
    if client_id_env:
        try:
            client_id = int(client_id_env)
        except ValueError:
            client_id = None
    return client_id, client_secret


def _ensure_access_token(token_or_tokens: object) -> tuple[str | None, dict | None]:
    """Given either an access token string or the token dict returned by the token endpoints,
    return a tuple (access_token, tokens_dict).

    If a dict is provided and contains no valid access_token but has a refresh_token,
    attempt to refresh using env client credentials. Returns (access_token, tokens_dict) or (None, None)
    on failure.
    """
    # If token_or_tokens is a string, assume it's an access token.
    if isinstance(token_or_tokens, str):
        return token_or_tokens, None

    # If it's a dict-like object, try to find access_token
    if isinstance(token_or_tokens, dict):
        access_token = token_or_tokens.get("access_token")
        if access_token:
            return access_token, token_or_tokens

        # try refresh flow
        refresh_token = token_or_tokens.get("refresh_token")
        client_id = token_or_tokens.get("client_id")
        client_secret = token_or_tokens.get("client_secret")

        # fallback to env vars if client id/secret not in the dict
        if not client_id or not client_secret:
            env_client_id, env_client_secret = _get_env_client_credentials()
            if not client_id:
                client_id = env_client_id
            if not client_secret:
                client_secret = env_client_secret

        if refresh_token and client_id and client_secret:
            try:
                new_tokens = refresh_access_token(refresh_token, int(client_id), client_secret)
            except Exception as e:
                print(f"refresh failed: {e}")
                return None, None

            access_token = new_tokens.get("access_token")
            return access_token, new_tokens

    return None, None


@mcp.tool("strava://athlete/stats")
def get_athlete_stats(token: object) -> object:
    """Retrieve athlete activities using either an access token string or a token dict.

    If a token dict is provided and the access token is missing/expired, the function will
    attempt to refresh it (one attempt) using provided refresh token and client credentials
    (falling back to STRAVA_CLIENT_ID/STRAVA_CLIENT_SECRET environment variables).
    """
    access_token, tokens_dict = _ensure_access_token(token)
    if not access_token:
        return {"error": "Could not obtain an access token"}

    url = "https://www.strava.com/api/v3/athlete/activities?per_page=60"
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {access_token}"
    }

    response = requests.get(url, headers=headers)

    # If unauthorized, try one refresh if we have a refresh token available
    if response.status_code == 401 and isinstance(token, dict):
        refresh_token = token.get("refresh_token") or (tokens_dict or {}).get("refresh_token")
        if refresh_token:
            client_id = token.get("client_id") or (tokens_dict or {}).get("client_id")
            client_secret = token.get("client_secret") or (tokens_dict or {}).get("client_secret")
            if not client_id or not client_secret:
                env_client_id, env_client_secret = _get_env_client_credentials()
                client_id = client_id or env_client_id
                client_secret = client_secret or env_client_secret

            if client_id and client_secret:
                new_tokens = refresh_access_token(refresh_token, int(client_id), client_secret)
                new_access = new_tokens.get("access_token")
                if new_access:
                    headers["authorization"] = f"Bearer {new_access}"
                    response = requests.get(url, headers=headers)

    try:
        response.raise_for_status()
    except requests.HTTPError:
        return {"error": "request failed", "status_code": response.status_code, "response": response.text}

    return response.json()

if __name__ == "__main__":
    mcp.run(transport="stdio")  # Run the server, using standard input/output for communication