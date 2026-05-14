#!/usr/bin/env python3
"""Pull 2026 runs from Strava and regenerate dashboard.html.

Reads credentials from config.json. Caches raw run data in runs.json. Renders
dashboard.html as a self-contained file (data + Chart.js embedded inline) so
you can open it in any browser without a server.

Run this whenever you want fresh data:
    python3 refresh.py
"""

from __future__ import annotations

import json
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).parent
CONFIG_PATH = ROOT / "config.json"
RUNS_PATH = ROOT / "runs.json"
TEMPLATE_PATH = ROOT / "template.html"
DASHBOARD_PATH = ROOT / "dashboard.html"

GOAL_MILES = 1000
GOAL_YEAR = 2026
METERS_PER_MILE = 1609.344

# Strava activity types that count as "running" toward the goal.
RUN_TYPES = {"Run", "TrailRun", "VirtualRun"}


# ---------- Strava API ----------


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        sys.exit("config.json not found. Run `python3 setup.py` first.")
    return json.loads(CONFIG_PATH.read_text())


def save_config(config: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(config, indent=2))


def ensure_access_token(config: dict) -> str:
    """Return a valid access token, refreshing if needed."""
    now = int(time.time())
    if config.get("access_token") and config.get("expires_at", 0) > now + 60:
        return config["access_token"]

    print("Refreshing Strava access token...")
    resp = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "grant_type": "refresh_token",
            "refresh_token": config["refresh_token"],
        },
        timeout=30,
    )
    if resp.status_code != 200:
        sys.exit(f"Token refresh failed: {resp.status_code} {resp.text}")
    data = resp.json()
    config["access_token"] = data["access_token"]
    config["refresh_token"] = data["refresh_token"]
    config["expires_at"] = data["expires_at"]
    save_config(config)
    return config["access_token"]


def fetch_activities(access_token: str, year: int) -> list[dict]:
    """Fetch every activity in the given calendar year."""
    after = int(datetime(year, 1, 1, tzinfo=timezone.utc).timestamp())
    before = int(datetime(year + 1, 1, 1, tzinfo=timezone.utc).timestamp())
    page = 1
    out: list[dict] = []
    while True:
        resp = requests.get(
            "https://www.strava.com/api/v3/athlete/activities",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"after": after, "before": before, "per_page": 200, "page": page},
            timeout=30,
        )
        if resp.status_code != 200:
            sys.exit(f"Activities fetch failed: {resp.status_code} {resp.text}")
        batch = resp.json()
        if not batch:
            break
        out.extend(batch)
        if len(batch) < 200:
            break
        page += 1
    return out


# ---------- Metric computation ----------


def m_to_mi(meters: float) -> float:
    return meters / METERS_PER_MILE


def build_run_records(activities: list[dict]) -> list[dict]:
    """Filter to runs and normalize the fields we care about."""
    runs = []
    for a in activities:
        if a.get("type") not in RUN_TYPES and a.get("sport_type") not in RUN_TYPES:
            continue
        start_local = a.get("start_date_local") or a.get("start_date")
        if not start_local:
            continue
        # start_date_local has no tz suffix; treat as naive ISO.
        dt = datetime.fromisoformat(start_local.replace("Z", ""))
        runs.append({
            "id": a["id"],
            "name": a.get("name", "Run"),
            "date": dt.date().isoformat(),
            "datetime": dt.isoformat(),
            "distance_mi": round(m_to_mi(a.get("distance", 0)), 3),
            "moving_time_s": a.get("moving_time", 0),
            "elapsed_time_s": a.get("elapsed_time", 0),
            "type": a.get("type"),
        })
    runs.sort(key=lambda r: r["date"])
    return runs


def compute_metrics(runs: list[dict], today: date) -> dict:
    year_start = date(GOAL_YEAR, 1, 1)
    year_end = date(GOAL_YEAR, 12, 31)
    days_in_year = (year_end - year_start).days + 1  # 365
    days_into_year = (today - year_start).days + 1   # inclusive (1 on Jan 1)
    days_into_year = max(1, min(days_into_year, days_in_year))
    days_remaining = max(0, (year_end - today).days)  # days strictly after today

    total_miles = round(sum(r["distance_mi"] for r in runs), 2)
    miles_remaining = max(0.0, GOAL_MILES - total_miles)
    progress_pct = round(total_miles / GOAL_MILES * 100, 1)

    ideal_miles_today = round(GOAL_MILES * days_into_year / days_in_year, 2)
    delta_vs_pace = round(total_miles - ideal_miles_today, 2)

    run_dates = {r["date"] for r in runs}
    days_run = len(run_dates)
    frequency_rate = round(days_run / days_into_year * 100, 1)  # %
    avg_distance = round(total_miles / len(runs), 2) if runs else 0.0

    # Last-30-days window (inclusive of today, so a 30-day rolling slice).
    window_start = today - timedelta(days=29)
    # Clip the window to the start of the year so the rate isn't misleading in January.
    effective_window_start = max(window_start, year_start)
    window_days = (today - effective_window_start).days + 1
    runs_30 = [r for r in runs if date.fromisoformat(r["date"]) >= effective_window_start]
    days_run_30 = len({r["date"] for r in runs_30})
    total_miles_30 = round(sum(r["distance_mi"] for r in runs_30), 2)
    frequency_rate_30 = round(days_run_30 / window_days * 100, 1) if window_days > 0 else 0.0
    avg_distance_30 = round(total_miles_30 / len(runs_30), 2) if runs_30 else 0.0

    # Forward-looking projection: at the last-30-day frequency rate, what avg
    # mi/run is needed to hit the goal?
    if days_remaining > 0:
        daily_pace_needed = round(miles_remaining / days_remaining, 2)
        expected_future_runs_30 = (frequency_rate_30 / 100) * days_remaining
        required_avg_distance_30 = (
            round(miles_remaining / expected_future_runs_30, 2)
            if expected_future_runs_30 > 0 else None
        )
    else:
        daily_pace_needed = 0.0
        required_avg_distance_30 = None

    # Build cumulative-miles series, one point per day, for charting.
    by_day: dict[str, float] = {}
    for r in runs:
        by_day[r["date"]] = by_day.get(r["date"], 0.0) + r["distance_mi"]

    cumulative_series = []
    ideal_series = []
    cum = 0.0
    d = year_start
    while d <= today:
        cum += by_day.get(d.isoformat(), 0.0)
        day_idx = (d - year_start).days + 1
        cumulative_series.append({"date": d.isoformat(), "miles": round(cum, 2)})
        ideal_series.append({"date": d.isoformat(), "miles": round(GOAL_MILES * day_idx / days_in_year, 2)})
        d += timedelta(days=1)
    # Extend the ideal line through year-end so the user sees the target trajectory.
    d = today + timedelta(days=1)
    while d <= year_end:
        day_idx = (d - year_start).days + 1
        ideal_series.append({"date": d.isoformat(), "miles": round(GOAL_MILES * day_idx / days_in_year, 2)})
        d += timedelta(days=1)

    # Weekly mileage bar series (ISO weeks).
    weekly: dict[str, float] = {}
    for r in runs:
        rd = date.fromisoformat(r["date"])
        # Use the Monday of the ISO week as the bucket key.
        monday = rd - timedelta(days=rd.weekday())
        weekly[monday.isoformat()] = weekly.get(monday.isoformat(), 0.0) + r["distance_mi"]
    weekly_series = [
        {"week_start": k, "miles": round(v, 2)}
        for k, v in sorted(weekly.items())
    ]

    return {
        "goal_miles": GOAL_MILES,
        "goal_year": GOAL_YEAR,
        "today": today.isoformat(),
        "days_into_year": days_into_year,
        "days_remaining": days_remaining,
        "total_miles": total_miles,
        "miles_remaining": round(miles_remaining, 2),
        "progress_pct": progress_pct,
        "ideal_miles_today": ideal_miles_today,
        "delta_vs_pace": delta_vs_pace,
        "total_runs": len(runs),
        "days_run": days_run,
        "frequency_rate": frequency_rate,
        "avg_distance": avg_distance,
        "window_days": window_days,
        "days_run_30": days_run_30,
        "runs_30": len(runs_30),
        "frequency_rate_30": frequency_rate_30,
        "avg_distance_30": avg_distance_30,
        "daily_pace_needed": daily_pace_needed,
        "required_avg_distance_30": required_avg_distance_30,
        "cumulative_series": cumulative_series,
        "ideal_series": ideal_series,
        "weekly_series": weekly_series,
        "recent_runs": list(reversed(runs))[:10],
        "last_refreshed": datetime.now().isoformat(timespec="seconds"),
    }


# ---------- Rendering ----------


def render_dashboard(metrics: dict) -> None:
    if not TEMPLATE_PATH.exists():
        sys.exit(f"Missing template: {TEMPLATE_PATH.name}")
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    payload = json.dumps(metrics)
    html = template.replace("/*__DATA__*/null", payload)
    DASHBOARD_PATH.write_text(html, encoding="utf-8")


# ---------- Entry point ----------


def main() -> None:
    config = load_config()
    access_token = ensure_access_token(config)

    print(f"Fetching {GOAL_YEAR} activities from Strava...")
    activities = fetch_activities(access_token, GOAL_YEAR)
    print(f"  fetched {len(activities)} total activities")

    runs = build_run_records(activities)
    print(f"  {len(runs)} count as running")

    RUNS_PATH.write_text(json.dumps(runs, indent=2))

    today = date.today()
    metrics = compute_metrics(runs, today)
    render_dashboard(metrics)

    print()
    print(f"Total: {metrics['total_miles']} / {GOAL_MILES} mi  ({metrics['progress_pct']}%)")
    delta = metrics["delta_vs_pace"]
    status = f"{abs(delta):.1f} mi {'ahead of' if delta >= 0 else 'behind'} pace"
    print(f"Pace: {status}")
    print(f"Frequency rate (all-time): {metrics['frequency_rate']}%  ({metrics['days_run']} days run / {metrics['days_into_year']})")
    print(f"Frequency rate (last 30d): {metrics['frequency_rate_30']}%  ({metrics['days_run_30']} days run / {metrics['window_days']})")
    print(f"Avg distance/run (all-time): {metrics['avg_distance']} mi")
    print(f"Avg distance/run (last 30d): {metrics['avg_distance_30']} mi")
    if metrics["required_avg_distance_30"] is not None:
        print(
            f"To finish at 30-day frequency: need {metrics['required_avg_distance_30']} mi/run "
            f"(currently averaging {metrics['avg_distance_30']} in the last 30 days)"
        )
    print()
    print(f"Dashboard written to: {DASHBOARD_PATH}")


if __name__ == "__main__":
    main()
