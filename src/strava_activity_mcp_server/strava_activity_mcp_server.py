import sys
import os
from mcp.server.fastmcp import FastMCP  # Import FastMCP, the quickstart server base
mcp = FastMCP("Strava")  # Initialize an MCP server instance with a descriptive name
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import requests
import urllib.parse
import json
import math
import time
from statistics import mean, stdev
from typing import Any, Dict, Literal

TOKEN_STORE_FILENAME = "strava_mcp_tokens.json"
MAX_STRAVA_PER_PAGE = 200
DEFAULT_PER_PAGE = 50
DEFAULT_MAX_PAGES = 10
DEFAULT_RETRY_COUNT = 2
RETRYABLE_HTTP_STATUS = {429, 500, 502, 503, 504}
DEFAULT_DETAIL_LEVEL = "summary"
MAX_DETAIL_ACTIVITY_ROWS = 100


def _banister_trimp_male(*, duration_seconds: float, avg_hr: float, hr_rest: float, hr_max: float) -> float:
    """Banister TRIMP (male).

    Kept for backwards compatibility; prefer `_banister_trimp(..., sex=...)`.
    """
    return _banister_trimp(duration_seconds=duration_seconds, avg_hr=avg_hr, hr_rest=hr_rest, hr_max=hr_max, sex="male")


def _banister_trimp(
    *,
    duration_seconds: float,
    avg_hr: float,
    hr_rest: float,
    hr_max: float,
    sex: Literal["male", "female"],
) -> float:
    """Banister TRIMP.

    Formula:
        TRIMP = duration(min) * HRr * A * exp(B * HRr)
    where HRr = (avg_hr - hr_rest) / (hr_max - hr_rest), clamped to [0, 1].

    Constants:
        male:   A=0.64, B=1.92
        female: A=0.86, B=1.67
    """
    duration_min = max(0.0, duration_seconds / 60.0)
    denom = (hr_max - hr_rest)
    if denom <= 0:
        return float("nan")
    hrr = (avg_hr - hr_rest) / denom
    hrr = min(1.0, max(0.0, hrr))
    if sex == "female":
        a, b = 0.86, 1.67
    else:
        a, b = 0.64, 1.92
    return duration_min * hrr * a * math.exp(b * hrr)

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


def _extract_activities(payload: Any) -> list[dict[str, Any]] | None:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("activities"), list):
        return [x for x in payload.get("activities") if isinstance(x, dict)]
    return None


def _token_status_from_store(raw_tokens: dict[str, Any] | None) -> dict[str, Any]:
    tokens = raw_tokens or {}
    return {
        "token_source": "local_store",
        "refresh_token_present": bool(tokens.get("refresh_token")),
        "access_token_present": bool(tokens.get("access_token")),
        "expires_at_present": bool(tokens.get("expires_at")),
    }


def _summarize_activity_window(activities: list[dict[str, Any]]) -> dict[str, Any]:
    if not activities:
        return {
            "total_activities": 0,
            "date_start": None,
            "date_end": None,
            "sports": {},
        }
    starts = [a.get("start_date_local") for a in activities if isinstance(a, dict) and a.get("start_date_local")]
    sports: dict[str, int] = {}
    for a in activities:
        if not isinstance(a, dict):
            continue
        sport = str(a.get("sport_type") or a.get("type") or "Unknown")
        sports[sport] = sports.get(sport, 0) + 1
    return {
        "total_activities": len(activities),
        "date_start": min(starts) if starts else None,
        "date_end": max(starts) if starts else None,
        "sports": sports,
    }


def _validate_paging(per_page: int, max_pages: int, page: int = 1) -> dict | None:
    if page <= 0:
        return {"error": "page must be >= 1"}
    if per_page <= 0:
        return {"error": "per_page must be > 0"}
    if per_page > MAX_STRAVA_PER_PAGE:
        return {"error": f"per_page must be <= {MAX_STRAVA_PER_PAGE}"}
    if max_pages <= 0:
        return {"error": "max_pages must be > 0"}
    return None


async def _fetch_activities_paged(
    *,
    access_token: str | None,
    after: int | None,
    before: int | None,
    per_page: int,
    max_pages: int,
    retry_count: int = DEFAULT_RETRY_COUNT,
) -> dict:
    validation_error = _validate_paging(per_page=per_page, max_pages=max_pages, page=1)
    if validation_error:
        return {
            "ok": False,
            "error": validation_error["error"],
            "meta": {
                "pages_attempted": 0,
                "pages_succeeded": 0,
                "items_fetched": 0,
                "stop_reason": "validation_error",
            },
        }

    used_access_token = access_token
    activities: list[dict[str, Any]] = []
    page = 1
    pages_attempted = 0
    pages_succeeded = 0
    stop_reason = "max_pages_reached"
    paging_error: dict[str, Any] | None = None
    last_page_size = 0

    # If no token is provided, bootstrap via refresh and consume page 1 from that response.
    if used_access_token is None:
        loaded = _load_tokens_from_disk()
        if not loaded.get("ok"):
            return {
                "ok": False,
                "error": "unable to load saved tokens",
                "details": loaded,
                "meta": {
                    "pages_attempted": pages_attempted,
                    "pages_succeeded": pages_succeeded,
                    "items_fetched": len(activities),
                    "stop_reason": "session_token_load_failed",
                },
            }

        saved = loaded.get("tokens", {})
        refresh_token = saved.get("refresh_token")
        if not isinstance(refresh_token, str) or not refresh_token.strip():
            return {
                "ok": False,
                "error": "refresh_token not found in saved tokens",
                "meta": {
                    "pages_attempted": pages_attempted,
                    "pages_succeeded": pages_succeeded,
                    "items_fetched": len(activities),
                    "stop_reason": "session_refresh_missing_refresh_token",
                },
            }

        refreshed = await _refresh_access_token_internal(refresh_token=refresh_token)
        if "error" in refreshed:
            return {
                "ok": False,
                "error": "unable to refresh/fetch activities",
                "details": refreshed,
                "meta": {
                    "pages_attempted": pages_attempted,
                    "pages_succeeded": pages_succeeded,
                    "items_fetched": len(activities),
                    "stop_reason": "session_refresh_failed",
                },
            }

        await save_tokens(refreshed)

        used_access_token = refreshed.get("access_token")
        if not isinstance(used_access_token, str) or not used_access_token.strip():
            return {
                "ok": False,
                "error": "refresh succeeded but no access_token returned",
                "details": refreshed,
                "meta": {
                    "pages_attempted": pages_attempted,
                    "pages_succeeded": pages_succeeded,
                    "items_fetched": len(activities),
                    "stop_reason": "session_refresh_missing_access_token",
                },
            }

        pages_attempted += 1
        session = await get_athlete_stats_with_token(
            access_token=used_access_token,
            after=after,
            before=before,
            page=1,
            per_page=per_page,
            retry_count=retry_count,
        )
        if session.get("status") != "success":
            return {
                "ok": False,
                "error": "unable to fetch first page",
                "details": session,
                "meta": {
                    "pages_attempted": pages_attempted,
                    "pages_succeeded": pages_succeeded,
                    "items_fetched": len(activities),
                    "stop_reason": "first_page_fetch_failed",
                },
            }

        first_page_batch = _extract_activities(session)
        if first_page_batch is None:
            paging_error = {
                "error": "unexpected first-page payload format",
                "payload_type": str(type(session)),
            }
            stop_reason = "api_error"
            return {
                "ok": False,
                "error": "unexpected first-page payload format",
                "details": paging_error,
                "meta": {
                    "pages_attempted": pages_attempted,
                    "pages_succeeded": pages_succeeded,
                    "items_fetched": len(activities),
                    "stop_reason": stop_reason,
                },
            }

        activities.extend(first_page_batch)
        pages_succeeded += 1
        last_page_size = len(first_page_batch)
        if len(first_page_batch) < per_page:
            stop_reason = "end_of_data"
            return {
                "ok": True,
                "activities": activities,
                "meta": {
                    "pages_attempted": pages_attempted,
                    "pages_succeeded": pages_succeeded,
                    "items_fetched": len(activities),
                    "last_page_size": last_page_size,
                    "per_page": per_page,
                    "max_pages": max_pages,
                    "stop_reason": stop_reason,
                    "used_saved_token_refresh": True,
                },
            }
        page = 2

    while page <= max_pages:
        pages_attempted += 1
        page_result = await get_athlete_stats_with_token(
            access_token=used_access_token,
            after=after,
            before=before,
            page=page,
            per_page=per_page,
            retry_count=retry_count,
        )
        batch = _extract_activities(page_result)
        if page_result.get("status") == "success" and isinstance(batch, list):
            activities.extend(batch)
            pages_succeeded += 1
            last_page_size = len(batch)
            if len(batch) < per_page:
                stop_reason = "end_of_data"
                break
            page += 1
            continue

        paging_error = page_result
        stop_reason = "api_error"
        break

    meta = {
        "pages_attempted": pages_attempted,
        "pages_succeeded": pages_succeeded,
        "items_fetched": len(activities),
        "last_page_size": last_page_size,
        "per_page": per_page,
        "max_pages": max_pages,
        "stop_reason": stop_reason,
        "used_saved_token_refresh": access_token is None,
    }
    if paging_error is not None:
        meta["paging_error"] = paging_error

    return {
        "ok": True,
        "activities": activities,
        "meta": meta,
    }

@mcp.tool("strava.auth.url")
async def get_auth_url(client_id: int | None = None):
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

async def _refresh_access_token_internal(
    *,
    refresh_token: str,
    client_id: int | None = None,
    client_secret: str | None = None,
) -> dict:
    """Refresh an access token using a refresh token (internal helper)."""
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
    return {
        "access_token": tokens.get("access_token"),
        "refresh_token": tokens.get("refresh_token"),
        "expires_at": tokens.get("expires_at"),
        "expires_in": tokens.get("expires_in")
    }


@mcp.tool("strava.auth.refresh")
async def refresh_access_token(
    refresh_token: str,
    client_id: int | None = None,
    client_secret: str | None = None,
) -> dict:
    """Refresh an access token using a refresh token.

    Security policy: token values are not returned to callers.
    """
    refreshed = await _refresh_access_token_internal(
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
    )
    if "error" in refreshed:
        return refreshed
    save_result = await save_tokens(refreshed)
    return {
        "ok": True,
        "message": "token refresh succeeded",
        "saved": bool(save_result.get("ok")),
        "token_status": {
            "token_source": "refresh_flow",
            "access_token_present": bool(refreshed.get("access_token")),
            "refresh_token_present": bool(refreshed.get("refresh_token")),
            "expires_at_present": bool(refreshed.get("expires_at")),
        },
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

    effective_page = 1 if page is None else int(page)
    effective_per_page = 30 if per_page is None else int(per_page)
    validation_error = _validate_paging(per_page=effective_per_page, max_pages=1, page=effective_page)
    if validation_error:
        return validation_error

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
    
    # Persist tokens for later refresh usage via the public save tool
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
    params = []
    if after is not None:
        params.append(f"after={after}")
    if before is not None:
        params.append(f"before={before}")
    params.append(f"page={effective_page}")
    params.append(f"per_page={effective_per_page}")
    
    query_string = "&".join(params) if params else ""
    url = f"https://www.strava.com/api/v3/athlete/activities?{query_string}"
    
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {access_token}"
    }

    response = requests.get(url, headers=headers)
    activities_data = response.json()

    return {
        "activities": activities_data,
        "token_status": {
            "token_source": "oauth_code_exchange",
            "access_token_present": bool(access_token),
            "refresh_token_present": bool(refresh_token),
            "expires_at_present": bool(tokens.get("expires_at")),
        },
        "save": save_result
    }

@mcp.tool("strava.athlete.stats-with-token")
async def get_athlete_stats_with_token(
    access_token: str,
    after: int | None = None,
    before: int | None = None,
    page: int | None = None,
    per_page: int | None = None,
    retry_count: int = DEFAULT_RETRY_COUNT,
) -> dict:
    """Get athlete activities using an existing access token with optional filters.
    
    Args:
        access_token: Strava access token
        after: An epoch timestamp to use for filtering activities that have taken place after a certain time
        before: An epoch timestamp to use for filtering activities that have taken place before a certain time
        page: The page of activities (default=1)
        per_page: How many activities per page (default=100)
    """
    if not access_token:
        return {"error": "access token is required"}

    effective_page = 1 if page is None else int(page)
    effective_per_page = DEFAULT_PER_PAGE if per_page is None else int(per_page)
    validation_error = _validate_paging(per_page=effective_per_page, max_pages=1, page=effective_page)
    if validation_error:
        return {
            "error": validation_error["error"],
            "status": "error",
            "debug": {
                "filters_applied": {
                    "after": after,
                    "before": before,
                    "page": effective_page,
                    "per_page": effective_per_page,
                }
            },
        }
    
    # Build URL with query parameters
    params = []
    if after is not None:
        params.append(f"after={after}")
    if before is not None:
        params.append(f"before={before}")
    params.append(f"page={effective_page}")
    params.append(f"per_page={effective_per_page}")
    
    query_string = "&".join(params) if params else ""
    url = f"https://www.strava.com/api/v3/athlete/activities?{query_string}"
    
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {access_token}"
    }

    try:
        total_attempts = max(1, int(retry_count) + 1)
        response = None
        for attempt in range(1, total_attempts + 1):
            response = requests.get(url, headers=headers)
            if response.status_code in RETRYABLE_HTTP_STATUS and attempt < total_attempts:
                time.sleep(0.35 * attempt)
                continue
            break
        if response is None:
            return {
                "error": "API request failed",
                "status": "error",
                "debug": {
                    "request_url": url,
                    "filters_applied": {
                        "after": after,
                        "before": before,
                        "page": effective_page,
                        "per_page": effective_per_page,
                    },
                    "retry_count": int(retry_count),
                    "attempts_used": 0,
                },
            }
        
        # Include debug information in the response
        debug_info = {
            "request_url": url,
            "response_status": response.status_code,
            "response_headers": dict(response.headers),
            "filters_applied": {
                "after": after,
                "before": before,
                "page": effective_page,
                "per_page": effective_per_page
            },
            "retry_count": int(retry_count),
            "attempts_used": attempt,
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
        response_status = response.status_code if response is not None else None
        response_headers = dict(response.headers) if response is not None else {}
        response_text = response.text if response is not None else ""
        return {
            "error": "API request failed", 
            "status_code": response_status,
            "response": response_text,
            "debug": {
                "request_url": url,
                "response_status": response_status,
                "response_headers": response_headers,
                "filters_applied": {
                    "after": after,
                    "before": before,
                    "page": effective_page,
                    "per_page": effective_per_page
                },
                "retry_count": int(retry_count),
                "attempts_used": attempt,
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
                    "page": effective_page,
                    "per_page": effective_per_page
                },
                "retry_count": int(retry_count),
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
    return {
        "ok": True,
        "path": result.get("path"),
        "token_status": _token_status_from_store(result.get("tokens") or {}),
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
        per_page: How many activities per page (default=100)
    """
    load_result = await load_tokens()
    if not load_result.get("ok"):
        return {"error": "no saved tokens", "details": load_result}
    raw = _load_tokens_from_disk()
    saved = raw.get("tokens", {}) if raw.get("ok") else {}
    refresh_token = saved.get("refresh_token")
    if not refresh_token:
        return {"error": "refresh_token not found in saved tokens"}

    refreshed = await _refresh_access_token_internal(refresh_token=refresh_token, client_id=client_id, client_secret=client_secret)
    if "error" in refreshed:
        return {"error": "refresh failed", "details": refreshed}

    # Save refreshed tokens
    await save_tokens(refreshed)

    access_token = refreshed.get("access_token")
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
        "token_status": {
            "token_source": "local_store_refresh",
            "access_token_present": bool(refreshed.get("access_token")),
            "refresh_token_present": bool(refreshed.get("refresh_token")),
            "expires_at_present": bool(refreshed.get("expires_at")),
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
        per_page: How many activities per page (default=100)
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
    url = await get_auth_url(client_id=client_id)
    return {"auth_url": url, "token_file_checked": token_path}


@mcp.tool("strava.athlete.fetch-all")
async def fetch_all_athlete_activities(
    access_token: str | None = None,
    after: int | None = None,
    before: int | None = None,
    per_page: int = DEFAULT_PER_PAGE,
    max_pages: int = DEFAULT_MAX_PAGES,
    retry_count: int = DEFAULT_RETRY_COUNT,
    detail_level: Literal["summary", "detailed"] = DEFAULT_DETAIL_LEVEL,
    detail_max_rows: int = MAX_DETAIL_ACTIVITY_ROWS,
) -> dict:
    """Fetch all athlete activities across pages with deterministic stop behavior.

    Stops when either:
    - a page returns fewer than `per_page` activities, or
    - `max_pages` is reached.
    """
    fetch_result = await _fetch_activities_paged(
        access_token=access_token,
        after=after,
        before=before,
        per_page=per_page,
        max_pages=max_pages,
        retry_count=retry_count,
    )
    if not fetch_result.get("ok"):
        return {
            "ok": False,
            "error": fetch_result.get("error", "failed to fetch activities"),
            "details": fetch_result.get("details"),
            "meta": fetch_result.get("meta", {}),
        }

    activities = fetch_result.get("activities", [])
    summary = _summarize_activity_window(activities)
    detail_rows = max(0, min(int(detail_max_rows), MAX_DETAIL_ACTIVITY_ROWS))
    data: dict[str, Any] = {"summary": summary}
    if detail_level == "detailed" and detail_rows > 0:
        data["activities"] = activities[:detail_rows]

    return {
        "ok": True,
        "data": data,
        "meta": fetch_result.get("meta", {}),
    }


@mcp.tool("strava://auth/url")
async def get_auth_url_alias(client_id: int | None = None):
    """URI alias for `strava.auth.url`."""
    return await get_auth_url(client_id=client_id)


@mcp.tool("strava://auth/refresh")
async def refresh_access_token_alias(
    refresh_token: str,
    client_id: int | None = None,
    client_secret: str | None = None,
) -> dict:
    """URI alias for `strava.auth.refresh`."""
    return await refresh_access_token(refresh_token=refresh_token, client_id=client_id, client_secret=client_secret)


@mcp.tool("strava://athlete/stats")
async def get_athlete_stats_alias(
    code: str,
    client_id: int | None = None,
    client_secret: str | None = None,
    after: int | None = None,
    before: int | None = None,
    page: int | None = None,
    per_page: int | None = None,
) -> dict:
    """URI alias for `strava.athlete.stats`."""
    return await get_athlete_stats(
        code=code,
        client_id=client_id,
        client_secret=client_secret,
        after=after,
        before=before,
        page=page,
        per_page=per_page,
    )


@mcp.tool("strava://athlete/stats-with-token")
async def get_athlete_stats_with_token_alias(
    access_token: str,
    after: int | None = None,
    before: int | None = None,
    page: int | None = None,
    per_page: int | None = None,
    retry_count: int = DEFAULT_RETRY_COUNT,
) -> dict:
    """URI alias for `strava.athlete.stats-with-token`."""
    return await get_athlete_stats_with_token(
        access_token=access_token,
        after=after,
        before=before,
        page=page,
        per_page=per_page,
        retry_count=retry_count,
    )


@mcp.tool("strava://auth/save")
async def save_tokens_alias(tokens: dict | None = None) -> dict:
    """URI alias for `strava.auth.save`."""
    return await save_tokens(tokens=tokens)


@mcp.tool("strava://auth/load")
async def load_tokens_alias() -> dict:
    """URI alias for `strava.auth.load`."""
    return await load_tokens()


@mcp.tool("strava://athlete/refresh-and-stats")
async def refresh_and_get_stats_alias(
    client_id: int | None = None,
    client_secret: str | None = None,
    after: int | None = None,
    before: int | None = None,
    page: int | None = None,
    per_page: int | None = None,
) -> dict:
    """URI alias for `strava.athlete.refresh-and-stats`."""
    return await refresh_and_get_stats(
        client_id=client_id,
        client_secret=client_secret,
        after=after,
        before=before,
        page=page,
        per_page=per_page,
    )


@mcp.tool("strava://session/start")
async def start_session_alias(
    client_id: int | None = None,
    client_secret: str | None = None,
    after: int | None = None,
    before: int | None = None,
    page: int | None = None,
    per_page: int | None = None,
) -> dict:
    """URI alias for `strava.session.start`."""
    return await start_session(
        client_id=client_id,
        client_secret=client_secret,
        after=after,
        before=before,
        page=page,
        per_page=per_page,
    )


@mcp.tool("strava://athlete/fetch-all")
async def fetch_all_athlete_activities_alias(
    access_token: str | None = None,
    after: int | None = None,
    before: int | None = None,
    per_page: int = DEFAULT_PER_PAGE,
    max_pages: int = DEFAULT_MAX_PAGES,
    retry_count: int = DEFAULT_RETRY_COUNT,
) -> dict:
    """URI alias for `strava.athlete.fetch-all`."""
    return await fetch_all_athlete_activities(
        access_token=access_token,
        after=after,
        before=before,
        per_page=per_page,
        max_pages=max_pages,
        retry_count=retry_count,
    )


@mcp.tool("strava.trimp.banister")
async def banister_trimp_report(
    access_token: str | None = None,
    sex: Literal["male", "female"] = "male",
    hr_rest: float = 52.0,
    hr_max: float = 190.0,
    after: int | None = None,
    before: int | None = None,
    per_page: int = DEFAULT_PER_PAGE,
    max_pages: int = DEFAULT_MAX_PAGES,
    detail_level: Literal["summary", "detailed"] = DEFAULT_DETAIL_LEVEL,
    detail_max_rows: int = MAX_DETAIL_ACTIVITY_ROWS,
) -> dict:
    """Compute Banister TRIMP (male) per activity and rank within-sport variability.

    Data fetching is delegated to existing MCP tools:
    - If `access_token` is provided, uses `strava.athlete.stats-with-token`.
    - Otherwise uses `strava.athlete.refresh-and-stats` to refresh from saved tokens,
      then continues paging with `strava.athlete.stats-with-token`.

    Returns a JSON report with activity TRIMP, variability (abs z-score within sport), and per-sport stats.
    """

    validation_error = _validate_paging(per_page=per_page, max_pages=max_pages, page=1)
    if validation_error:
        return validation_error
    if hr_max <= hr_rest:
        return {"error": "hr_max must be greater than hr_rest"}
    if sex not in ("male", "female"):
        return {"error": "sex must be 'male' or 'female'"}

    fetch_result = await _fetch_activities_paged(
        access_token=access_token,
        after=after,
        before=before,
        per_page=per_page,
        max_pages=max_pages,
    )
    if not fetch_result.get("ok"):
        return {
            "error": fetch_result.get("error", "failed to fetch paged activities"),
            "details": fetch_result.get("details"),
            "debug": {"paging": fetch_result.get("meta")},
        }

    activities = fetch_result.get("activities") or []
    debug: dict[str, Any] = {
        "filters": {"after": after, "before": before},
        "paging": fetch_result.get("meta", {}),
    }

    # Compute TRIMP per activity (only those with average HR)
    hr_rows: list[dict[str, Any]] = []
    for a in activities:
        if not isinstance(a, dict):
            continue

        # Strava includes `has_heartrate` for many activity types. Prefer it when present.
        has_hr = a.get("has_heartrate")
        if isinstance(has_hr, bool) and has_hr is False:
            continue

        avg_hr = a.get("average_heartrate")
        if avg_hr is None:
            continue
        try:
            avg_hr_f = float(avg_hr)
        except Exception:
            continue

        moving_time = a.get("moving_time")
        if moving_time is None:
            continue
        try:
            moving_time_s = int(moving_time)
        except Exception:
            continue

        sport_type = a.get("sport_type") or a.get("type") or "Unknown"

        trimp = _banister_trimp(
            duration_seconds=float(moving_time_s),
            avg_hr=avg_hr_f,
            hr_rest=float(hr_rest),
            hr_max=float(hr_max),
            sex=sex,
        )

        hr_rows.append(
            {
                "id": a.get("id"),
                "name": a.get("name") or "",
                "sport_type": str(sport_type),
                "start_date_local": a.get("start_date_local"),
                "moving_time_s": moving_time_s,
                "avg_hr": avg_hr_f,
                "trimp": trimp,
            }
        )

    by_sport: dict[str, list[dict[str, Any]]] = {}
    for r in hr_rows:
        by_sport.setdefault(str(r["sport_type"]), []).append(r)

    sport_stats: dict[str, dict[str, float]] = {}
    for sport, rows in by_sport.items():
        trimps = [float(x["trimp"]) for x in rows if not math.isnan(float(x["trimp"]))]
        if len(trimps) >= 2:
            mu = mean(trimps)
            sd = stdev(trimps)
        elif len(trimps) == 1:
            mu = trimps[0]
            sd = 0.0
        else:
            mu = float("nan")
            sd = float("nan")
        cv = (float(sd) / float(mu)) if (not math.isnan(float(mu)) and float(mu) != 0.0 and not math.isnan(float(sd))) else float("nan")
        sport_stats[sport] = {
            "count": float(len(rows)),
            "count_with_trimp": float(len(trimps)),
            "mean_trimp": float(mu),
            "stdev_trimp": float(sd),
            "cv_trimp": float(cv),
            "total_trimp": float(sum(trimps)),
        }

    # Rank sports by variability (low -> high). CV is often better for comparing sports with different means.
    sport_variability_low_to_high_cv = sorted(
        (
            {"sport_type": sport, **stats}
            for sport, stats in sport_stats.items()
            if not math.isnan(float(stats.get("cv_trimp", float("nan"))))
        ),
        key=lambda x: float(x["cv_trimp"]),
    )
    sport_variability_low_to_high_stdev = sorted(
        (
            {"sport_type": sport, **stats}
            for sport, stats in sport_stats.items()
            if not math.isnan(float(stats.get("stdev_trimp", float("nan"))))
        ),
        key=lambda x: float(x["stdev_trimp"]),
    )

    activity_rows: list[dict[str, Any]] = []
    for r in hr_rows:
        sport = str(r["sport_type"])
        mu = float(sport_stats[sport]["mean_trimp"])
        sd = float(sport_stats[sport]["stdev_trimp"])
        trimp = float(r["trimp"])
        if sd > 0 and not math.isnan(trimp) and not math.isnan(mu):
            variability = abs(trimp - mu) / sd
        else:
            variability = 0.0
        activity_rows.append({**r, "variability_score": float(variability)})

    activity_rows_sorted = sorted(activity_rows, key=lambda x: (float(x["variability_score"]), float(x["trimp"])))
    detail_rows = max(0, min(int(detail_max_rows), MAX_DETAIL_ACTIVITY_ROWS))

    all_trimps = [float(x["trimp"]) for x in activity_rows_sorted if not math.isnan(float(x["trimp"]))]
    overall_total_trimp = float(sum(all_trimps)) if all_trimps else 0.0
    overall_mean_trimp = float(mean(all_trimps)) if all_trimps else float("nan")

    result: dict[str, Any] = {
        "status": "success",
        "summary": {
            "total_activities_fetched": len(activities),
            "activities_with_average_hr": len(activity_rows_sorted),
            "sports_represented": len(by_sport),
            "total_trimp": overall_total_trimp,
            "mean_trimp": overall_mean_trimp,
        },
        "inputs": {
            "sex": sex,
            "hr_rest": float(hr_rest),
            "hr_max": float(hr_max),
            "after": after,
            "before": before,
            "per_page": per_page,
            "max_pages": max_pages,
            "used_saved_token_refresh": bool(fetch_result.get("meta", {}).get("used_saved_token_refresh")),
        },
        "sport_stats": sport_stats,
        "sport_variability": {
            "low_to_high_cv": sport_variability_low_to_high_cv,
            "low_to_high_stdev": sport_variability_low_to_high_stdev,
        },
        "debug": debug,
    }
    if detail_level == "detailed" and detail_rows > 0:
        result["activities"] = activity_rows_sorted[:detail_rows]
        result["detail_meta"] = {
            "detail_level": detail_level,
            "detail_rows_returned": min(detail_rows, len(activity_rows_sorted)),
            "detail_rows_cap": MAX_DETAIL_ACTIVITY_ROWS,
        }
    return result


@mcp.tool("strava://trimp/account-report")
async def banister_trimp_account_report(
    access_token: str | None = None,
    sex: Literal["male", "female"] = "male",
    hr_rest: float = 52.0,
    hr_max: float = 190.0,
    after: int | None = None,
    before: int | None = None,
    per_page: int = 200,
    max_pages: int = 10,
    detail_level: Literal["summary", "detailed"] = DEFAULT_DETAIL_LEVEL,
    detail_max_rows: int = MAX_DETAIL_ACTIVITY_ROWS,
) -> dict:
    """Alias for `strava.trimp.banister` kept for backwards compatibility with README/examples."""
    return await banister_trimp_report(
        access_token=access_token,
        sex=sex,
        hr_rest=hr_rest,
        hr_max=hr_max,
        after=after,
        before=before,
        per_page=per_page,
        max_pages=max_pages,
        detail_level=detail_level,
        detail_max_rows=detail_max_rows,
    )

#@mcp.prompt
#def greet_user_prompt(question: str) -> str:
    #"""Generates a message orchestrating mcp tools"""
    #return f"""
    #Return a message for a user called '{question}'. 
    #if the user is asking, use a formal style, else use a street style.
    #"""

if __name__ == "__main__":
    mcp.run(transport="stdio")  # Run the server, using standard input/output for communication