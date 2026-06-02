from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from llm.evaluate_golden import DEFAULT_DATASET, evaluate


DEFAULT_REPORT_PATH = Path(__file__).resolve().parents[3] / "reports" / "evidence_quality.json"


def evaluate_evidence_quality(
    dataset_path: Path = DEFAULT_DATASET,
    output_path: Path = DEFAULT_REPORT_PATH,
    mode: str = "rules",
) -> dict[str, Any]:
    started = time.monotonic()
    golden_report = evaluate(dataset_path, mode=mode)
    items = [evaluate_item(item) for item in golden_report["failures"]]

    passed_rows = golden_report["passed"]
    failed_rows = golden_report["failed"]
    total_rows = golden_report["total"]
    false_positive_rows = [
        item for item in golden_report["failures"]
        if not item["expected"]["risk_detected"] and item["actual"]["risk_detected"]
    ]
    false_negative_rows = [
        item for item in golden_report["failures"]
        if item["expected"]["risk_detected"] and not item["actual"]["risk_detected"]
    ]
    term_recall = expected_term_recall(golden_report)

    report = {
        "dataset": str(dataset_path),
        "mode": mode,
        "created_at_unix": int(time.time()),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "summary": {
            "total": total_rows,
            "passed": passed_rows,
            "failed": failed_rows,
            "evidence_accuracy": golden_report["evidence_accuracy"],
            "evidence_term_recall": term_recall,
            "false_positive_evidence_rate": round(len(false_positive_rows) / total_rows, 4) if total_rows else 0.0,
            "false_positive_count": len(false_positive_rows),
            "false_negative_count": len(false_negative_rows),
        },
        "failure_analysis": items,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def evaluate_item(item: dict[str, Any]) -> dict[str, Any]:
    expected_terms = set(item["expected"].get("evidence", []))
    actual_terms = actual_evidence_terms(item["actual"].get("matched_terms", {}))
    return {
        "id": item["id"],
        "checks": {
            "risk_ok": item["risk_ok"],
            "category_ok": item["category_ok"],
            "rating_ok": item["rating_ok"],
            "evidence_ok": item["evidence_ok"],
        },
        "expected": item["expected"],
        "actual": item["actual"],
        "missing_evidence_terms": sorted(expected_terms - actual_terms),
        "unexpected_evidence_terms": sorted(actual_terms - expected_terms)[:20],
        "failure_kind": failure_kind(item),
    }


def failure_kind(item: dict[str, Any]) -> str:
    if not item["expected"]["risk_detected"] and item["actual"]["risk_detected"]:
        return "false_positive"
    if item["expected"]["risk_detected"] and not item["actual"]["risk_detected"]:
        return "false_negative"
    if not item["evidence_ok"]:
        return "evidence_mismatch"
    if not item["rating_ok"]:
        return "rating_mismatch"
    if not item["category_ok"]:
        return "category_mismatch"
    return "other"


def expected_term_recall(report: dict[str, Any]) -> float:
    total_expected = 0
    total_hit = 0
    for item in report.get("items", []):
        expected = set(item["expected"].get("evidence", []))
        actual = actual_evidence_terms(item["actual"].get("matched_terms", {}))
        total_expected += len(expected)
        total_hit += len(expected & actual)
    if total_expected == 0:
        return 1.0
    return round(total_hit / total_expected, 4)


def actual_evidence_terms(matched_terms: dict[str, list[str]]) -> set[str]:
    return {
        str(term)
        for terms in matched_terms.values()
        for term in terms
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate evidence quality on golden regression rows.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--mode", choices=["rules", "pipeline"], default="rules")
    args = parser.parse_args()
    print(json.dumps(
        evaluate_evidence_quality(args.dataset, args.output, mode=args.mode),
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
