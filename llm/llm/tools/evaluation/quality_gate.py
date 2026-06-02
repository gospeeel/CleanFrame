from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from llm.evaluate import evaluate as evaluate_rubert
from llm.evaluate_golden import DEFAULT_DATASET as DEFAULT_GOLDEN_DATASET
from llm.evaluate_golden import evaluate as evaluate_golden
from llm.paths import DEFAULT_MODEL_DIR
from llm.tools.evaluation.ambiguous_contexts import DEFAULT_DATASET as DEFAULT_AMBIGUOUS_CONTEXTS_DATASET
from llm.tools.evaluation.ambiguous_contexts import evaluate_ambiguous_contexts
from llm.tools.evaluation.evidence_quality import evaluate_evidence_quality
from llm.tools.evaluation.recommendations_quality import evaluate_dataset as evaluate_recommendations
from llm.tools.evaluation.rubert_compare import run_compare as compare_rubert_models


DEFAULT_REPORT_DIR = Path(__file__).resolve().parents[3] / "reports"


def main() -> None:
    args = parse_args()
    report_dir = args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    checks = []

    rules_report = evaluate_golden(args.golden_dataset, mode="rules")
    write_json(report_dir / "golden_rules.json", rules_report)
    checks.append(check("golden_rules_failed_zero", rules_report["failed"] == 0, {
        "failed": rules_report["failed"],
        "total": rules_report["total"],
    }))

    if not args.skip_ambiguous_contexts:
        ambiguous_report = evaluate_ambiguous_contexts(
            dataset_path=args.ambiguous_contexts_dataset,
            output_path=report_dir / "ambiguous_context_eval.json",
        )
        ambiguous_summary = ambiguous_report["summary"]
        checks.append(check(
            "ambiguous_contexts_pass_rate",
            ambiguous_summary["pass_rate"] >= args.min_ambiguous_contexts_pass_rate,
            {
                "pass_rate": ambiguous_summary["pass_rate"],
                "threshold": args.min_ambiguous_contexts_pass_rate,
                "failed": ambiguous_summary["failed"],
                "total": ambiguous_summary["total"],
            },
        ))

    if args.run_pipeline_golden:
        pipeline_report = evaluate_golden(args.golden_dataset, mode="pipeline")
        write_json(report_dir / "golden_pipeline.json", pipeline_report)
        write_json(report_dir / "golden_pipeline_failures.json", analyze_golden_failures(pipeline_report))
        checks.append(check(
            "golden_pipeline_rating_accuracy",
            pipeline_report["rating_accuracy"] >= args.min_pipeline_rating_accuracy,
            {
                "rating_accuracy": pipeline_report["rating_accuracy"],
                "threshold": args.min_pipeline_rating_accuracy,
                "failed": pipeline_report["failed"],
            },
        ))

    if args.run_evidence_quality:
        evidence_report = evaluate_evidence_quality(
            dataset_path=args.golden_dataset,
            output_path=report_dir / "evidence_quality.json",
            mode=args.evidence_quality_mode,
        )
        evidence_summary = evidence_report["summary"]
        checks.append(check(
            "evidence_quality_accuracy",
            evidence_summary["evidence_accuracy"] >= args.min_evidence_accuracy,
            {
                "evidence_accuracy": evidence_summary["evidence_accuracy"],
                "threshold": args.min_evidence_accuracy,
                "term_recall": evidence_summary["evidence_term_recall"],
                "false_positive_evidence_rate": evidence_summary["false_positive_evidence_rate"],
            },
        ))
        checks.append(check(
            "evidence_false_positive_rate",
            evidence_summary["false_positive_evidence_rate"] <= args.max_false_positive_evidence_rate,
            {
                "false_positive_evidence_rate": evidence_summary["false_positive_evidence_rate"],
                "threshold": args.max_false_positive_evidence_rate,
            },
        ))

    if args.rubert_dataset:
        rubert_report = evaluate_rubert(
            dataset_path=args.rubert_dataset,
            model_dir=args.rubert_model_dir,
            output_path=report_dir / "rubert_evaluation.json",
            max_len=args.rubert_max_len,
            device=args.rubert_device,
        )
        checks.extend(rubert_checks(rubert_report, args))

    if args.rubert_candidate_model_dir:
        if not args.rubert_dataset:
            raise ValueError("--rubert-candidate-model-dir requires --rubert-dataset")
        compare_report = compare_rubert_models(
            dataset_path=args.rubert_dataset,
            current_model_dir=args.rubert_model_dir,
            candidate_model_dir=args.rubert_candidate_model_dir,
            output_dir=report_dir / "rubert_compare",
            max_len=args.rubert_max_len,
            device=args.rubert_device,
            min_rating_accuracy_delta=args.min_candidate_rating_accuracy_delta,
            max_level_mae_delta=args.max_candidate_level_mae_delta,
        )
        checks.append(check(
            "rubert_candidate_compare",
            compare_report["promote_recommended"],
            {
                "promote_recommended": compare_report["promote_recommended"],
                "regression_count": len(compare_report["regressions"]),
                "regressions": compare_report["regressions"],
                "report": str(report_dir / "rubert_compare" / "compare_summary.json"),
            },
        ))

    if args.recommendations_dataset:
        recommendation_report = evaluate_recommendations(
            dataset_path=args.recommendations_dataset,
            output_path=report_dir / "recommendations_quality.json",
            limit=args.recommendations_limit,
            batch_size=args.recommendations_batch_size,
            use_expected=args.recommendations_use_expected,
        )
        summary = recommendation_report["summary"]
        checks.append(check(
            "recommendations_pass_rate",
            summary["pass_rate"] >= args.min_recommendations_pass_rate,
            {"pass_rate": summary["pass_rate"], "threshold": args.min_recommendations_pass_rate},
        ))
        checks.append(check(
            "recommendations_fallback_rate",
            summary["fallback_rate"] <= args.max_recommendations_fallback_rate,
            {"fallback_rate": summary["fallback_rate"], "threshold": args.max_recommendations_fallback_rate},
        ))

    summary_report = {
        "created_at_unix": int(time.time()),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "report_dir": str(report_dir),
        "passed": all(item["passed"] for item in checks),
        "checks": checks,
    }
    write_json(report_dir / "quality_gate_summary.json", summary_report)
    print(json.dumps(summary_report, ensure_ascii=False, indent=2))
    if not summary_report["passed"]:
        sys.exit(1)


def rubert_checks(report: dict[str, Any], args: argparse.Namespace) -> list[dict[str, Any]]:
    rating_metrics = report.get("rating_metrics") or {}
    return [
        check(
            "rubert_category_accuracy",
            report["category_metrics"]["accuracy"] >= args.min_rubert_category_accuracy,
            {
                "accuracy": report["category_metrics"]["accuracy"],
                "threshold": args.min_rubert_category_accuracy,
            },
        ),
        check(
            "rubert_level_accuracy",
            report["level_metrics"]["accuracy"] >= args.min_rubert_level_accuracy,
            {
                "accuracy": report["level_metrics"]["accuracy"],
                "threshold": args.min_rubert_level_accuracy,
            },
        ),
        check(
            "rubert_level_mae",
            report["level_metrics"]["mae"] <= args.max_rubert_level_mae,
            {
                "mae": report["level_metrics"]["mae"],
                "threshold": args.max_rubert_level_mae,
            },
        ),
        check(
            "rubert_rating_accuracy",
            rating_metrics.get("accuracy", 0.0) >= args.min_rubert_rating_accuracy,
            {
                "accuracy": rating_metrics.get("accuracy"),
                "threshold": args.min_rubert_rating_accuracy,
            },
        ),
    ]


def analyze_golden_failures(report: dict[str, Any]) -> dict[str, Any]:
    failures = []
    by_kind: dict[str, int] = {}
    for item in report.get("failures", []):
        kind = golden_failure_kind(item)
        by_kind[kind] = by_kind.get(kind, 0) + 1
        actual = item.get("actual", {})
        expected = item.get("expected", {})
        failures.append({
            "id": item.get("id"),
            "kind": kind,
            "expected_rating": expected.get("rating"),
            "actual_rating": actual.get("rating"),
            "expected_primary_category": expected.get("primary_category"),
            "actual_primary_category": actual.get("primary_category"),
            "actual_level": actual.get("level"),
            "confidence": actual.get("confidence", {}),
            "evidence_count": actual.get("evidence_count", 0),
            "matched_terms": actual.get("matched_terms", {}),
            "aggregation_reason": actual.get("aggregation_reason"),
            "checks": {
                "risk_ok": item.get("risk_ok"),
                "category_ok": item.get("category_ok"),
                "secondary_ok": item.get("secondary_ok"),
                "rating_ok": item.get("rating_ok"),
                "evidence_ok": item.get("evidence_ok"),
            },
        })

    return {
        "dataset": report.get("dataset"),
        "mode": report.get("mode"),
        "total": report.get("total"),
        "failed": report.get("failed"),
        "by_kind": by_kind,
        "failures": failures,
    }


def golden_failure_kind(item: dict[str, Any]) -> str:
    if not item.get("risk_ok"):
        expected = item.get("expected", {})
        actual = item.get("actual", {})
        if not expected.get("risk_detected") and actual.get("risk_detected"):
            return "false_positive"
        if expected.get("risk_detected") and not actual.get("risk_detected"):
            return "false_negative"
        return "risk_mismatch"
    if not item.get("category_ok"):
        return "category_mismatch"
    if not item.get("secondary_ok"):
        return "secondary_mismatch"
    if not item.get("rating_ok"):
        return "rating_mismatch"
    if not item.get("evidence_ok"):
        return "evidence_mismatch"
    return "other"


def check(name: str, passed: bool, details: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "passed": bool(passed),
        "details": details,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ML_WINK LLM quality gates and write reports.")
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--golden-dataset", type=Path, default=DEFAULT_GOLDEN_DATASET)
    parser.add_argument("--skip-ambiguous-contexts", action="store_true")
    parser.add_argument("--ambiguous-contexts-dataset", type=Path, default=DEFAULT_AMBIGUOUS_CONTEXTS_DATASET)
    parser.add_argument("--min-ambiguous-contexts-pass-rate", type=float, default=1.0)

    parser.add_argument("--run-pipeline-golden", action="store_true")
    parser.add_argument("--min-pipeline-rating-accuracy", type=float, default=0.8)
    parser.add_argument("--run-evidence-quality", action="store_true")
    parser.add_argument("--evidence-quality-mode", choices=["rules", "pipeline"], default="rules")
    parser.add_argument("--min-evidence-accuracy", type=float, default=0.85)
    parser.add_argument("--max-false-positive-evidence-rate", type=float, default=0.1)

    parser.add_argument("--rubert-dataset", type=Path)
    parser.add_argument("--rubert-model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--rubert-max-len", type=int, default=256)
    parser.add_argument("--rubert-device", default=None)
    parser.add_argument("--rubert-candidate-model-dir", type=Path)
    parser.add_argument("--min-candidate-rating-accuracy-delta", type=float, default=0.0)
    parser.add_argument("--max-candidate-level-mae-delta", type=float, default=0.0)
    parser.add_argument("--min-rubert-category-accuracy", type=float, default=0.75)
    parser.add_argument("--min-rubert-level-accuracy", type=float, default=0.65)
    parser.add_argument("--max-rubert-level-mae", type=float, default=0.75)
    parser.add_argument("--min-rubert-rating-accuracy", type=float, default=0.7)

    parser.add_argument("--recommendations-dataset", type=Path)
    parser.add_argument("--recommendations-limit", type=int, default=None)
    parser.add_argument("--recommendations-batch-size", type=int, default=16)
    parser.add_argument("--recommendations-use-expected", action="store_true")
    parser.add_argument("--min-recommendations-pass-rate", type=float, default=0.9)
    parser.add_argument("--max-recommendations-fallback-rate", type=float, default=0.05)
    return parser.parse_args()


if __name__ == "__main__":
    main()
