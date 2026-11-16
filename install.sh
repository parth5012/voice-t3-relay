#!/usr/bin/env bash
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="voice-t3-relay.service"
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"
DATA_DIR="${HOME}/.local/share/voice-t3-relay"

echo "=== Installing Voice to T3 Relay ==="

mkdir -p "$DATA_DIR"
mkdir -p "$SYSTEMD_USER_DIR"

# Copy or update systemd unit
cp "${REPO_DIR}/${SERVICE_NAME}" "${SYSTEMD_USER_DIR}/${SERVICE_NAME}"
echo "✓ Installed systemd service to ${SYSTEMD_USER_DIR}/${SERVICE_NAME}"

# Ensure permissions
chmod +x "${REPO_DIR}/server.py"
chmod +x "${REPO_DIR}/test_relay.sh"

# Reload systemd and enable service
systemctl --user daemon-reload
systemctl --user enable --now "$SERVICE_NAME"
echo "✓ Enabled and started ${SERVICE_NAME}"

# Status check
sleep 1
if systemctl --user is-active --quiet "$SERVICE_NAME"; then
    echo "✓ Voice T3 Relay daemon is running successfully!"
else
    echo "⚠️ Service did not start cleanly. Check logs with: journalctl --user -u ${SERVICE_NAME} -n 30"
    exit 1
fi

echo ""
echo "=== Setup complete! ==="
echo "To expose over Tailscale:"
echo "  tailscale serve --set-path /voice-relay http://127.0.0.1:8799"
echo ""
echo "To test:"
echo "  ${REPO_DIR}/test_relay.sh"
