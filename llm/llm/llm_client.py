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

BATCH_RECOMMENDATION_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "summary": {"type": "string"},
                    "explanation": {"type": "string"},
                    "risk_factors": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "rewrite_suggestions": RECOMMENDATION_SCHEMA["properties"]["rewrite_suggestions"],
                    "self_check_passed": {"type": "boolean"},
                    "uncertainty_note": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                    },
                },
                "required": [
                    "id",
                    "summary",
                    "explanation",
                    "risk_factors",
                    "rewrite_suggestions",
                    "self_check_passed",
                    "uncertainty_note",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["items"],
    "additionalProperties": False,
}

FAST_BATCH_RECOMMENDATION_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "summary": {"type": "string"},
                    "explanation": {"type": "string"},
                    "risk_factors": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "self_check_passed": {"type": "boolean"},
                    "uncertainty_note": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                    },
                },
                "required": [
                    "id",
                    "summary",
                    "explanation",
                    "risk_factors",
                    "self_check_passed",
                    "uncertainty_note",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["items"],
    "additionalProperties": False,
}

GROUPED_RECOMMENDATION_SCHEMA = {
    "type": "object",
    "properties": {
        "groups": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "group_id": {"type": "string"},
                    "applies_to_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "summary": {"type": "string"},
                    "explanation": {"type": "string"},
                    "risk_factors": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "rewrite_suggestions": RECOMMENDATION_SCHEMA["properties"]["rewrite_suggestions"],
                    "self_check_passed": {"type": "boolean"},
                    "uncertainty_note": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                    },
                },
                "required": [
                    "group_id",
                    "applies_to_ids",
                    "summary",
                    "explanation",
                    "risk_factors",
                    "rewrite_suggestions",
                    "self_check_passed",
                    "uncertainty_note",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["groups"],
    "additionalProperties": False,
}

GROUPED_SUMMARY_RECOMMENDATION_SCHEMA = {
    "type": "object",
    "properties": {
        "groups": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "group_id": {"type": "string"},
                    "applies_to_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "summary": {"type": "string"},
                    "explanation": {"type": "string"},
                    "risk_factors": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "self_check_passed": {"type": "boolean"},
                    "uncertainty_note": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                    },
                },
                "required": [
                    "group_id",
                    "applies_to_ids",
                    "summary",
                    "explanation",
                    "risk_factors",
                    "self_check_passed",
                    "uncertainty_note",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["groups"],
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


def call_ollama_json(
    messages: list[dict[str, str]],
    schema: dict = RECOMMENDATION_SCHEMA,
    num_predict: int | None = None,
    timeout_seconds: float | None = None,
) -> LlmResult:
    if not llm_enabled():
        return LlmResult(payload=None, fallback_used=True, error="LLM recommendations disabled")

    base_url = os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).rstrip("/")
    model = os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
    timeout = timeout_seconds if timeout_seconds is not None else float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "45"))
    retry_count = max(0, int(os.getenv("OLLAMA_RETRY_COUNT", "0")))
    resolved_num_predict = num_predict if num_predict is not None else int(os.getenv("OLLAMA_NUM_PREDICT", "700"))
    format_mode = os.getenv("OLLAMA_JSON_FORMAT_MODE", "json").lower()
    url = f"{base_url}/api/chat"
    options = ollama_options(resolved_num_predict)
    body = {
        "model": model,
        "messages": messages,
        "stream": False,
        "format": schema if format_mode == "schema" else "json",
        "think": os.getenv("OLLAMA_THINK", "false").lower() in {"1", "true", "yes"},
        "keep_alive": os.getenv("OLLAMA_KEEP_ALIVE", "5m"),
        "options": options,
    }

    last_error = None
    for _ in range(retry_count + 1):
        try:
            response = requests.post(url, json=body, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            content = data.get("message", {}).get("content", "")
            payload = json.loads(content)
            normalize_payload_for_schema(payload, schema)
            validate_payload_for_schema(payload, schema)
            return LlmResult(payload=payload, fallback_used=False)
        except Exception as exc:
            last_error = str(exc)

    record_error("ollama")
    return LlmResult(payload=None, fallback_used=True, error=last_error)


def ollama_options(num_predict: int) -> dict[str, Any]:
    options: dict[str, Any] = {
        "temperature": float(os.getenv("OLLAMA_TEMPERATURE", "0.2")),
        "num_predict": num_predict,
    }

    optional_ints = {
        "OLLAMA_NUM_CTX": "num_ctx",
        "OLLAMA_NUM_THREAD": "num_thread",
        "OLLAMA_NUM_BATCH": "num_batch",
        "OLLAMA_NUM_GPU": "num_gpu",
        "OLLAMA_SEED": "seed",
        "OLLAMA_TOP_K": "top_k",
    }
    for env_name, option_name in optional_ints.items():
        value = _env_int(env_name)
        if value is not None:
            options[option_name] = value

    top_p = _env_float("OLLAMA_TOP_P")
    if top_p is not None:
        options["top_p"] = top_p

    raw_options = os.getenv("OLLAMA_OPTIONS_JSON", "").strip()
    if raw_options:
        try:
            parsed = json.loads(raw_options)
            if isinstance(parsed, dict):
                options.update(parsed)
        except json.JSONDecodeError:
            record_error("ollama_options")

    return options


def _env_int(name: str) -> int | None:
    value = os.getenv(name, "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        record_error("ollama_options")
        return None


def _env_float(name: str) -> float | None:
    value = os.getenv(name, "").strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        record_error("ollama_options")
        return None


def normalize_payload_for_schema(payload: Any, schema: dict) -> None:
    if schema is not FAST_BATCH_RECOMMENDATION_SCHEMA or not isinstance(payload, dict):
        return

    items = payload.get("items")
    if not isinstance(items, list):
        return

    for item in items:
        if not isinstance(item, dict):
            continue
        risk_factors = item.get("risk_factors")
        if isinstance(risk_factors, str):
            parts = [
                part.strip(" -.;")
                for part in risk_factors.replace("\n", ",").split(",")
                if part.strip(" -.;")
            ]
            item["risk_factors"] = parts or [risk_factors.strip()]


def validate_payload_for_schema(payload: Any, schema: dict) -> None:
    if schema is BATCH_RECOMMENDATION_SCHEMA:
        validate_batch_recommendation_payload(payload)
        return
    if schema is FAST_BATCH_RECOMMENDATION_SCHEMA:
        validate_fast_batch_recommendation_payload(payload)
        return
    if schema is GROUPED_RECOMMENDATION_SCHEMA:
        validate_grouped_recommendation_payload(payload)
        return
    if schema is GROUPED_SUMMARY_RECOMMENDATION_SCHEMA:
        validate_grouped_summary_recommendation_payload(payload)
        return

    validate_recommendation_payload(payload)


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


def validate_batch_recommendation_payload(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise ValueError("LLM batch payload is not an object")

    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("LLM batch items must be an array")

    seen_ids = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("LLM batch item is not an object")
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id.strip():
            raise ValueError("LLM batch item id is missing")
        if item_id in seen_ids:
            raise ValueError("LLM batch item ids must be unique")
        seen_ids.add(item_id)
        validate_recommendation_payload({key: value for key, value in item.items() if key != "id"})


def validate_fast_batch_recommendation_payload(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise ValueError("LLM fast batch payload is not an object")

    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("LLM fast batch items must be an array")

    seen_ids = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("LLM fast batch item is not an object")
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id.strip():
            raise ValueError("LLM fast batch item id is missing")
        if item_id in seen_ids:
            raise ValueError("LLM fast batch item ids must be unique")
        seen_ids.add(item_id)
        for key in ("summary", "explanation"):
            if not isinstance(item.get(key), str) or not item.get(key).strip():
                raise ValueError(f"LLM fast batch {key} is missing")
        risk_factors = item.get("risk_factors")
        if not isinstance(risk_factors, list) or not all(isinstance(value, str) for value in risk_factors):
            raise ValueError("LLM fast batch risk_factors must be a string array")
        if not isinstance(item.get("self_check_passed"), bool):
            raise ValueError("LLM fast batch self_check_passed must be boolean")
        uncertainty_note = item.get("uncertainty_note")
        if uncertainty_note is not None and not isinstance(uncertainty_note, str):
            raise ValueError("LLM fast batch uncertainty_note must be a string or null")


def validate_grouped_recommendation_payload(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise ValueError("LLM grouped payload is not an object")

    groups = payload.get("groups")
    if not isinstance(groups, list):
        raise ValueError("LLM grouped groups must be an array")

    seen_group_ids = set()
    for group in groups:
        if not isinstance(group, dict):
            raise ValueError("LLM grouped item is not an object")
        group_id = group.get("group_id")
        if not isinstance(group_id, str) or not group_id.strip():
            raise ValueError("LLM grouped group_id is missing")
        if group_id in seen_group_ids:
            raise ValueError("LLM grouped group ids must be unique")
        seen_group_ids.add(group_id)
        applies_to_ids = group.get("applies_to_ids")
        if not isinstance(applies_to_ids, list) or not all(isinstance(item, str) and item.strip() for item in applies_to_ids):
            raise ValueError("LLM grouped applies_to_ids must be a string array")
        validate_recommendation_payload({
            key: value
            for key, value in group.items()
            if key not in {"group_id", "applies_to_ids"}
        })


def validate_grouped_summary_recommendation_payload(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise ValueError("LLM grouped summary payload is not an object")

    groups = payload.get("groups")
    if not isinstance(groups, list):
        raise ValueError("LLM grouped summary groups must be an array")

    seen_group_ids = set()
    for group in groups:
        if not isinstance(group, dict):
            raise ValueError("LLM grouped summary item is not an object")
        group_id = group.get("group_id")
        if not isinstance(group_id, str) or not group_id.strip():
            raise ValueError("LLM grouped summary group_id is missing")
        if group_id in seen_group_ids:
            raise ValueError("LLM grouped summary group ids must be unique")
        seen_group_ids.add(group_id)
        applies_to_ids = group.get("applies_to_ids")
        if not isinstance(applies_to_ids, list) or not all(isinstance(item, str) and item.strip() for item in applies_to_ids):
            raise ValueError("LLM grouped summary applies_to_ids must be a string array")
        for key in ("summary", "explanation"):
            if not isinstance(group.get(key), str) or not group.get(key).strip():
                raise ValueError(f"LLM grouped summary {key} is missing")
        risk_factors = group.get("risk_factors")
        if not isinstance(risk_factors, list) or not all(isinstance(value, str) for value in risk_factors):
            raise ValueError("LLM grouped summary risk_factors must be a string array")
        if not isinstance(group.get("self_check_passed"), bool):
            raise ValueError("LLM grouped summary self_check_passed must be boolean")
        uncertainty_note = group.get("uncertainty_note")
        if uncertainty_note is not None and not isinstance(uncertainty_note, str):
            raise ValueError("LLM grouped summary uncertainty_note must be a string or null")


def _is_rewrite_suggestion(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    required = ["goal", "before", "after", "rationale", "expected_effect"]
    return all(isinstance(item.get(key), str) and item.get(key).strip() for key in required)
