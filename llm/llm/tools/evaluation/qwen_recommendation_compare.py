from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


def load_report(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        report = json.load(f)
    if not isinstance(report.get("summary"), dict):
        raise ValueError(f"Recommendation quality report must contain summary object: {path}")
    return report


def compare_reports(
    base_report: dict[str, Any],
    candidate_report: dict[str, Any],
    min_pass_rate_delta: float = 0.01,
    max_fallback_rate_delta: float = 0.0,
) -> dict[str, Any]:
    base_summary = base_report["summary"]
    candidate_summary = candidate_report["summary"]
    pass_rate_delta = round(candidate_summary["pass_rate"] - base_summary["pass_rate"], 4)
    fallback_rate_delta = round(candidate_summary["fallback_rate"] - base_summary["fallback_rate"], 4)
    checks = [
        {
            "name": "pass_rate_improved",
            "passed": pass_rate_delta >= min_pass_rate_delta,
            "details": {
                "base": base_summary["pass_rate"],
                "candidate": candidate_summary["pass_rate"],
                "delta": pass_rate_delta,
                "threshold": min_pass_rate_delta,
            },
        },
        {
            "name": "fallback_rate_not_worse",
            "passed": fallback_rate_delta <= max_fallback_rate_delta,
            "details": {
                "base": base_summary["fallback_rate"],
                "candidate": candidate_summary["fallback_rate"],
                "delta": fallback_rate_delta,
                "threshold": max_fallback_rate_delta,
            },
        },
    ]
    return {
        "created_at_unix": int(time.time()),
        "passed": all(item["passed"] for item in checks),
        "checks": checks,
        "metrics": {
            "base": base_summary,
            "candidate": candidate_summary,
            "delta": {
                "pass_rate": pass_rate_delta,
                "fallback_rate": fallback_rate_delta,
            },
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare base Qwen vs fine-tuned Qwen recommendation quality reports.")
    parser.add_argument("--base-report", type=Path, required=True)
    parser.add_argument("--candidate-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("llm/reports/qwen_recommendation_compare.json"))
    parser.add_argument("--min-pass-rate-delta", type=float, default=0.01)
    parser.add_argument("--max-fallback-rate-delta", type=float, default=0.0)
    args = parser.parse_args()

    report = compare_reports(
        load_report(args.base_report),
        load_report(args.candidate_report),
        min_pass_rate_delta=args.min_pass_rate_delta,
        max_fallback_rate_delta=args.max_fallback_rate_delta,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "passed": report["passed"],
        "output": str(args.output),
        "checks": report["checks"],
    }, ensure_ascii=False, indent=2))
    if not report["passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
