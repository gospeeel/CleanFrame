from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from llm.recommendations.service import build_recommendation_context, generate_recommendation_packages_batch


REQUIRED_SUGGESTION_FIELDS = {"goal", "before", "after", "rationale", "expected_effect"}
DEFAULT_REPORT_PATH = Path(__file__).resolve().parents[3] / "reports" / "recommendations_quality.json"


def read_jsonl(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row.get("input"), dict):
                raise ValueError(f"{path}:{line_no}: recommendation row must contain input object")
            rows.append(row)
            if limit and len(rows) >= limit:
                break
    if not rows:
        raise ValueError(f"Dataset is empty: {path}")
    return rows


def row_to_context(row: dict[str, Any]) -> dict[str, Any]:
    payload = row["input"]
    return build_recommendation_context(
        item_id=row["id"],
        text=payload["text"],
        category=payload["category"],
        category_label=payload.get("category_label"),
        secondary_categories=payload.get("secondary_categories", []),
        level=int(payload["level"]),
        level_label=payload.get("level_label"),
        rating=payload["rating"],
        target_rating=payload["target_rating"],
        evidence=payload.get("evidence", []),
        confidence=payload.get("confidence", {"category": 1.0, "level": 1.0, "rating": 1.0}),
        needs_review=True,
        element_type=payload.get("element_type", "action"),
        character=payload.get("character", ""),
    )


def evaluate_dataset(
    dataset_path: Path,
    output_path: Path,
    limit: int | None = None,
    batch_size: int = 16,
    use_expected: bool = False,
) -> dict[str, Any]:
    started = time.monotonic()
    rows = read_jsonl(dataset_path, limit=limit)
    contexts = [row_to_context(row) for row in rows]
    packages: dict[str, dict[str, Any]] = {}

    if use_expected:
        packages = {
            row["id"]: {
                "fallback_used": False,
                "fallback_reason": None,
                "llm_recommendation": row.get("expected", {}),
                "recommendation": row.get("expected", {}),
            }
            for row in rows
        }
    else:
        for start in range(0, len(contexts), batch_size):
            packages.update(generate_recommendation_packages_batch(contexts[start:start + batch_size]))

    item_reports = []
    for row, context in zip(rows, contexts):
        package = packages.get(context["id"], {})
        payload = package.get("llm_recommendation") or package.get("recommendation") or {}
        item_reports.append(evaluate_item(row=row, context=context, package=package, payload=payload))

    summary = summarize(item_reports)
    report = {
        "dataset": str(dataset_path),
        "mode": "expected_payload" if use_expected else "live_recommendation_service",
        "created_at_unix": int(time.time()),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "sample_count": len(item_reports),
        "summary": summary,
        "items": item_reports,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def evaluate_item(row: dict[str, Any], context: dict[str, Any], package: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    suggestions = payload.get("rewrite_suggestions", [])
    if not isinstance(suggestions, list):
        suggestions = []

    suggestion_checks = [evaluate_suggestion(item, context) for item in suggestions if isinstance(item, dict)]
    exact_three = len(suggestions) == 3
    schema_valid = bool(payload.get("summary")) and bool(payload.get("explanation")) and exact_three
    category_ok = recommendation_mentions_category(payload, context["category"], context["category_label"])
    rating_guard_ok = not payload_changes_rating(payload)
    before_after_quality = quality_ratio(suggestion_checks, "quality_ok")
    grounded_ratio = quality_ratio(suggestion_checks, "before_grounded")

    checks = {
        "schema_valid": schema_valid,
        "category_ok": category_ok,
        "three_suggestions": exact_three,
        "rating_guard_ok": rating_guard_ok,
        "before_after_quality_ok": before_after_quality >= 0.8,
        "before_grounded_ok": grounded_ratio >= 0.67,
        "self_check_passed": bool(payload.get("self_check_passed")),
        "fallback_used": bool(package.get("fallback_used")),
    }
    checks["passed"] = (
        checks["schema_valid"]
        and checks["category_ok"]
        and checks["three_suggestions"]
        and checks["rating_guard_ok"]
        and checks["before_after_quality_ok"]
        and not checks["fallback_used"]
    )

    return {
        "id": row["id"],
        "source_document": row.get("source_document"),
        "category": context["category"],
        "rating": context["rating"],
        "target_rating": context["target_rating"],
        "checks": checks,
        "metrics": {
            "suggestion_count": len(suggestions),
            "before_after_quality": round(before_after_quality, 4),
            "before_grounded_ratio": round(grounded_ratio, 4),
        },
        "fallback_reason": package.get("fallback_reason"),
        "suggestion_checks": suggestion_checks,
    }


def evaluate_suggestion(item: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    before = normalize_text(item.get("before", ""))
    after = normalize_text(item.get("after", ""))
    source_text = normalize_text(context.get("text", ""))
    evidence_text = " ".join(normalize_text(evidence.get("text", "")) for evidence in context.get("evidence", []))
    search_space = f"{source_text} {evidence_text}"

    required_fields_ok = REQUIRED_SUGGESTION_FIELDS.issubset({key for key, value in item.items() if str(value).strip()})
    before_grounded = bool(before) and (before in search_space or any_overlap(before, search_space))
    changed = bool(before and after and before != after)
    after_not_empty = len(after) >= 8
    after_not_longer_by_much = len(after) <= max(240, int(len(before) * 2.5)) if before else len(after) <= 240

    return {
        "goal": item.get("goal"),
        "required_fields_ok": required_fields_ok,
        "before_grounded": before_grounded,
        "changed": changed,
        "after_not_empty": after_not_empty,
        "after_not_longer_by_much": after_not_longer_by_much,
        "quality_ok": required_fields_ok and changed and after_not_empty and after_not_longer_by_much,
    }


def summarize(items: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(items)
    if not total:
        return {}

    check_keys = [
        "schema_valid",
        "category_ok",
        "three_suggestions",
        "rating_guard_ok",
        "before_after_quality_ok",
        "before_grounded_ok",
        "self_check_passed",
        "fallback_used",
        "passed",
    ]
    rates = {
        key: round(sum(1 for item in items if item["checks"][key]) / total, 4)
        for key in check_keys
    }
    return {
        "pass_rate": rates["passed"],
        "fallback_rate": rates["fallback_used"],
        "rates": rates,
        "failed_count": sum(1 for item in items if not item["checks"]["passed"]),
        "failed_ids": [item["id"] for item in items if not item["checks"]["passed"]][:50],
    }


def recommendation_mentions_category(payload: dict[str, Any], category: str, category_label: str) -> bool:
    text = " ".join([
        str(payload.get("summary", "")),
        str(payload.get("explanation", "")),
        " ".join(str(item) for item in payload.get("risk_factors", []) if isinstance(item, str)),
        " ".join(
            " ".join(str(value) for value in item.values())
            for item in payload.get("rewrite_suggestions", [])
            if isinstance(item, dict)
        ),
    ]).lower()
    semantic_tokens = {
        "violence": ["насил", "драк", "удар", "оруж", "violence", "violent"],
        "profanity": ["лексик", "бран", "ругател", "мат", "profan", "swear", "language"],
        "substance": ["алког", "табак", "наркот", "substance", "drug", "alcohol"],
        "sexual": ["интим", "сексу", "эрот", "sexual", "intim"],
        "fear": ["пуга", "страх", "тревог", "fear", "scary"],
    }.get(category, [])
    label_tokens = [token.lower() for token in str(category_label).split() if len(token) > 3]
    return any(token in text for token in semantic_tokens + label_tokens)


def payload_changes_rating(payload: dict[str, Any]) -> bool:
    text = json.dumps(payload, ensure_ascii=False).lower()
    forbidden = [
        "изменить рейтинг",
        "сменить рейтинг",
        "присвоить рейтинг",
        "change rating",
        "set rating",
        "rating should be",
    ]
    return any(phrase in text for phrase in forbidden)


def quality_ratio(items: list[dict[str, Any]], key: str) -> float:
    if not items:
        return 0.0
    return sum(1 for item in items if item.get(key)) / len(items)


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").lower().split())


def any_overlap(needle: str, haystack: str) -> bool:
    terms = [term for term in needle.split() if len(term) > 4]
    if not terms:
        return False
    hits = sum(1 for term in terms if term in haystack)
    return hits / len(terms) >= 0.5


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate policy recommendation quality and write a JSON report.")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--use-expected", action="store_true", help="Evaluate expected payloads instead of generated policy output.")
    args = parser.parse_args()

    report = evaluate_dataset(
        dataset_path=args.dataset,
        output_path=args.output,
        limit=args.limit,
        batch_size=args.batch_size,
        use_expected=args.use_expected,
    )
    print(json.dumps({
        "sample_count": report["sample_count"],
        "pass_rate": report["summary"]["pass_rate"],
        "fallback_rate": report["summary"]["fallback_rate"],
        "output": str(args.output),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
