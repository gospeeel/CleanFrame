from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from llm.detection.rule_detector import is_suspicious_scene


DEFAULT_DATASET = Path(__file__).resolve().parents[3] / "datasets" / "silver" / "ambiguous_contexts.jsonl"
DEFAULT_REPORT_PATH = Path(__file__).resolve().parents[3] / "reports" / "ambiguous_context_eval.json"


def evaluate_ambiguous_contexts(
    dataset_path: Path = DEFAULT_DATASET,
    output_path: Path = DEFAULT_REPORT_PATH,
) -> dict[str, Any]:
    started = time.monotonic()
    rows = load_jsonl(dataset_path)
    failures = []
    by_source: dict[str, dict[str, int]] = {}

    for row in rows:
        result = is_suspicious_scene(row["text"])
        active = active_categories(result)
        expected_suspicious = bool(row.get("expected_suspicious", False))
        required = set(row.get("required_categories", []))
        forbidden = set(row.get("forbidden_categories", []))

        errors = []
        if bool(result.get("is_suspicious")) != expected_suspicious:
            errors.append(
                f"expected_suspicious={expected_suspicious}, got={bool(result.get('is_suspicious'))}"
            )

        missing = sorted(required - active)
        if missing:
            errors.append(f"missing required categories: {missing}")

        forbidden_present = sorted(forbidden & active)
        if forbidden_present:
            errors.append(f"forbidden categories present: {forbidden_present}")

        source = str(row.get("source", "unknown"))
        by_source.setdefault(source, {"total": 0, "passed": 0})
        by_source[source]["total"] += 1
        if not errors:
            by_source[source]["passed"] += 1
            continue

        failures.append({
            "id": row.get("id"),
            "line": row.get("_line"),
            "source": source,
            "text": row.get("text"),
            "errors": errors,
            "active_categories": sorted(active),
            "matched_terms": result.get("matched_terms", {}),
        })

    total = len(rows)
    passed = total - len(failures)
    report = {
        "dataset": str(dataset_path),
        "created_at_unix": int(time.time()),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "summary": {
            "total": total,
            "passed": passed,
            "failed": len(failures),
            "pass_rate": round(passed / total, 4) if total else 0.0,
            "by_source": {
                source: {
                    **stats,
                    "pass_rate": round(stats["passed"] / stats["total"], 4) if stats["total"] else 0.0,
                }
                for source, stats in sorted(by_source.items())
            },
        },
        "failures": failures,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            row["_line"] = line_number
            rows.append(row)
    return rows


def active_categories(result: dict[str, Any]) -> set[str]:
    return {
        category
        for category, is_active in result.get("normalized_flags", {}).items()
        if is_active
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate ambiguous-context regression dataset.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--fail-under", type=float, default=1.0)
    args = parser.parse_args()

    report = evaluate_ambiguous_contexts(args.dataset, args.output)
    summary = report["summary"]
    print(
        f"ambiguous_contexts total={summary['total']} passed={summary['passed']} "
        f"failed={summary['failed']} pass_rate={summary['pass_rate']}"
    )
    if summary["pass_rate"] < args.fail_under:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
