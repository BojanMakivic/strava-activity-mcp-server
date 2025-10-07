Title: strava-mcp-server

URL Source: http://pypi.org/project/strava-mcp-server/

Markdown Content:
Project description
-------------------

![Image 1: Python Package](https://pypi-camo.freetls.fastly.net/0ecf904318113383d77ec39a9c48b8ba0d2baf38/68747470733a2f2f6769746875622e636f6d2f746f6d656b6b6f7262616b2f7374726176612d6d63702d7365727665722f776f726b666c6f77732f507974686f6e2532305061636b6167652f62616467652e737667)[![Image 2: License: MIT](https://pypi-camo.freetls.fastly.net/8645b002dd7ec1b54275a80574942e7a318e03c6/68747470733a2f2f696d672e736869656c64732e696f2f62616467652f4c6963656e73652d4d49542d79656c6c6f772e737667)](https://opensource.org/licenses/MIT)[![Image 3: Python 3.10](https://pypi-camo.freetls.fastly.net/ea10074cb289a2913e3e6b97173e8b2ce3051997/68747470733a2f2f696d672e736869656c64732e696f2f62616467652f707974686f6e2d332e31302d626c75652e737667)](https://www.python.org/downloads/release/python-3100/)

A [Model Context Protocol](https://modelcontextprotocol.io/introduction) (MCP) server that provides access to the Strava API. It allows language models to query athlete activities data from the Strava API.

Available Tools
---------------

The server exposes the following tools:

### Activities Queries

*   `get_activities(limit: int = 10)`: Get the authenticated athlete's recent activities
*   `get_activities_by_date_range(start_date: str, end_date: str, limit: int = 30)`: Get activities within a specific date range
*   `get_activity_by_id(activity_id: int)`: Get detailed information about a specific activity
*   `get_recent_activities(days: int = 7, limit: int = 10)`: Get activities from the past X days

Dates should be provided in ISO format (`YYYY-MM-DD`).

Activity Data Format
--------------------

The server returns activity data with consistent field names and units:

| Field | Description | Unit |
| --- | --- | --- |
| `name` | Activity name | - |
| `sport_type` | Type of sport | - |
| `start_date` | Start date and time | ISO 8601 |
| `distance_metres` | Distance | meters |
| `elapsed_time_seconds` | Total elapsed time | seconds |
| `moving_time_seconds` | Moving time | seconds |
| `average_speed_mps` | Average speed | meters per second |
| `max_speed_mps` | Maximum speed | meters per second |
| `total_elevation_gain_metres` | Total elevation gain | meters |
| `elev_high_metres` | Highest elevation | meters |
| `elev_low_metres` | Lowest elevation | meters |
| `calories` | Calories burned | kcal |
| `start_latlng` | Start coordinates | [lat, lng] |
| `end_latlng` | End coordinates | [lat, lng] |

Authentication
--------------

To use this server, you'll need to authenticate with the Strava API. Follow these steps:

1.   Create a Strava API application:

    *   Go to [Strava API Settings](https://www.strava.com/settings/api)
    *   Create an application to get your Client ID and Client Secret
    *   Set the Authorization Callback Domain to `localhost`

2.   Get your refresh token:

    *   Use the included `get_strava_token.py` script:

python get_strava_token.py

    *   Follow the prompts to authorize your application
    *   The script will save your tokens to a `.env` file

3.   Set environment variables: The server requires the following environment variables:

    *   `STRAVA_CLIENT_ID`: Your Strava API Client ID
    *   `STRAVA_CLIENT_SECRET`: Your Strava API Client Secret
    *   `STRAVA_REFRESH_TOKEN`: Your Strava API Refresh Token

Usage
-----

### Claude for Desktop

Update your `claude_desktop_config.json` (located in `~/Library/Application\ Support/Claude/claude_desktop_config.json` on macOS and `%APPDATA%/Claude/claude_desktop_config.json` on Windows) to include the following:

{
 "mcpServers": {
 "strava": {
 "command": "uvx",
 "args": [
 "strava-mcp-server"
 ],
 "env": {
 "STRAVA_CLIENT_ID": "YOUR_CLIENT_ID",
 "STRAVA_CLIENT_SECRET": "YOUR_CLIENT_SECRET",
 "STRAVA_REFRESH_TOKEN": "YOUR_REFRESH_TOKEN"
 }
 }
 }
}

### Claude Web

For Claude Web, you can run the server locally and connect it using the MCP extension.

Example Queries
---------------

Once connected, you can ask Claude questions like:

*   "What are my recent activities?"
*   "Show me my activities from last week"
*   "What was my longest run in the past month?"
*   "Get details about my latest cycling activity"

Error Handling
--------------

The server provides human-readable error messages for common issues:

*   Invalid date formats
*   API authentication errors
*   Network connectivity problems

License
-------

This project is licensed under the MIT License - see the LICENSE file for details.

Download files
--------------

Download the file for your platform. If you're not sure which to choose, learn more about [installing packages](https://packaging.python.org/tutorials/installing-packages/ "External link").

### Source Distribution

### Built Distribution

Filter files by name, interpreter, ABI, and platform.

If you're not sure about the file name format, learn more about [wheel file names](https://packaging.python.org/en/latest/specifications/binary-distribution-format/ "External link").

Copy a direct link to the current filters [](https://pypi.org/project/strava-mcp-server/#files)

File name

Interpreter

ABI

Platform

File details
------------

Details for the file `strava_mcp_server-0.1.3.tar.gz`.

### File metadata

*    Download URL: [strava_mcp_server-0.1.3.tar.gz](https://files.pythonhosted.org/packages/c5/af/6d0b992c2d5a01b5494d6388e714072ccd47d84a1d0e4ffe9c4e077ad877/strava_mcp_server-0.1.3.tar.gz)
*   Upload date:  Feb 28, 2025 
*    Size: 6.1 kB 
*   Tags: Source
*    Uploaded using Trusted Publishing? No 
*   Uploaded via: uv/0.6.0

### File hashes

Hashes for strava_mcp_server-0.1.3.tar.gz| Algorithm | Hash digest |  |
| --- | --- | --- |
| SHA256 | `8713d2e206dec10e65a67d22220677df221c02247ad4bcf0a7a4e0ae2a682202` |  |
| MD5 | `95d9c00594437c032360dd2d3da1667f` |  |
| BLAKE2b-256 | `c5af6d0b992c2d5a01b5494d6388e714072ccd47d84a1d0e4ffe9c4e077ad877` |  |

[See more details on using hashes here.](https://pip.pypa.io/en/stable/topics/secure-installs/#hash-checking-mode "External link")

File details
------------

Details for the file `strava_mcp_server-0.1.3-py3-none-any.whl`.

### File metadata

*    Download URL: [strava_mcp_server-0.1.3-py3-none-any.whl](https://files.pythonhosted.org/packages/ed/ae/72c2ea3d9a59a235f89ad0013741add100df968153e6c737b2d199b9a9ba/strava_mcp_server-0.1.3-py3-none-any.whl)
*   Upload date:  Feb 28, 2025 
*    Size: 7.5 kB 
*   Tags: Python 3
*    Uploaded using Trusted Publishing? No 
*   Uploaded via: uv/0.6.0

### File hashes

Hashes for strava_mcp_server-0.1.3-py3-none-any.whl| Algorithm | Hash digest |  |
| --- | --- | --- |
| SHA256 | `b048109b3bae7601fcb65285405c38424996bccd59904ba443bb0a7150b00cc8` |  |
| MD5 | `843e3701478e827fc36dfcf9c8e539aa` |  |
| BLAKE2b-256 | `edae72c2ea3d9a59a235f89ad0013741add100df968153e6c737b2d199b9a9ba` |  |

[See more details on using hashes here.](https://pip.pypa.io/en/stable/topics/secure-installs/#hash-checking-mode "External link")