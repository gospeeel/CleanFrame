#!/usr/bin/env bash
set -euo pipefail

COMPOSE="${COMPOSE:-docker compose}"
API_BASE="${API_BASE:-http://127.0.0.1:8000}"

$COMPOSE up -d redis postgres llm backend backend-worker
$COMPOSE restart backend-worker

curl -fsS "${API_BASE}/api/ready" >/dev/null
$COMPOSE ps backend-worker

echo "Worker restart smoke check completed"
