#!/usr/bin/env python3
"""One-time Strava OAuth setup.

Walks you through:
  1. Entering your Strava API app's Client ID and Client Secret.
  2. Authorizing the app in your browser.
  3. Exchanging the resulting code for a long-lived refresh token.
  4. Saving everything to config.json.

Re-run this only if you need to reconnect (e.g. you revoked access).
"""

import http.server
import json
import os
import socketserver
import sys
import threading
import urllib.parse
import webbrowser
from pathlib import Path

import requests

CONFIG_PATH = Path(__file__).parent / "config.json"
PORT = 8731  # arbitrary unused port
REDIRECT_URI = f"http://localhost:{PORT}/callback"
SCOPE = "activity:read_all"


class _CodeCatcher(http.server.BaseHTTPRequestHandler):
    """Tiny one-shot server that catches the OAuth redirect."""

    code: str | None = None
    error: str | None = None

    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if "code" in params:
            _CodeCatcher.code = params["code"][0]
            body = b"<h1>Authorized!</h1><p>You can close this tab and return to the terminal.</p>"
        else:
            _CodeCatcher.error = params.get("error", ["unknown"])[0]
            body = f"<h1>Authorization failed</h1><p>{_CodeCatcher.error}</p>".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass  # silence default logging


def _wait_for_code(timeout_s: int = 300) -> str:
    """Run a one-shot local HTTP server and block until Strava redirects to it."""
    with socketserver.TCPServer(("localhost", PORT), _CodeCatcher) as httpd:
        httpd.timeout = 1
        deadline = timeout_s
        while deadline > 0 and _CodeCatcher.code is None and _CodeCatcher.error is None:
            httpd.handle_request()
            deadline -= 1
    if _CodeCatcher.error:
        raise RuntimeError(f"Strava authorization failed: {_CodeCatcher.error}")
    if _CodeCatcher.code is None:
        raise RuntimeError("Timed out waiting for Strava authorization.")
    return _CodeCatcher.code


def main() -> None:
    print("=" * 60)
    print("Strava API setup")
    print("=" * 60)
    print()
    print("Get your Client ID and Client Secret from:")
    print("  https://www.strava.com/settings/api")
    print()
    print("Make sure the app's Authorization Callback Domain is set to 'localhost'.")
    print()

    client_id = input("Client ID: ").strip()
    client_secret = input("Client Secret: ").strip()
    if not client_id or not client_secret:
        print("Both values are required. Aborting.")
        sys.exit(1)

    auth_url = (
        "https://www.strava.com/oauth/authorize"
        f"?client_id={client_id}"
        "&response_type=code"
        f"&redirect_uri={urllib.parse.quote(REDIRECT_URI, safe='')}"
        "&approval_prompt=force"
        f"&scope={SCOPE}"
    )

    print()
    print("Opening Strava authorization page in your browser...")
    print("If it doesn't open automatically, paste this URL:")
    print()
    print(f"  {auth_url}")
    print()
    print("After clicking Authorize, you'll be redirected to a local page that")
    print("confirms success. Keep this script running until then.")
    print()

    server_thread = threading.Thread(target=lambda: None)  # placeholder
    del server_thread

    # Open browser asynchronously, then block on the server.
    webbrowser.open(auth_url)

    try:
        code = _wait_for_code()
    except RuntimeError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    print("Got authorization code. Exchanging it for a refresh token...")

    token_resp = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    if token_resp.status_code != 200:
        print(f"Token exchange failed: {token_resp.status_code} {token_resp.text}")
        sys.exit(1)

    token_data = token_resp.json()
    athlete = token_data.get("athlete", {})
    config = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": token_data["refresh_token"],
        "access_token": token_data["access_token"],
        "expires_at": token_data["expires_at"],
        "athlete_id": athlete.get("id"),
        "athlete_name": f"{athlete.get('firstname', '')} {athlete.get('lastname', '')}".strip(),
    }
    CONFIG_PATH.write_text(json.dumps(config, indent=2))
    # Lock down permissions on Unix-like systems.
    try:
        os.chmod(CONFIG_PATH, 0o600)
    except OSError:
        pass

    print()
    print(f"Saved credentials to {CONFIG_PATH.name}.")
    if config["athlete_name"]:
        print(f"Authorized as: {config['athlete_name']}")
    print()
    print("Next step: run `python3 refresh.py` to fetch your runs and build the dashboard.")


if __name__ == "__main__":
    main()
