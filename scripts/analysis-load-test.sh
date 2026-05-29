#!/usr/bin/env bash
set -euo pipefail

API_BASE="${API_BASE:-http://127.0.0.1:8000}"
TOKEN="${TOKEN:-}"
FILE_PATH="${FILE_PATH:-doc/test_script_safe.txt}"
COUNT="${COUNT:-5}"

if [[ -z "$TOKEN" ]]; then
  echo "TOKEN is required" >&2
  exit 1
fi

if [[ ! -f "$FILE_PATH" ]]; then
  echo "File not found: $FILE_PATH" >&2
  exit 1
fi

for index in $(seq 1 "$COUNT"); do
  curl -fsS \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@${FILE_PATH}" \
    "${API_BASE}/api/analyses" &
done

wait
echo "Submitted ${COUNT} analysis jobs"
