# Aent

This repository contains the MCP server that fetches activity data for a given user from Strava.

## Purpose

Aent.md documents the "Aent" component (agent) used to interact with the Strava API and the MCP server. It explains responsibilities, usage, and configuration for maintainers and integrators.

## Responsibilities

- Authenticate with the Strava API and manage tokens.
- Fetch activity data for a given user (activities, streams, segments as needed).
- Normalize and validate activity payloads before forwarding to downstream systems.
- Retry and error handling for transient failures.
- Emit logs and metrics for observability.

## Configuration

Configure the agent via environment variables or a configuration file. Typical settings:

- STRAVA_CLIENT_ID - Strava API client id
- STRAVA_CLIENT_SECRET - Strava API client secret
- STRAVA_REDIRECT_URI - Redirect URI for OAuth flow
- STRAVA_ACCESS_TOKEN - Access token (if pre-obtained)
- STRAVA_REFRESH_TOKEN - Refresh token (if pre-obtained)
- MCP_SERVER_URL - URL of the MCP server to forward data to
- LOG_LEVEL - Logging verbosity (debug, info, warn, error)
- RETRY_MAX_ATTEMPTS - Max retry attempts for transient requests

## Usage

1. Ensure the necessary environment variables are set.
2. Run the MCP server (see repository README for start commands).
3. The agent will authenticate and begin fetching activity data for configured users.

## Development

- Follow existing project conventions (tests, linting, type checks).
- Add unit tests for authentication and data normalization logic.
- Use feature branches and open pull requests for changes.

## Troubleshooting

- Check logs for authentication errors or rate-limit responses from Strava.
- Confirm tokens and client credentials are valid.
- Inspect network connectivity to the Strava API and MCP server endpoints.

## Contact

Maintainer: Bojan Makivic
Repository: https://github.com/BojanMakivic/strava-activity-mcp-server

## License

Follow the repository license (see LICENSE file if present).
