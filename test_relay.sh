#!/bin/bash
set -e

BASE_URL="${PUBLIC_BASE_URL:-http://localhost:8799}"
if [ -n "$TAILSCALE_HOST" ]; then
  BASE_URL="https://${TAILSCALE_HOST}/voice-relay"
fi

echo "=== 1. Checking Relay Service Health on $BASE_URL ==="
curl -sf "${BASE_URL}/health" | jq .

echo -e "\n=== 2. Simulating Capture (Scratch fallback) ==="
RES=$(curl -sf -X POST "${BASE_URL}/capture" \
  -H "Content-Type: application/json" \
  -d '{"text": "Research latest WebGPU specifications for mobile browsers"}')
echo "$RES" | jq .

ID=$(echo "$RES" | jq -r .id)

echo -e "\n=== 3. Simulating Discard ==="
curl -sf "${BASE_URL}/discard?id=$ID"
echo -e "\nDone. Test passed!"
