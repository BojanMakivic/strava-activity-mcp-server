# Strava Activity MCP Server
![Python Package](https://github.com/tomekkorbak/strava-mcp-server/actions/workflows/python-package.yml/badge.svg)
[![License: GNU](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://opensource.org/licenses/gpl-3-0)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue?logo=python&logoColor=white)](https://www.python.org/downloads/release/python-3130/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/strava-activity-mcp-server)](https://pypistats.org/packages/strava-activity-mcp-server)

![image](https://github.com/user-attachments/assets/4bb214ca-1132-4e63-9390-d6eaddab50be)



A small Model Context Protocol (MCP) server that exposes your Strava athlete data to language-model tooling.

After the first browser-based authorization, the server uses the saved `refresh_token` to automatically refresh your session; no further URL-redirected logins are required on subsequent runs.

This package provides a lightweight MCP server which communicates with the Strava API and exposes a few helper tools (authorization URL, token exchange/refresh, and fetching athlete activities) that language models or other local tools can call.

The project is intended to be used locally (for example with Claude MCP integrations) and is published on PyPI as `strava-activity-mcp-server`.

## Installation

Install from PyPI with pip (recommended inside a virtual environment):

```powershell
pip install strava-activity-mcp-server
```

## Requirements

- Python >= 3.13 (see `pyproject.toml`)
- The package depends on `mcp[cli]` and `requests` (installed from PyPI).

## Quick start

After installing, you can run the MCP server using the provided console script or by importing and calling `main()`.

Run via the console script (entry point defined in `pyproject.toml`):

```cmd
strava-activity-mcp-server
```

Or, from Python:

```python
from strava_activity_mcp_server import main
main()
```

By default the server starts the MCP runtime; when used with an MCP-aware client (for example Msty MCP orsome other MCP integrations such Claude, LM Tool and etc.) the exposed tools become callable.

## Authentication (Strava OAuth)

This server requires Strava OAuth credentials to access athlete data. You will need:

- STRAVA_CLIENT_ID
- STRAVA_CLIENT_SECRET

Steps:

1. Create a Strava API application at https://www.strava.com/settings/api and note your Client ID and Client Secret. Use `localhost` as the Authorization Callback Domain.
2. Initial authorization: call the `strava://auth/url` tool to generate an authorization URL (see IMAGE below), open it in your browser, and grant access. This step is only needed the first time to obtain an authorization code.

   ![auth](https://github.com/user-attachments/assets/a348ccc7-a4be-49fb-8f79-b88f9d80cfc9)

3. Copy the `code` from the redirected URL (Image below). Use the provided tools to exchange it for access/refresh tokens.

   ![code](https://github.com/user-attachments/assets/0bb54edb-c9f9-4416-8fb2-c7e0a38d11c9)


4. After the initial authorization, a token file named `strava_mcp_tokens.json` is created and stored in your home directory (for example on Windows: `C:\\Users\\<YourUserName>\\strava_mcp_tokens.json`). This file contains your `refresh_token`, which will be used automatically for subsequent logins. After the first authorization you do not need to open the browser flow again; future runs refresh the access token from the locally stored `refresh_token`.




## Exposed Tools (what the server provides)

The MCP server exposes the following tools (tool IDs shown). These map to functions in `src/strava_activity_mcp_server/strava_activity_mcp_server.py` and cover both initial authorization and subsequent refresh flows:

- `strava://auth/url` — Build the Strava OAuth authorization URL.
  - Inputs: `client_id` (int, optional; reads `STRAVA_CLIENT_ID` if omitted)
  - Output: Authorization URL string
- `strava://auth/refresh` — Refresh an access token using a refresh token.
  - Inputs: `refresh_token` (str), `client_id` (int, optional), `client_secret` (str, optional)
  - Output: `{ access_token, refresh_token, expires_at, expires_in }`
- `strava://athlete/stats` — Exchange an authorization `code` for tokens and then fetch recent activities.
  - Inputs: `code` (str), `client_id` (int, optional), `client_secret` (str, optional)
  - Output: `{ activities, tokens, save }`
- `strava://athlete/stats-with-token` — Fetch recent activities using an existing access token.
  - Inputs: `access_token` (str)
  - Output: Activity list (JSON)
- `strava://auth/save` — Save tokens to `~\strava_mcp_tokens.json`.
  - Inputs: `tokens` (dict)
  - Output: `{ ok, path }` or error
- `strava://auth/load` — Load tokens from `~\strava_mcp_tokens.json`.
  - Inputs: none
  - Output: `{ ok, tokens, path }` or error
- `strava://athlete/refresh-and-stats` — Load saved refresh token, refresh access token, save it, and fetch activities.
  - Inputs: `client_id` (int, optional), `client_secret` (str, optional)
  - Output: `{ activities, tokens }`
- `strava://session/start` — Convenience entry: if tokens exist, refresh and fetch; otherwise return an auth URL to begin initial authorization.
  - Inputs: `client_id` (int, optional), `client_secret` (str, optional)
  - Output: Either `{ activities, tokens }` or `{ auth_url, token_file_checked }`

These tools are intended to be called by MCP clients.

## Example flows

1) Get an authorization URL and retrieve tokens

- Call `strava://auth/url` with your `client_id` and open the returned URL in your browser.
- After authorizing, Strava will provide a `code`.

2) Fetch recent activities

- Use `strava://athlete/stats` with a valid access token. If the access token is expired, use the refresh flow to get a new access token.

### Client config example and quick inspector test

Any MCP-capable client can launch the server using a config similar to the following (example file often called `config.json`. Be sure to enter your values here):

```json
{
  "command": "uvx",
  "args": [
    "strava-activity-mcp-server"
  ],
  "env": {
    "STRAVA_CLIENT_ID": "12345",
    "STRAVA_CLIENT_SECRET": "e1234a12d12345f12c1f12345a123bba1d12c1"
  }
}
```

To quickly test the server using the Model Context Protocol inspector tool, run:

```powershell
npx @modelcontextprotocol/inspector uvx strava-activity-mcp-server
```

This will attempt to start the server with the `uvx` transport and connect the inspector to the running MCP server instance named `strava-activity-mcp-server`.

## Chat example using MCP in Msty Studio

![chat_1](https://github.com/user-attachments/assets/460cced5-15b3-41eb-9805-72966826ede8)
![chat_2](https://github.com/user-attachments/assets/9ded03f3-0f86-400e-8ebc-c414d0346257)
![chat_3](https://github.com/user-attachments/assets/d793c9a5-8fb2-430e-a0bf-679903cf3f97)
![chat_4](https://github.com/user-attachments/assets/4a459c31-3b42-4c32-8685-e6dd851dadca)


## Contributing

Contributions are welcome. Please open issues or pull requests that include a clear description and tests where applicable.

## License

This project is licensed under the GNU GENERAL PUBLIC LICENSE — see the `LICENSE` file for details.

## Links

- Source: repository root
- Documentation note: see `README.md` for an example MCP configuration





