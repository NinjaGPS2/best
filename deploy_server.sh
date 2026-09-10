#!/bin/bash
# ================================================================
# EDC Electricity Billing & Management System - Server Deploy Script
# Repository: https://github.com/NinjaGPS2/best
# ================================================================

set -e

echo ">>> [1/4] Pulling latest code from GitHub..."
git pull origin main

echo ">>> [2/4] Activating virtual environment (if exists)..."
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
fi

echo ">>> [3/4] Installing/Updating dependencies..."
pip install -r requirements.txt

echo ">>> [4/4] Restarting Application Service..."
# If using systemd service named 'edc':
if systemctl is-active --quiet edc 2>/dev/null; then
    sudo systemctl restart edc
    echo ">>> Systemd service 'edc' restarted successfully!"
else
    echo ">>> Note: Please restart your gunicorn / web server process manually."
fi

echo ">>> Deployment completed successfully!"
