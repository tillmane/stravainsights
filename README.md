# 2026 Running Goal Tracker

Automated dashboard that pulls your runs from Strava and tracks progress toward your 1000-mile goal.

Designed to run in WSL Ubuntu at `~/prj/stravainsights/`.

## One-time setup

### 1. Make sure Python 3 and the required libraries are available:

```bash
python3 --version             # 3.10+ recommended
```

### 2. Create a Strava API application

1. Go to https://www.strava.com/settings/api
2. Fill in the form:
   - **Application Name:** `Running Goal Tracker` (anything works)
   - **Category:** `Data Importer`
   - **Club:** leave blank
   - **Website:** `http://localhost` (anything works)
   - **Authorization Callback Domain:** `localhost` (important — must be exactly `localhost`)
3. Upload any image as the app icon and click **Create**.
4. On the resulting page, note down two values:
   - **Client ID** (a number)
   - **Client Secret** (click "Show" to reveal it)

### 3. Run the setup script

```bash
python3 setup.py
```

It will:
- Ask for your Client ID and Client Secret
- Open a browser to Strava's authorization page (WSL2 forwards `localhost` to Windows, so the auto-capture works)
- Exchange the code for a long-lived refresh token
- Save everything to `config.json`

> **If the browser doesn't auto-open in WSL,** the script prints the authorize URL — paste it into your Windows browser. After clicking Authorize you'll be redirected to `http://localhost:8731/callback?code=…`; the local server still receives it because WSL2 binds `localhost` to the Windows host.

You only have to do this once. The refresh token lasts indefinitely.

### 4. Pull your data and build the dashboard

```bash
python3 refresh.py
```

This fetches every 2026 activity from Strava and regenerates `dashboard.html`.

## Daily use

You have two ways to view the dashboard:

### Option A — local server (recommended; refresh button works)

```bash
cd ~/prj/stravainsights
python3 serve.py
```

This starts a tiny local server at http://localhost:8732 and auto-opens it in your browser. The **Refresh** button in the dashboard's top-right pulls the latest activities from Strava and reloads — no terminal needed once it's running. Stop the server with Ctrl-C.

Bookmark http://localhost:8732 so it's one click away whenever the server is up.

### Option B — open the file directly

```bash
explorer.exe dashboard.html   # opens via your default Windows browser
# or
wslview dashboard.html        # if wslu is installed
```

The dashboard displays normally, but the Refresh button can't reach a server, so it will pop up a dialog explaining how to refresh from the terminal instead.

## Automate the refresh with cron

Install a daily cron job that runs the refresh at 6 AM every morning:

```bash
( crontab -l 2>/dev/null; echo "0 6 * * * cd $HOME/prj/stravainsights && /usr/bin/python3 refresh.py >> refresh.log 2>&1" ) | crontab -
```

Verify:

```bash
crontab -l
```

Notes:
- WSL2 only runs cron while the WSL instance is running. If your WSL session isn't active at 6 AM (e.g. you closed all terminals), the job is skipped — the next manual `refresh.py` will catch up.
- To keep WSL running in the background, add `wsl.exe -d Ubuntu --exec sleep infinity` to Windows Startup, or just open a terminal in the morning.
- All output goes to `refresh.log` in the project folder.

## Files

- `config.json` — Strava credentials (keep private; never commit to git)
- `runs.json` — cached run data (rebuilt on every refresh)
- `dashboard.html` — the dashboard (rebuilt on every refresh)
- `setup.py` — one-time OAuth setup
- `refresh.py` — fetch + rebuild script
- `serve.py` — local web server for the dashboard (powers the Refresh button)
- `template.html` — dashboard layout (edit to tweak the look)
- `refresh.log` — output from cron runs

## Troubleshooting

- **`config.json not found`** — run `python3 setup.py` first.
- **`Token refresh failed`** — your refresh token was revoked. Re-run `setup.py` to re-authorize.
- **`Activities fetch failed: 401`** — same as above; access was revoked. Re-run `setup.py`.
- **`Activities fetch failed: 429`** — you've hit Strava's rate limit (200 requests / 15 min). Wait 15 minutes and re-run `refresh.py`.
