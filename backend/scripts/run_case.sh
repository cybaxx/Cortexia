#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 /path/to/payload.json [api_base_url]" >&2
  exit 1
fi

PAYLOAD_FILE="$1"
API_BASE_URL="${2:-http://127.0.0.1:8000}"

if [[ ! -f "$PAYLOAD_FILE" ]]; then
  echo "Payload file not found: $PAYLOAD_FILE" >&2
  exit 1
fi

curl -sS -X POST \
  "${API_BASE_URL%/}/api/simulate" \
  -H "content-type: application/json" \
  --data "@${PAYLOAD_FILE}"

