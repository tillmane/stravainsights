#!/usr/bin/env bash
set -euo pipefail

# Bootstrap script for a fresh Ubuntu instance (e.g. AWS Lightsail).
# Run as: sudo bash deploy/setup.sh

APP_DIR="/home/ubuntu/stravainsights"
SERVICE_NAME="stravainsights"

echo "=== Strava Insights — server setup ==="
echo

# --- 1. System packages ---
echo "[1/7] Installing system packages..."
apt-get update -qq
apt-get install -y -qq python3 python3-pip git > /dev/null

echo "[2/7] Installing Python dependencies..."
pip3 install --quiet requests

# --- 2. Install Caddy ---
echo "[3/7] Installing Caddy..."
apt-get install -y -qq debian-keyring debian-archive-keyring apt-transport-https curl > /dev/null
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg 2>/dev/null
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list > /dev/null
apt-get update -qq
apt-get install -y -qq caddy > /dev/null

# --- 3. Check config.json ---
echo
if [ ! -f "$APP_DIR/config.json" ]; then
    echo "WARNING: $APP_DIR/config.json not found."
    echo "Copy your Strava credentials to the server before starting the service:"
    echo "  scp config.json ubuntu@<your-ip>:$APP_DIR/config.json"
    echo
fi

# --- 4. Basic auth credentials ---
echo "[4/7] Setting up basic auth..."
read -rp "  Username: " AUTH_USER
read -rsp "  Password: " AUTH_PASS
echo

AUTH_HASH=$(caddy hash-password --plaintext "$AUTH_PASS")

# --- 5. Write Caddyfile ---
echo "[5/7] Writing Caddyfile..."
cat > /etc/caddy/Caddyfile <<EOF
:80 {
    basicauth * {
        $AUTH_USER $AUTH_HASH
    }
    reverse_proxy 127.0.0.1:8732
}
EOF

# --- 6. Install and start app service ---
echo "[6/7] Installing systemd service..."
cp "$APP_DIR/deploy/stravainsights.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

# --- 7. Restart Caddy ---
echo "[7/7] Starting Caddy..."
systemctl restart caddy

# --- Initial refresh ---
echo
if [ -f "$APP_DIR/config.json" ]; then
    echo "Running initial refresh..."
    sudo -u ubuntu python3 "$APP_DIR/refresh.py"
fi

echo
echo "=== Done ==="
echo "Dashboard is live at http://$(curl -s ifconfig.me):80"
echo "Login with the credentials you just set."
