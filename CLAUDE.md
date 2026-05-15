# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A personal running goal tracker that pulls data from the Strava API and renders a self-contained HTML dashboard showing progress toward a 1000-mile annual goal (2026). Designed to run locally in WSL2 Ubuntu.

## Commands

```bash
python3 setup.py          # One-time OAuth setup (interactive, opens browser)
python3 refresh.py        # Fetch runs from Strava, rebuild dashboard.html
python3 serve.py          # Local server at http://localhost:8732 (enables in-browser refresh button)
```

No build system, no tests, no linting configured. Only dependency beyond stdlib is `requests`.

## Architecture

The data pipeline is: **Strava API → runs.json → dashboard.html**

- `refresh.py` — Core logic. Authenticates via OAuth refresh token, fetches activities, filters to runs (`Run`, `TrailRun`, `VirtualRun`), computes metrics (cumulative miles, pace delta, frequency rates, 30-day rolling window), and renders the dashboard by injecting a JSON payload into `template.html` at the `/*__DATA__*/null` placeholder.
- `template.html` — Dashboard layout with Chart.js. The `DATA` variable is replaced at build time. All rendering is client-side JS reading from that embedded JSON blob.
- `serve.py` — Thin HTTP server (port 8732, localhost-only). Serves `dashboard.html` at `/` and exposes `POST /refresh` which shells out to `refresh.py`.
- `setup.py` — One-time interactive OAuth flow. Spins up a temporary HTTP server on port 8731 to catch the redirect callback.
- `config.json` — Strava credentials (client_id, client_secret, refresh_token, access_token). **Never commit this file.**
- `runs.json` — Cached run data, regenerated on every refresh.
- `dashboard.html` — Generated output; do not edit directly (edit `template.html` instead).

## Key Constants

In `refresh.py`: `GOAL_MILES = 1000`, `GOAL_YEAR = 2026`, `METERS_PER_MILE = 1609.344`.

## Sensitive Files

`config.json` contains API secrets and must never be committed or shared.
