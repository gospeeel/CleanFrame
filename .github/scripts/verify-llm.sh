#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR/llm"

PYTHON_BIN="${PYTHON_BIN:-./.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="${PYTHON_BIN_FALLBACK:-python3}"
fi

"$PYTHON_BIN" -m compileall llm tests
"$PYTHON_BIN" -m unittest tests.test_taxonomy

GATE_ARGS=()

if [[ "${RUN_EVIDENCE_QUALITY:-true}" == "true" ]]; then
  GATE_ARGS+=(--run-evidence-quality)
fi

if [[ "${RUN_FULL_PIPELINE_GOLDEN:-false}" == "true" ]]; then
  GATE_ARGS+=(--run-pipeline-golden)
fi

if [[ -n "${RUBERT_EVAL_DATASET:-}" ]]; then
  GATE_ARGS+=(--rubert-dataset "$RUBERT_EVAL_DATASET")
  GATE_ARGS+=(--rubert-model-dir "${RUBERT_MODEL_DIR:-trained_model}")
  if [[ -n "${RUBERT_CANDIDATE_MODEL_DIR:-}" ]]; then
    GATE_ARGS+=(--rubert-candidate-model-dir "$RUBERT_CANDIDATE_MODEL_DIR")
  fi
fi

if [[ -n "${RECOMMENDATIONS_EVAL_DATASET:-}" ]]; then
  GATE_ARGS+=(--recommendations-dataset "$RECOMMENDATIONS_EVAL_DATASET")
  if [[ "${RECOMMENDATIONS_EVAL_USE_EXPECTED:-false}" == "true" ]]; then
    GATE_ARGS+=(--recommendations-use-expected)
  fi
  if [[ -n "${RECOMMENDATIONS_EVAL_LIMIT:-}" ]]; then
    GATE_ARGS+=(--recommendations-limit "$RECOMMENDATIONS_EVAL_LIMIT")
  fi
fi

"$PYTHON_BIN" -m llm.tools.evaluation.quality_gate "${GATE_ARGS[@]}"
