from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from llm.detection.rule_detector import is_suspicious_scene
from llm.rating import calculate_rating
from llm.taxonomy import primary_category_from_evidence


DEFAULT_DATASET = Path(__file__).resolve().parents[1] / "datasets" / "golden" / "regression.jsonl"


def evaluate(path: Path = DEFAULT_DATASET, mode: str = "rules") -> dict:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    results = []

    for row in rows:
        if mode == "pipeline":
            actual = _evaluate_pipeline_row(row)
            risk_detected = actual["risk_detected"]
            primary = actual["primary_category"]
            secondary = actual["secondary_categories"]
            rating = actual["rating"]
            matched_terms = actual["matched_terms"]
        else:
            natasha = is_suspicious_scene(row["text"])
            risk_detected = bool(natasha.get("is_suspicious"))
            if risk_detected:
                primary, secondary = primary_category_from_evidence(row.get("expected_primary_category", "safe"), natasha)
                level = row.get("expected_level", 1)
                rating = calculate_rating(primary, level)
            else:
                primary, secondary, level, rating = "safe", [], 0, "0+"
            matched_terms = natasha.get("matched_terms", {})

        result = {
            "id": row["id"],
            "risk_ok": risk_detected == row["expected_risk_detected"],
            "category_ok": primary == row["expected_primary_category"],
            "secondary_ok": _same_set(secondary, row.get("expected_secondary_categories", [])),
            "rating_ok": rating == row["expected_rating"],
            "evidence_ok": _evidence_ok(matched_terms, row.get("expected_evidence", [])),
            "expected": {
                "risk_detected": row["expected_risk_detected"],
                "primary_category": row["expected_primary_category"],
                "secondary_categories": row.get("expected_secondary_categories", []),
                "rating": row["expected_rating"],
                "evidence": row.get("expected_evidence", []),
            },
            "actual": {
                "risk_detected": risk_detected,
                "primary_category": primary,
                "secondary_categories": secondary,
                "rating": rating,
                "matched_terms": matched_terms,
            },
        }
        results.append(result)

    total = len(results)
    failed = [
        item for item in results
        if not (
            item["risk_ok"]
            and item["category_ok"]
            and item["secondary_ok"]
            and item["rating_ok"]
            and item["evidence_ok"]
        )
    ]
    return {
        "dataset": str(path),
        "mode": mode,
        "total": total,
        "passed": total - len(failed),
        "failed": len(failed),
        "category_accuracy": _accuracy(results, "category_ok"),
        "secondary_accuracy": _accuracy(results, "secondary_ok"),
        "rating_accuracy": _accuracy(results, "rating_ok"),
        "evidence_accuracy": _accuracy(results, "evidence_ok"),
        "risk_detection_accuracy": _accuracy(results, "risk_ok"),
        "items": results,
        "failures": failed,
    }


def _evaluate_pipeline_row(row: dict) -> dict:
    from llm.pipeline.full_pipeline import process_script

    previous_llm_enabled = os.environ.get("LLM_RECOMMENDATIONS_ENABLED")
    os.environ["LLM_RECOMMENDATIONS_ENABLED"] = "false"

    try:
        with tempfile.TemporaryDirectory(prefix="ml-wink-golden-") as tmpdir:
            tmp_path = Path(tmpdir) / f"{row['id']}.txt"
            tmp_path.write_text(row["text"], encoding="utf-8")
            result = process_script(
                input_path=str(tmp_path),
                output_all=str(Path(tmpdir) / "all.json"),
                output_max=str(Path(tmpdir) / "max.json"),
                analysis_id=f"golden-{row['id']}",
                request_id=f"golden-{row['id']}",
            )
    finally:
        if previous_llm_enabled is None:
            os.environ.pop("LLM_RECOMMENDATIONS_ENABLED", None)
        else:
            os.environ["LLM_RECOMMENDATIONS_ENABLED"] = previous_llm_enabled

    scenes = result.get("все_подозрительные_сцены") or result.get("обработанные_сцены") or []
    metadata = result.get("metadata", {}) if isinstance(result, dict) else {}
    if not scenes:
        return {
            "risk_detected": False,
            "primary_category": "safe",
            "secondary_categories": [],
            "rating": "0+",
            "matched_terms": {},
            "level": 0,
            "confidence": {},
            "evidence_count": 0,
            "aggregation_reason": metadata.get("rating_aggregation", {}).get("reason"),
        }

    first = scenes[0]
    return {
        "risk_detected": bool(first.get("risk_detected")),
        "primary_category": first.get("primary_category") or first.get("категория"),
        "secondary_categories": first.get("secondary_categories", []),
        "rating": first.get("rating") or first.get("рейтинг"),
        "matched_terms": first.get("evidence_meta", {}).get("matched_terms", {}),
        "level": first.get("level") if first.get("level") is not None else first.get("СѓСЂРѕРІРµРЅСЊ"),
        "confidence": first.get("confidence", {}),
        "evidence_count": len(first.get("evidence") or []),
        "aggregation_reason": metadata.get("rating_aggregation", {}).get("reason"),
    }


def _accuracy(results: list[dict], key: str) -> float:
    if not results:
        return 0.0
    return round(sum(1 for item in results if item[key]) / len(results), 4)


def _same_set(actual: list[str], expected: list[str]) -> bool:
    return set(actual) == set(expected)


def _evidence_ok(matched_terms: dict[str, list[str]], expected: list[str]) -> bool:
    actual_terms = {
        term
        for terms in matched_terms.values()
        for term in terms
    }
    return set(expected).issubset(actual_terms)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate golden regression dataset.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--mode", choices=["rules", "pipeline"], default="rules")
    args = parser.parse_args()
    print(json.dumps(evaluate(args.dataset, mode=args.mode), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
