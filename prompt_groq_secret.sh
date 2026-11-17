#!/bin/bash
set -e

CLIENT_REQ_ID="groq-secret-$(date +%s)"
AGY_PID=$(pgrep -f "299eb30febbe89443a569f90e5482e306a4e9d1fef813ca2cf14bce9cb7c9032" | head -n1)
if [ -z "$AGY_PID" ]; then
  AGY_PID=$(pgrep -f "agy acp" | tail -n1)
fi

BRIDGE_PID=$(pgrep -P "$AGY_PID" -f "acp-mcp-bridge" | head -n1)
if [ -z "$BRIDGE_PID" ]; then
  BRIDGE_PID=$(pgrep -f "acp-mcp-bridge" | tail -n1)
fi

if [ -z "$BRIDGE_PID" ]; then
  echo "Error: Could not locate active t3 acp-mcp-bridge process." >&2
  exit 1
fi

AUTH=$(strings /proc/${BRIDGE_PID}/environ | grep '^T3_ACP_MCP_AUTHORIZATION=' | cut -d= -f2-)
T3_BIN=$(ls -1d /home/parth/.t3/runtime/versions/*/t3 2>/dev/null | sort -V | tail -n1)

export T3_ACP_MCP_ENDPOINT="http://127.0.0.1:3773/mcp"
export T3_ACP_MCP_AUTHORIZATION="$AUTH"

echo "Requesting Groq API key via T3 MCP request_secret card (ID: $CLIENT_REQ_ID)..."

RES=$("$T3_BIN" acp-mcp-call request_secret "{
  \"clientRequestId\": \"$CLIENT_REQ_ID\",
  \"label\": \"Groq API Key\",
  \"reason\": \"Enter your Groq API key (starts with gsk_) for Voice-to-T3 Relay transcription\",
  \"placeholder\": \"gsk_...\",
  \"url\": \"https://console.groq.com/keys\",
  \"delivery\": \"file\",
  \"timeoutMs\": 600000
}")

echo "request_secret returned response: $RES"
SECRET_FILE=$(echo "$RES" | jq -r '.file // .structuredContent.file // empty')

if [ -n "$SECRET_FILE" ] && [ -f "$SECRET_FILE" ]; then
  KEY_VAL=$(cat "$SECRET_FILE" | tr -d '\r\n ')
  rm -f "$SECRET_FILE"
  if [ -n "$KEY_VAL" ]; then
    sed -i "s|^GROQ_API_KEY=.*|GROQ_API_KEY=${KEY_VAL}|" /home/parth/projects/voice-t3-relay/.env
    systemctl --user restart voice-t3-relay.service
    echo "SUCCESS: Saved GROQ_API_KEY to .env and restarted voice-t3-relay.service"
    curl -sf http://localhost:8799/health | jq .
  else
    echo "Error: Received empty key value." >&2
    exit 1
  fi
else
  echo "Error: No valid secret file returned: $RES" >&2
  exit 1
fi
