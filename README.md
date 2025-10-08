# Strava Activity MCP Server
![Image 1: Python Package](https://pypi-camo.freetls.fastly.net/0ecf904318113383d77ec39a9c48b8ba0d2baf38/68747470733a2f2f6769746875622e636f6d2f746f6d656b6b6f7262616b2f7374726176612d6d63702d7365727665722f776f726b666c6f77732f507974686f6e2532305061636b6167652f62616467652e737667)[![Image 2: License: GNU](https://pypi-camo.freetls.fastly.net/8de17537dd1659a5a076ce547de301e27c839e67/68747470733a2f2f696d672e736869656c64732e696f2f62616467652f4c6963656e73652d47504c76332d626c75652e737667)](https://opensource.org/licenses/gpl-3-0)[![Image 3: Python 3.13](https://pypi-camo.freetls.fastly.net/e4930d5d2a7b16dfd9891ecb7396975ef462cff3/68747470733a2f2f696d672e736869656c64732e696f2f707970692f707976657273696f6e732f696e6a782e7376673f6c6f676f3d707974686f6e266c6f676f436f6c6f723d7768697465)](https://www.python.org/downloads/release/python-3130/)

A small Model Context Protocol (MCP) server that exposes your Strava athlete data to language-model tooling.

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

```powershell
strava-activity-mcp-server
```

Or, from Python:

```python
from strava_activity_mcp_server import main
main()
```

By default the server starts the MCP runtime; when used with an MCP-aware client (for example Claude MCP integrations) the exposed tools become callable.

## Authentication (Strava OAuth)

This server requires Strava OAuth credentials to access athlete data. You will need:

- STRAVA_CLIENT_ID
- STRAVA_CLIENT_SECRET
- STRAVA_REFRESH_TOKEN (or a short-lived access token obtained from the authorization flow)

Steps:

1. Create a Strava API application at https://www.strava.com/settings/api and note your Client ID and Client Secret. Use `localhost` as the Authorization Callback Domain.
2. Open the authorization URL produced by the `strava://auth/url` tool (see Tools below) in a browser to obtain an authorization code.
3. Exchange the code for tokens using `strava://auth/token` or use the included helper to save refresh/access tokens to your environment.

For local testing you can also manually set the environment variables before running the server:

```powershell
$env:STRAVA_CLIENT_ID = "<your client id>";
$env:STRAVA_CLIENT_SECRET = "<your client secret>";
$env:STRAVA_REFRESH_TOKEN = "<your refresh token>";
strava-activity-mcp-server
```

Note: Keep secrets out of version control. Use a `.env` file and a tool such as `direnv` or your system secrets manager for convenience.

## Exposed Tools (what the server provides)

The MCP server exposes the following tools (tool IDs shown):

- `strava://auth/url` — Build the Strava OAuth authorization URL. Input: `client_id` (int). Output: URL string to open in a browser.
- `strava://auth/token` — Exchange an authorization code for access + refresh tokens. Inputs: `code` (str), `client_id` (int), `client_secret` (str). Output: token dict (with `access_token`, `refresh_token`).
- `strava://athlete/stats` — Fetch recent athlete activities. Input: `token` (str). Output: JSON with activity list.

These tools map to the functions implemented in `src/strava_activity_mcp_server/strava_activity_mcp_server.py` and are intended to be called by MCP clients.

## Example flows

1) Get an authorization URL and retrieve tokens

- Call `strava://auth/url` with your `client_id` and open the returned URL in your browser.
- After authorizing, Strava will provide a `code`. Call `strava://auth/token` with `code`, `client_id`, and `client_secret` to receive `access_token` and `refresh_token`.

2) Fetch recent activities

- Use `strava://athlete/stats` with a valid access token. If the access token is expired, use the refresh flow to get a new access token.

## Developer notes

- The package entry point calls `mcp.run()` which runs the MCP server. If you want to change transport or logging settings, modify `src/strava_activity_mcp_server/__init__.py` or `strava_activity_mcp_server.py`.
- The code uses the `requests` library for HTTP calls.


### Client config example and quick inspector test

Any MCP-capable client can launch the server using a config similar to the following (example file often called `config.json`):

```json
{
	"command": "uvx",
	"args": [
		"strava-activity-mcp-server"
	]
}
```

To quickly test the server using the Model Context Protocol inspector tool, run:

```powershell
npx @modelcontextprotocol/inspector uvx strava-mcp-server
```

This will attempt to start the server with the `uvx` transport and connect the inspector to the running MCP server instance named `strava-mcp-server`.


## Contributing

Contributions are welcome. Please open issues or pull requests that include a clear description and tests where applicable.

## License

This project is licensed under the GNU GENERAL PUBLIC LICENSE — see the `LICENSE` file for details.

## Links

- Source: repository root
- Documentation note: see `README.md` for an example MCP configuration


