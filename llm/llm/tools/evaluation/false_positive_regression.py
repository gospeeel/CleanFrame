from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from llm.detection.rule_detector import is_suspicious_scene
from llm.rating import TERM_LEVELS
from llm.taxonomy import normalize_category


DEFAULT_DATASET = Path(__file__).resolve().parents[3] / "datasets" / "golden" / "false_positive_regression.jsonl"
DEFAULT_REPORT_PATH = Path(__file__).resolve().parents[3] / "reports" / "false_positive_regression.json"


def evaluate_false_positive_regression(
    dataset_path: Path = DEFAULT_DATASET,
    output_path: Path = DEFAULT_REPORT_PATH,
) -> dict[str, Any]:
    started = time.monotonic()
    rows = load_jsonl(dataset_path)
    items = []
    failures = []
    false_positive_count = 0
    false_negative_count = 0
    high_risk_false_positive_count = 0
    false_positive_by_category: dict[str, int] = {}

    for row in rows:
        result = is_suspicious_scene(row["text"])
        active = active_categories(result)
        expected_risk = bool(row.get("risk_detected", False))
        expected_category = normalize_category(row.get("category", "safe"))
        is_risk = bool(result.get("is_suspicious"))
        errors = []

        if is_risk != expected_risk:
            errors.append(f"risk_detected expected={expected_risk}, actual={is_risk}")

        if expected_risk and expected_category != "safe" and expected_category not in active:
            errors.append(f"missing expected category: {expected_category}")

        if not expected_risk and active:
            false_positive_count += 1
            for category in active:
                false_positive_by_category[category] = false_positive_by_category.get(category, 0) + 1
            if max_evidence_level(active, result.get("matched_terms", {})) >= 3:
                high_risk_false_positive_count += 1

        if expected_risk and not is_risk:
            false_negative_count += 1

        item = {
            "id": row.get("id"),
            "text": row.get("text"),
            "expected_risk_detected": expected_risk,
            "actual_risk_detected": is_risk,
            "expected_category": expected_category,
            "active_categories": sorted(active),
            "matched_terms": result.get("matched_terms", {}),
            "errors": errors,
        }
        items.append(item)
        if errors:
            failures.append(item)

    total = len(rows)
    passed = total - len(failures)
    safe_total = sum(1 for row in rows if not row.get("risk_detected", False))
    report = {
        "dataset": str(dataset_path),
        "created_at_unix": int(time.time()),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "summary": {
            "total": total,
            "passed": passed,
            "failed": len(failures),
            "pass_rate": round(passed / total, 4) if total else 0.0,
            "safe_total": safe_total,
            "false_positive_count": false_positive_count,
            "false_positive_rate": round(false_positive_count / safe_total, 4) if safe_total else 0.0,
            "false_negative_count": false_negative_count,
            "high_risk_false_positive_count": high_risk_false_positive_count,
            "false_positive_by_category": dict(sorted(false_positive_by_category.items())),
        },
        "items": items,
        "failures": failures,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            row["_line"] = line_number
            rows.append(row)
    if not rows:
        raise ValueError(f"Dataset is empty: {path}")
    return rows


def active_categories(result: dict[str, Any]) -> set[str]:
    return {
        normalize_category(category)
        for category, is_active in result.get("normalized_flags", {}).items()
        if is_active
    }


def max_evidence_level(active: set[str], matched_terms: dict[str, list[str]]) -> int:
    max_level = 0
    for category in active:
        terms = {
            str(term).lower()
            for key, values in (matched_terms or {}).items()
            if normalize_category(key) == category
            for term in values
        }
        for level, level_terms in TERM_LEVELS.get(category, {}).items():
            if terms & level_terms:
                max_level = max(max_level, level)
    return max_level


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate manual false-positive regression dataset.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--min-pass-rate", type=float, default=0.9)
    parser.add_argument("--max-high-risk-false-positives", type=int, default=0)
    args = parser.parse_args()

    report = evaluate_false_positive_regression(args.dataset, args.output)
    summary = report["summary"]
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if (
        summary["pass_rate"] < args.min_pass_rate
        or summary["high_risk_false_positive_count"] > args.max_high_risk_false_positives
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
