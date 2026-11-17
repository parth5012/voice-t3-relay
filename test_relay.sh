#!/bin/bash
set -e

BASE_URL="${PUBLIC_BASE_URL:-http://localhost:8799}"
if [ -n "$TAILSCALE_HOST" ]; then
  BASE_URL="https://${TAILSCALE_HOST}/voice-relay"
fi

echo "=== 1. Checking Relay Service Health on $BASE_URL ==="
HEALTH=$(curl -sf "${BASE_URL}/health")
echo "$HEALTH" | jq .

echo -e "\n=== 2. Simulating Text Capture ==="
RES=$(curl -sf -X POST "${BASE_URL}/capture" \
  -H "Content-Type: application/json" \
  -d '{"text": "In Vela, add latency ratchet metrics to websocket"}')
echo "$RES" | jq .

ID=$(echo "$RES" | jq -r .id)

echo -e "\n=== 3. Simulating Discard ==="
curl -sf "${BASE_URL}/discard?id=$ID"

echo -e "\n=== 4. Testing Audio Capture Endpoint (/capture-audio) ==="
# Generate dummy 1s mp3
ffmpeg -y -f lavfi -i "sine=frequency=1000:duration=1" -c:a libmp3lame /tmp/test_beep.mp3 >/dev/null 2>&1

AUDIO_RES=$(curl -s -X POST "${BASE_URL}/capture-audio" \
  -F "file=@/tmp/test_beep.mp3")
echo "$AUDIO_RES" | jq . || echo "$AUDIO_RES"
rm -f /tmp/test_beep.mp3

echo -e "\nDone. Test completed successfully!"
