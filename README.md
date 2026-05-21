# 2026 Running Goal Tracker

Automated dashboard that pulls your runs from Strava and tracks progress toward your 1000-mile goal.

Accessible at https://stravainsights.tillworks.com (password protected). Also runs locally in WSL Ubuntu at `~/prj/stravainsights/`.

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

### Option A — live site (recommended)

Visit https://stravainsights.tillworks.com. The **Refresh** button pulls the latest activities from Strava in a few seconds. Works from any device including mobile.

### Option B — local server

```bash
cd ~/prj/stravainsights
python3 serve.py
```

Starts a server at http://localhost:8732 and auto-opens it in your browser. The Refresh button works here too. Stop with Ctrl-C.

### Option C — open the file directly

```bash
explorer.exe dashboard.html   # opens via your default Windows browser
# or
wslview dashboard.html        # if wslu is installed
```

The dashboard displays normally, but the Refresh button will pop up a dialog explaining how to refresh from the terminal instead.

## Automate the refresh with cron

### On the Lightsail server (recommended)

SSH in and install a cron job to refresh automatically:

```bash
( crontab -l 2>/dev/null; echo "0 6 * * * cd /home/ubuntu/stravainsights && /usr/bin/python3 refresh.py >> refresh.log 2>&1" ) | crontab -
```

This runs at 6 AM daily. The server is always on, so the job always fires.

### In WSL (local only)

```bash
( crontab -l 2>/dev/null; echo "0 6 * * * cd $HOME/prj/stravainsights && /usr/bin/python3 refresh.py >> refresh.log 2>&1" ) | crontab -
```

Note: WSL2 only runs cron while the WSL instance is active. If your terminal is closed at 6 AM the job is skipped — the next manual `refresh.py` or Refresh button press will catch up.

## Files

- `config.json` — Strava credentials (keep private; never commit to git)
- `runs.json` — cached run data (rebuilt on every refresh)
- `dashboard.html` — the dashboard (rebuilt on every refresh)
- `setup.py` — one-time OAuth setup
- `refresh.py` — fetch + rebuild script
- `serve.py` — web server for the dashboard (powers the Refresh button)
- `template.html` — dashboard layout (edit to tweak the look)
- `refresh.log` — output from cron runs
- `deploy/` — Lightsail server setup (systemd service, Caddyfile, bootstrap script)

## Troubleshooting

- **`config.json not found`** — run `python3 setup.py` first.
- **`Token refresh failed`** — your refresh token was revoked. Re-run `setup.py` to re-authorize.
- **`Activities fetch failed: 401`** — same as above; access was revoked. Re-run `setup.py`.
- **`Activities fetch failed: 429`** — you've hit Strava's rate limit (200 requests / 15 min). Wait 15 minutes and re-run `refresh.py`.
