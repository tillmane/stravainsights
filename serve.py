#!/usr/bin/env python3
"""Local HTTP server that hosts the dashboard and provides a manual refresh hook.

Run with:
    python3 serve.py

Then open http://localhost:8732 in your browser. The dashboard's "Refresh" button
will POST to /refresh, which runs refresh.py and returns the result as JSON.

Stop the server with Ctrl-C. Designed for local use only — it binds to 127.0.0.1
so nothing on your network can reach it.
"""

from __future__ import annotations

import http.server
import json
import os
import socketserver
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).parent
DASHBOARD = ROOT / "dashboard.html"
TEMPLATE = ROOT / "template.html"
REFRESH_SCRIPT = ROOT / "refresh.py"

HOST = "127.0.0.1"
PORT = 8732


class Handler(http.server.SimpleHTTPRequestHandler):
    # Serve files from the project folder.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):  # noqa: N802
        # Root → dashboard.html. Lets the user just hit http://localhost:8732.
        if self.path in ("/", "/index.html"):
            if DASHBOARD.exists():
                self.path = "/dashboard.html"
            else:
                # First-time visit before refresh.py has ever run.
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    b"<h1>Dashboard not built yet</h1>"
                    b"<p>Run <code>python3 refresh.py</code> once, then reload.</p>"
                )
                return
        return super().do_GET()

    def do_POST(self):  # noqa: N802
        if self.path != "/refresh":
            self.send_error(404, "Unknown endpoint")
            return

        start = time.time()
        try:
            result = subprocess.run(
                [sys.executable, str(REFRESH_SCRIPT)],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=120,
            )
            elapsed = round(time.time() - start, 1)
            payload = {
                "ok": result.returncode == 0,
                "elapsed_s": elapsed,
                "stdout": result.stdout[-4000:],
                "stderr": result.stderr[-4000:],
                "returncode": result.returncode,
            }
            status = 200 if result.returncode == 0 else 500
        except subprocess.TimeoutExpired:
            payload = {"ok": False, "error": "refresh.py timed out after 120s"}
            status = 504
        except Exception as exc:  # noqa: BLE001
            payload = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            status = 500

        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        # Quieter logs: timestamp + method/path/status.
        print(f"[{time.strftime('%H:%M:%S')}] {self.address_string()} {fmt % args}")


def main() -> None:
    if not REFRESH_SCRIPT.exists():
        sys.exit(f"Missing refresh.py at {REFRESH_SCRIPT}")
    if not TEMPLATE.exists():
        sys.exit(f"Missing template.html at {TEMPLATE}")

    url = f"http://{HOST}:{PORT}/"
    print(f"Serving 2026 Running Goal dashboard at {url}")
    print(f"  (project folder: {ROOT})")
    print("  press Ctrl-C to stop")
    print()

    # Open the browser shortly after the server starts.
    # Redirect stderr to suppress xdg-open noise in WSL2.
    def _open_browser():
        devnull = os.open(os.devnull, os.O_WRONLY)
        old_stderr = os.dup(2)
        os.dup2(devnull, 2)
        try:
            webbrowser.open(url)
        finally:
            os.dup2(old_stderr, 2)
            os.close(devnull)
            os.close(old_stderr)

    threading.Timer(0.4, _open_browser).start()

    with socketserver.ThreadingTCPServer((HOST, PORT), Handler) as httpd:
        httpd.allow_reuse_address = True
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down.")


if __name__ == "__main__":
    main()
