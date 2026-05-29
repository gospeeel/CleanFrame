import json
import os
from dataclasses import dataclass
from typing import Any

import requests

from llm.core.metrics import record_error


DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "qwen2.5:3b-instruct"


RECOMMENDATION_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "explanation": {"type": "string"},
        "risk_factors": {
            "type": "array",
            "items": {"type": "string"},
        },
        "rewrite_suggestions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "goal": {"type": "string"},
                    "before": {"type": "string"},
                    "after": {"type": "string"},
                    "rationale": {"type": "string"},
                    "expected_effect": {"type": "string"},
                },
                "required": ["goal", "before", "after", "rationale", "expected_effect"],
                "additionalProperties": False,
            },
        },
        "self_check_passed": {"type": "boolean"},
        "uncertainty_note": {
            "anyOf": [{"type": "string"}, {"type": "null"}],
        },
    },
    "required": [
        "summary",
        "explanation",
        "risk_factors",
        "rewrite_suggestions",
        "self_check_passed",
        "uncertainty_note",
    ],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class LlmResult:
    payload: dict[str, Any] | None
    fallback_used: bool
    error: str | None = None


def llm_enabled() -> bool:
    return os.getenv("LLM_RECOMMENDATIONS_ENABLED", "true").lower() in {"1", "true", "yes"}


def ollama_status() -> dict[str, Any]:
    enabled = llm_enabled()
    base_url = os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).rstrip("/")
    model = os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)

    if not enabled:
        return {
            "enabled": False,
            "ready": False,
            "base_url": base_url,
            "model": model,
            "status": "disabled",
        }

    try:
        response = requests.get(f"{base_url}/api/tags", timeout=3)
        response.raise_for_status()
        models = response.json().get("models", [])
        names = {item.get("name") for item in models if isinstance(item, dict)}
        return {
            "enabled": True,
            "ready": model in names,
            "base_url": base_url,
            "model": model,
            "available_models": sorted(name for name in names if name),
            "status": "ready" if model in names else "model_not_pulled",
        }
    except Exception as exc:
        return {
            "enabled": True,
            "ready": False,
            "base_url": base_url,
            "model": model,
            "status": "unavailable",
            "error": str(exc),
        }


def call_ollama_json(messages: list[dict[str, str]], schema: dict = RECOMMENDATION_SCHEMA) -> LlmResult:
    if not llm_enabled():
        return LlmResult(payload=None, fallback_used=True, error="LLM recommendations disabled")

    base_url = os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).rstrip("/")
    model = os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
    timeout = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "45"))
    retry_count = max(0, int(os.getenv("OLLAMA_RETRY_COUNT", "0")))
    num_predict = int(os.getenv("OLLAMA_NUM_PREDICT", "700"))
    url = f"{base_url}/api/chat"
    body = {
        "model": model,
        "messages": messages,
        "stream": False,
        "format": schema,
        "keep_alive": os.getenv("OLLAMA_KEEP_ALIVE", "5m"),
        "options": {
            "temperature": 0.2,
            "num_predict": num_predict,
        },
    }

    last_error = None
    for _ in range(retry_count + 1):
        try:
            response = requests.post(url, json=body, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            content = data.get("message", {}).get("content", "")
            payload = json.loads(content)
            validate_recommendation_payload(payload)
            return LlmResult(payload=payload, fallback_used=False)
        except Exception as exc:
            last_error = str(exc)

    record_error("ollama")
    return LlmResult(payload=None, fallback_used=True, error=last_error)


def validate_recommendation_payload(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise ValueError("LLM payload is not an object")

    explanation = payload.get("explanation")
    summary = payload.get("summary")
    risk_factors = payload.get("risk_factors")
    rewrite_suggestions = payload.get("rewrite_suggestions")
    self_check_passed = payload.get("self_check_passed")
    uncertainty_note = payload.get("uncertainty_note")

    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("LLM summary is missing")
    if not isinstance(explanation, str) or not explanation.strip():
        raise ValueError("LLM explanation is missing")
    if not isinstance(risk_factors, list) or not all(isinstance(item, str) for item in risk_factors):
        raise ValueError("LLM risk_factors must be a string array")
    if not isinstance(rewrite_suggestions, list) or not all(_is_rewrite_suggestion(item) for item in rewrite_suggestions):
        raise ValueError("LLM rewrite_suggestions must be a rewrite suggestion array")
    if not isinstance(self_check_passed, bool):
        raise ValueError("LLM self_check_passed must be boolean")
    if uncertainty_note is not None and not isinstance(uncertainty_note, str):
        raise ValueError("LLM uncertainty_note must be a string or null")


def _is_rewrite_suggestion(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    required = ["goal", "before", "after", "rationale", "expected_effect"]
    return all(isinstance(item.get(key), str) and item.get(key).strip() for key in required)
