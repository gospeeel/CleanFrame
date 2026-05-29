#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

require_pattern() {
  local pattern="$1"
  local file="$2"
  if ! grep -Eq "$pattern" "$file"; then
    echo "Missing pattern '$pattern' in $file" >&2
    exit 1
  fi
}

require_pattern "DEAD_LETTER" backend/prisma/schema.prisma
require_pattern "markDeadLetter" backend/src/analyses/analysis-processor.service.ts
require_pattern "dist/src/worker\\.js" docker-compose.yaml
require_pattern "backend-worker:" docker-compose.yaml
require_pattern "ANALYSIS_WORKER_ENABLED: \"false\"" docker-compose.yaml
require_pattern "ANALYSIS_WORKER_ENABLED: \"true\"" docker-compose.yaml
require_pattern "start:worker" backend/package.json
require_pattern "DEAD_LETTER" frontend/app/entities/analysis/model/types.ts

echo "V2 architecture static checks passed"
