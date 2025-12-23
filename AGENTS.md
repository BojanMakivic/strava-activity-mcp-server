# AGENTS.md

Project: strava-activity-mcp-server
Repository: BojanMakivic/strava-activity-mcp-server

Purpose
-------
This file provides concise, machine-friendly instructions to help an automated coding agent (or new contributor) understand, build, test, and modify the project.

Project overview
----------------
- This repository implements an MCP server that fetches Strava activity data for a given user.
- Language: Python
- Key behaviors: authenticate with Strava, fetch activity data, process or expose data via defined endpoints (see source code for details).

Quick start (developer)
-----------------------
1. Create and activate a virtual environment:
   - python -m venv .venv
   - source .venv/bin/activate   # macOS / Linux
   - .venv\Scripts\activate      # Windows

2. Install dependencies:
   - pip install -r requirements.txt

3. Environment variables (example):
   - STRAVA_CLIENT_ID
   - STRAVA_CLIENT_SECRET
   - STRAVA_REDIRECT_URI
   - DATABASE_URL (if applicable)
   - Use a .env file for local development and ensure it's excluded from VCS.

4. Run the development server / scripts:
   - Follow instructions in README.md or run the module entrypoint. Example:
     - python -m app   # adjust to actual entrypoint

Testing
-------
- Unit tests: pytest
  - Run: pytest
  - Run a single test: pytest path/to/test_file.py::test_name
- Linting / formatting:
  - black .              # formatting
  - ruff . or flake8 .   # linting (if configured)

Conventions & style
-------------------
- Follow PEP 8 and existing project conventions.
- Prefer small, well-tested changes. Add tests for new behavior or bug fixes.

Common tasks for agents
-----------------------
- Run tests and fix failing tests when making changes.
- Add type hints where beneficial and consistent with the codebase.
- Respect secrets handling rules and do not commit tokens.
- Search the repo for TODO or FIXME comments for starter tasks.

Security & secrets
------------------
- Never commit secrets or API tokens. Use environment variables or a secrets manager.
- When testing with real Strava credentials, rotate or revoke them if accidentally exposed.

Where to look in the repo
-------------------------
- README.md — human-focused project overview and instructions.
- Source modules (app/, src/, or package folders) — core implementation.
- tests/ — unit and integration tests.
- Config files (pyproject.toml, setup.cfg, requirements.txt) — linters/formatters and dependency info.

If you want me to modify files
------------------------------
- You asked to commit directly to the default branch. I will commit AGENTS.md to branch 'main'.
- Alternatively I can create a branch and open a PR if you prefer.

Copyright & license
-------------------
Follow the repository's existing license. Do not add third-party content that conflicts with the repo license.
