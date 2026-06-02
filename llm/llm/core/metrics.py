from __future__ import annotations

from collections import Counter, defaultdict
from threading import Lock


_lock = Lock()
_counters: Counter[str] = Counter()
_fallback_reasons: Counter[str] = Counter()
_stage_seconds: dict[str, list[float]] = defaultdict(list)


def record_analysis_completed(suspicious_count: int, duration_seconds: float) -> None:
    with _lock:
        _counters["analysis_completed_total"] += 1
        _counters["suspicious_elements_total"] += int(suspicious_count)
        _stage_seconds["analysis_total"].append(float(duration_seconds))


def record_fallback(reason: str | None) -> None:
    with _lock:
        _counters["fallback_total"] += 1
        _fallback_reasons[_public_fallback_reason(reason)] += 1


def record_error(kind: str) -> None:
    with _lock:
        _counters[f"{kind}_errors_total"] += 1


def record_stage_timing(stage: str, seconds: float) -> None:
    with _lock:
        _stage_seconds[stage].append(float(seconds))


def metrics_snapshot() -> dict:
    with _lock:
        return {
            "counters": dict(_counters),
            "fallback_reasons": dict(_fallback_reasons),
            "stage_seconds": {
                stage: _summary(values)
                for stage, values in _stage_seconds.items()
            },
        }


def _summary(values: list[float]) -> dict[str, float | int]:
    if not values:
        return {"count": 0, "sum": 0.0, "avg": 0.0, "max": 0.0}
    total = sum(values)
    return {
        "count": len(values),
        "sum": round(total, 3),
        "avg": round(total / len(values), 3),
        "max": round(max(values), 3),
    }


def _public_fallback_reason(reason: str | None) -> str:
    if not reason:
        return "unknown"
    lowered = reason.lower()
    if "production budget" in lowered or "time budget" in lowered:
        return "LLM recommendation time budget exceeded"
    if "timed out" in lowered or "timeout" in lowered or "read timed out" in lowered:
        return "LLM recommendation timed out"
    if "connection" in lowered or "unavailable" in lowered or "not ready" in lowered:
        return "LLM service unavailable"
    if "missing item" in lowered:
        return "LLM batch response missing item"
    if "unterminated string" in lowered or "json" in lowered:
        return "LLM recommendation returned invalid JSON"
    if "self-check" in lowered or "self check" in lowered:
        return "LLM recommendation failed self-check"
    if "disabled" in lowered:
        return "LLM recommendations disabled"
    return reason[:160]
