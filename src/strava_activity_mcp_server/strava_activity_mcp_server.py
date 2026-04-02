import sys
import os
from mcp.server.fastmcp import FastMCP  # Import FastMCP, the quickstart server base
mcp = FastMCP("Strava")  # Initialize an MCP server instance with a descriptive name
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import logging
import requests
import urllib.parse
import json
from typing import Any, Dict

# Logger for safe informational messages (do not log secrets)
logger = logging.getLogger(__name__)


def _mask_secret(s: str | None, show: int = 4) -> str | None:
    """Return a masked version of a secret, showing only the last `show` chars.
    If `s` is falsy, returns None. Used to avoid exposing secrets in tool responses.
    """
    if not s:
        return None
    s = str(s)
    if len(s) <= show:
        return "*" * len(s)
    return "*" * (len(s) - show) + s[-show:]

TOKEN_STORE_FILENAME = "strava_mcp_tokens.json"

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

@mcp.tool("strava.auth.url")
async def get_auth_url(client_id: int | None = None):
    """Return a Strava OAuth authorization URL for first-time setup only.

    Usage: Call only when no refresh token exists (first-time user authorization).
    Side effects: none (does not store tokens). The server will read
    `STRAVA_CLIENT_ID` from environment if `client_id` is not passed. The value
    of `STRAVA_CLIENT_ID` is never returned in full; only a masked presence
    indicator is returned.

    Example response:
      {
        "auth_url": "...",
        "first_time_only": True,
        "env_client_id_present": True
      }
    """
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
    url = "https://www.strava.com/oauth/authorize?" + urllib.parse.urlencode(params)
    return {
        "auth_url": url,
        "first_time_only": True,
        "env_client_id_present": bool(os.getenv("STRAVA_CLIENT_ID")),
    }

@mcp.tool("strava.auth.refresh")
async def refresh_access_token(
    refresh_token: str,
    client_id: int | None = None,
    client_secret: str | None = None,
) -> dict:
    """Refresh an access token using a refresh token.

    Usage: This tool is intended for subsequent authorizations only (after
    initial setup). It will call Strava to refresh tokens and persist the raw
    tokens to disk, but it will NOT return raw secrets or tokens to the client.

    Returns masked previews and expiry metadata only.
    """
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
    # Persist raw tokens to disk for internal use, but do not return them raw
    _save_tokens_to_disk(tokens)
    logger.info("tokens refreshed and saved; access_preview=%s refresh_preview=%s",
                _mask_secret(tokens.get("access_token")), _mask_secret(tokens.get("refresh_token")))

    return {
        "access_token_preview": _mask_secret(tokens.get("access_token")),
        "refresh_token_preview": _mask_secret(tokens.get("refresh_token")),
        "expires_at": tokens.get("expires_at"),
        "expires_in": tokens.get("expires_in"),
        "requires_refresh_token": True,
        "env_client_id_present": bool(os.getenv("STRAVA_CLIENT_ID")),
        "env_client_secret_present": bool(os.getenv("STRAVA_CLIENT_SECRET")),
    }

@mcp.tool("strava.athlete.stats")
async def get_athlete_stats(
    code: str,
    client_id: int | None = None,
    client_secret: str | None = None,
    after: int | None = None,
    before: int | None = None,
    page: int | None = None,
    per_page: int | None = None,
) -> dict:
    """Exchange an authorization code for access + refresh tokens and get athlete activities with optional filters.
    
    Args:
        code: Authorization code from Strava OAuth
        client_id: Strava client ID
        client_secret: Strava client secret
        after: An epoch timestamp to use for filtering activities that have taken place after a certain time
        before: An epoch timestamp to use for filtering activities that have taken place before a certain time
        page: The page of activities (default=1)
        per_page: How many activities per page (default=30)
    """
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
    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")

    # Persist raw tokens for later refresh usage via the public save tool
    save_result = await save_tokens({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": tokens.get("expires_at"),
        "expires_in": tokens.get("expires_in"),
        "athlete": tokens.get("athlete"),
        "token_type": tokens.get("token_type"),
        "scope": tokens.get("scope"),
    })

    # return {"tokens": tokens, "access_token": access_token, "refresh_token": refresh_token}

    # Build URL with query parameters
    params_dict = {}
    if after is not None:
        params_dict["after"] = after
    if before is not None:
        params_dict["before"] = before
    if page is not None:
        params_dict["page"] = page
    if per_page is not None:
        params_dict["per_page"] = per_page
    
    # Default per_page to 30 if not specified (Strava API default)
    if per_page is None:
        params_dict["per_page"] = 30
    
    query_string = urllib.parse.urlencode(params_dict)
    url = f"https://www.strava.com/api/v3/athlete/activities?{query_string}"
    
    # Debug output
    print(f"DEBUG: Requesting URL: {url}")
    
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {access_token}"
    }

    response = requests.get(url, headers=headers)
    activities_data = response.json()
    print(f"DEBUG: Response status: {response.status_code}, Activities count: {len(activities_data) if isinstance(activities_data, list) else 0}")
    
    return {
        "activities": activities_data,
        "tokens": {
            "access_token_preview": _mask_secret(access_token),
            "refresh_token_preview": _mask_secret(refresh_token),
            "expires_at": tokens.get("expires_at"),
            "expires_in": tokens.get("expires_in"),
        },
        "save": save_result,
        "first_time_flow": True,
    }

@mcp.tool("strava.athlete.stats-with-token")
async def get_athlete_stats_with_token(
    access_token: str,
    after: int | None = None,
    before: int | None = None,
    page: int | None = None,
    per_page: int | None = None
) -> dict:
    """Get athlete activities using an existing access token with optional filters.
    
    Args:
        access_token: Strava access token
        after: An epoch timestamp to use for filtering activities that have taken place after a certain time
        before: An epoch timestamp to use for filtering activities that have taken place before a certain time
        page: The page of activities (default=1)
        per_page: How many activities per page (default=30)
    """
    if not access_token:
        return {"error": "access token is required"}
    
    # Build URL with query parameters
    params = []
    if after is not None:
        params.append(f"after={after}")
    if before is not None:
        params.append(f"before={before}")
    if page is not None:
        params.append(f"page={page}")
    if per_page is not None:
        params.append(f"per_page={per_page}")
    
    # Default per_page to 30 if not specified (Strava API default)
    if per_page is None:
        params.append("per_page=30")
    
    query_string = "&".join(params) if params else ""
    url = f"https://www.strava.com/api/v3/athlete/activities?{query_string}"
    
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {access_token}"
    }

    try:
        response = requests.get(url, headers=headers)
        
        # Include debug information in the response
        debug_info = {
            "request_url": url,
            "response_status": response.status_code,
            "response_headers": dict(response.headers),
            "filters_applied": {
                "after": after,
                "before": before,
                "page": page,
                "per_page": per_page
            }
        }
        
        response.raise_for_status()
        
        activities_data = response.json()
        
        return {
            "activities": activities_data,
            "count": len(activities_data) if isinstance(activities_data, list) else 0,
            "status": "success",
            "debug": debug_info
        }
        
    except requests.HTTPError as e:
        return {
            "error": "API request failed", 
            "status_code": response.status_code, 
            "response": response.text,
            "debug": {
                "request_url": url,
                "response_status": response.status_code,
                "response_headers": dict(response.headers),
                "filters_applied": {
                    "after": after,
                    "before": before,
                    "page": page,
                    "per_page": per_page
                }
            }
        }
    except Exception as e:
        return {
            "error": "API request failed", 
            "error_message": str(e),
            "debug": {
                "request_url": url,
                "filters_applied": {
                    "after": after,
                    "before": before,
                    "page": page,
                    "per_page": per_page
                }
            }
        }

@mcp.tool("strava.debug.test-connection")
async def test_strava_connection(access_token: str) -> dict:
    """Test the Strava API connection and token validity with debug information."""
    if not access_token:
        return {"error": "access token is required"}
    
    # Test 1: Simple request without filters
    url_no_filters = "https://www.strava.com/api/v3/athlete/activities?per_page=5"
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {access_token}"
    }
    
    try:
        response = requests.get(url_no_filters, headers=headers)
        
        debug_info = {
            "test_url": url_no_filters,
            "response_status": response.status_code,
            "response_headers": dict(response.headers),
            "content_length": len(response.content) if response.content else 0
        }
        
        if response.status_code == 200:
            activities_data = response.json()
            debug_info["activities_count"] = len(activities_data) if isinstance(activities_data, list) else 0
            debug_info["sample_activity"] = activities_data[0] if activities_data and len(activities_data) > 0 else None
            
            return {
                "status": "success",
                "message": "Connection successful",
                "activities": activities_data,
                "debug": debug_info
            }
        else:
            debug_info["response_text"] = response.text
            return {
                "status": "error",
                "message": f"API returned status {response.status_code}",
                "debug": debug_info
            }
            
    except Exception as e:
        return {
            "status": "error",
            "message": f"Request failed: {str(e)}",
            "debug": {
                "test_url": url_no_filters,
                "error": str(e)
            }
        }

@mcp.tool("strava.auth.save")
async def save_tokens(tokens: dict | None = None) -> dict:
    """Save tokens to local disk at ~/.strava_mcp_tokens.json. If tokens is not provided, no-op with error."""
    if not tokens or not isinstance(tokens, dict):
        return {"error": "tokens dict is required"}
    result = _save_tokens_to_disk(tokens)
    if not result.get("ok"):
        return {"error": "failed to save tokens", **result}
    return {"ok": True, "path": result.get("path")}


@mcp.tool("strava.auth.load")
async def load_tokens() -> dict:
    """Load tokens from local disk at ~/.strava_mcp_tokens.json"""
    result = _load_tokens_from_disk()
    if not result.get("ok"):
        return {"error": result.get("error"), "path": result.get("path")}
    tokens = result.get("tokens", {})
    # Mask sensitive values for public responses
    masked = dict(tokens)
    if "access_token" in masked:
        masked["access_token_preview"] = _mask_secret(masked.pop("access_token"))
    if "refresh_token" in masked:
        masked["refresh_token_preview"] = _mask_secret(masked.pop("refresh_token"))
    return {"ok": True, "tokens": masked, "path": result.get("path")}


@mcp.tool("strava.auth.status")
async def auth_status() -> dict:
    """Return current auth/token environment status and recommended next action.

    This tool intentionally masks secrets. Use it to decide whether to call
    `strava.auth.url` (first-time) or a refresh/refresh-and-stats flow.
    """
    path = _get_token_store_path()
    token_file_exists = os.path.exists(path)
    refresh_preview = None
    token_details = None
    if token_file_exists:
        loaded = _load_tokens_from_disk()
        if loaded.get("ok"):
            token_details = loaded.get("tokens", {})
            refresh_preview = _mask_secret(token_details.get("refresh_token"))

    client_id_present = bool(os.getenv("STRAVA_CLIENT_ID"))
    client_secret_present = bool(os.getenv("STRAVA_CLIENT_SECRET"))

    if not token_file_exists or not refresh_preview:
        recommended = "call strava.auth.url (first-time authorization)"
    elif not (client_id_present and client_secret_present):
        recommended = "set STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET in environment"
    else:
        recommended = "call strava.athlete.refresh-and-stats or strava.auth.refresh"

    return {
        "token_file_path": path,
        "token_file_exists": token_file_exists,
        "refresh_token_preview": refresh_preview,
        "env_client_id_present": client_id_present,
        "env_client_secret_present": client_secret_present,
        "recommended_action": recommended,
    }

@mcp.tool("strava.athlete.refresh-and-stats")
async def refresh_and_get_stats(
    client_id: int | None = None, 
    client_secret: str | None = None,
    after: int | None = None,
    before: int | None = None,
    page: int | None = None,
    per_page: int | None = None
) -> dict:
    """Load saved refresh token, refresh access token, save it, then fetch activities with optional filters.
    
    Args:
        client_id: Strava client ID
        client_secret: Strava client secret
        after: An epoch timestamp to use for filtering activities that have taken place after a certain time
        before: An epoch timestamp to use for filtering activities that have taken place before a certain time
        page: The page of activities (default=1)
        per_page: How many activities per page (default=30)
    """
    # Use internal disk loader to obtain raw saved tokens (do not use public tool here)
    load_result = _load_tokens_from_disk()
    if not load_result.get("ok"):
        return {"error": "no saved tokens", "details": load_result}
    saved = load_result.get("tokens", {})
    refresh_token = saved.get("refresh_token")
    if not refresh_token:
        return {"error": "refresh_token not found in saved tokens"}

    # Call refresh; refresh_access_token will persist raw tokens to disk but
    # it returns a masked public response.
    refreshed_public = await refresh_access_token(refresh_token=refresh_token, client_id=client_id, client_secret=client_secret)
    if "error" in refreshed_public:
        return {"error": "refresh failed", "details": refreshed_public}

    # Reload raw tokens from disk (saved by refresh_access_token) to use for API calls
    reloaded = _load_tokens_from_disk()
    if not reloaded.get("ok"):
        return {"error": "failed to reload tokens after refresh", "details": reloaded}
    tokens_raw = reloaded.get("tokens", {})
    access_token = tokens_raw.get("access_token")
    if not access_token:
        return {"error": "no access_token after refresh"}

    # Fetch activities with new token and filters
    activities = await get_athlete_stats_with_token(
        access_token=access_token,
        after=after,
        before=before,
        page=page,
        per_page=per_page
    )
    return {
        "activities": activities,
        "tokens": {
            "access_token_preview": _mask_secret(access_token),
            "refresh_token_preview": _mask_secret(tokens_raw.get("refresh_token")),
            "expires_at": tokens_raw.get("expires_at"),
            "expires_in": tokens_raw.get("expires_in"),
        },
        "debug": {
            "filters_applied": {
                "after": after,
                "before": before,
                "page": page,
                "per_page": per_page
            }
        }
    }

@mcp.tool("strava.session.start")
async def start_session(
    client_id: int | None = None, 
    client_secret: str | None = None,
    after: int | None = None,
    before: int | None = None,
    page: int | None = None,
    per_page: int | None = None
) -> dict:
    """Start a session: if a refresh token exists, refresh and fetch; otherwise return auth URL.
    
    Args:
        client_id: Strava client ID
        client_secret: Strava client secret
        after: An epoch timestamp to use for filtering activities that have taken place after a certain time
        before: An epoch timestamp to use for filtering activities that have taken place before a certain time
        page: The page of activities (default=1)
        per_page: How many activities per page (default=30)
    """
    token_path = _get_token_store_path()
    if os.path.exists(token_path):
        loaded = _load_tokens_from_disk()
        if loaded.get("ok"):
            saved = loaded.get("tokens", {})
            refresh_token = saved.get("refresh_token")
            if isinstance(refresh_token, str) and refresh_token.strip():
                result = await refresh_and_get_stats(
                    client_id=client_id, 
                    client_secret=client_secret,
                    after=after,
                    before=before,
                    page=page,
                    per_page=per_page
                )
                return {**result, "used_token_file": token_path}
    # Fall back to auth URL flow
    else:
        url = await get_auth_url(client_id=client_id)
        return {"auth_url": url, "token_file_checked": token_path}

#@mcp.prompt
#def greet_user_prompt(question: str) -> str:
    #"""Generates a message orchestrating mcp tools"""
    #return f"""
    #Return a message for a user called '{question}'. 
    #if the user is asking, use a formal style, else use a street style.
    #"""

if __name__ == "__main__":
    mcp.run(transport="stdio")  # Run the server, using standard input/output for communication