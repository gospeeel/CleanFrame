#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/llm"

PYTHON_BIN="${PYTHON_BIN:-./.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="${PYTHON_BIN_FALLBACK:-python3}"
fi

"$PYTHON_BIN" -m compileall llm tests
"$PYTHON_BIN" -m unittest tests.test_taxonomy
"$PYTHON_BIN" -m llm.evaluate_golden

if [[ "${RUN_FULL_PIPELINE_GOLDEN:-false}" == "true" ]]; then
  "$PYTHON_BIN" -m llm.evaluate_golden --mode pipeline
fi
