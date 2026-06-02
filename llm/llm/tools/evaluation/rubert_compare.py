from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from llm.evaluate import evaluate as evaluate_rubert
from llm.paths import DEFAULT_MODEL_DIR


DEFAULT_REPORT_DIR = Path(__file__).resolve().parents[3] / "reports" / "rubert_compare"
METRIC_PATHS = {
    "category_accuracy": ("category_metrics", "accuracy"),
    "category_macro_f1": ("category_metrics", "macro_f1"),
    "level_accuracy": ("level_metrics", "accuracy"),
    "level_macro_f1": ("level_metrics", "macro_f1"),
    "level_mae": ("level_metrics", "mae"),
    "rating_accuracy": ("rating_metrics", "accuracy"),
    "rating_macro_f1": ("rating_metrics", "macro_f1"),
}
LOWER_IS_BETTER = {"level_mae"}


def run_compare(
    dataset_path: Path,
    current_model_dir: Path,
    candidate_model_dir: Path,
    output_dir: Path,
    max_len: int = 256,
    device: str | None = None,
    min_rating_accuracy_delta: float = 0.0,
    max_level_mae_delta: float = 0.0,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    current_report = evaluate_rubert(
        dataset_path=dataset_path,
        model_dir=current_model_dir,
        output_path=output_dir / "current.json",
        max_len=max_len,
        device=device,
    )
    candidate_report = evaluate_rubert(
        dataset_path=dataset_path,
        model_dir=candidate_model_dir,
        output_path=output_dir / "candidate.json",
        max_len=max_len,
        device=device,
    )
    comparison = compare_reports(
        dataset_path=dataset_path,
        current_report=current_report,
        candidate_report=candidate_report,
        current_model_dir=current_model_dir,
        candidate_model_dir=candidate_model_dir,
        min_rating_accuracy_delta=min_rating_accuracy_delta,
        max_level_mae_delta=max_level_mae_delta,
    )
    (output_dir / "compare_summary.json").write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return comparison


def compare_reports(
    dataset_path: Path,
    current_report: dict[str, Any],
    candidate_report: dict[str, Any],
    current_model_dir: Path,
    candidate_model_dir: Path,
    min_rating_accuracy_delta: float = 0.0,
    max_level_mae_delta: float = 0.0,
) -> dict[str, Any]:
    deltas = metric_deltas(current_report, candidate_report)
    regressions = regression_checks(
        deltas=deltas,
        min_rating_accuracy_delta=min_rating_accuracy_delta,
        max_level_mae_delta=max_level_mae_delta,
    )
    current_errors = error_breakdown(current_report.get("predictions", []))
    candidate_errors = error_breakdown(candidate_report.get("predictions", []))
    return {
        "created_at_unix": int(time.time()),
        "dataset": str(dataset_path),
        "current_model_dir": str(current_model_dir),
        "candidate_model_dir": str(candidate_model_dir),
        "sample_count": candidate_report.get("sample_count"),
        "promote_recommended": not regressions,
        "regressions": regressions,
        "metrics": {
            "current": metric_snapshot(current_report),
            "candidate": metric_snapshot(candidate_report),
            "delta": deltas,
        },
        "errors": {
            "current": current_errors,
            "candidate": candidate_errors,
            "delta": {
                "false_positive_count": candidate_errors["false_positive_count"] - current_errors["false_positive_count"],
                "false_negative_count": candidate_errors["false_negative_count"] - current_errors["false_negative_count"],
                "category_error_count": candidate_errors["category_error_count"] - current_errors["category_error_count"],
                "level_error_count": candidate_errors["level_error_count"] - current_errors["level_error_count"],
                "rating_error_count": candidate_errors["rating_error_count"] - current_errors["rating_error_count"],
            },
        },
    }


def metric_snapshot(report: dict[str, Any]) -> dict[str, float | None]:
    return {name: metric_value(report, path) for name, path in METRIC_PATHS.items()}


def metric_deltas(current_report: dict[str, Any], candidate_report: dict[str, Any]) -> dict[str, float | None]:
    deltas = {}
    for name, path in METRIC_PATHS.items():
        current = metric_value(current_report, path)
        candidate = metric_value(candidate_report, path)
        if current is None or candidate is None:
            deltas[name] = None
        else:
            deltas[name] = round(candidate - current, 4)
    return deltas


def metric_value(report: dict[str, Any], path: tuple[str, str]) -> float | None:
    parent = report.get(path[0])
    if not isinstance(parent, dict):
        return None
    value = parent.get(path[1])
    return float(value) if isinstance(value, (int, float)) else None


def regression_checks(
    deltas: dict[str, float | None],
    min_rating_accuracy_delta: float,
    max_level_mae_delta: float,
) -> list[dict[str, Any]]:
    checks = []
    for metric, delta in deltas.items():
        if delta is None:
            continue
        if metric in LOWER_IS_BETTER:
            regressed = delta > max_level_mae_delta
            threshold = max_level_mae_delta
        elif metric == "rating_accuracy":
            regressed = delta < min_rating_accuracy_delta
            threshold = min_rating_accuracy_delta
        else:
            regressed = delta < 0
            threshold = 0.0
        if regressed:
            checks.append({
                "metric": metric,
                "delta": delta,
                "threshold": threshold,
                "direction": "lower_is_better" if metric in LOWER_IS_BETTER else "higher_is_better",
            })
    return checks


def error_breakdown(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    false_positives = []
    false_negatives = []
    category_errors = []
    level_errors = []
    rating_errors = []

    for row in predictions:
        expected_category = row.get("category")
        predicted_category = row.get("predicted_category")
        expected_rating = row.get("rating")
        predicted_rating = row.get("predicted_rating")

        if expected_category == "safe" and predicted_category != "safe":
            false_positives.append(compact_prediction(row))
        if expected_category != "safe" and predicted_category == "safe":
            false_negatives.append(compact_prediction(row))
        if expected_category != predicted_category:
            category_errors.append(compact_prediction(row))
        if row.get("level") != row.get("predicted_level"):
            level_errors.append(compact_prediction(row))
        if expected_rating is not None and expected_rating != predicted_rating:
            rating_errors.append(compact_prediction(row))

    return {
        "false_positive_count": len(false_positives),
        "false_negative_count": len(false_negatives),
        "category_error_count": len(category_errors),
        "level_error_count": len(level_errors),
        "rating_error_count": len(rating_errors),
        "false_positive_examples": false_positives[:25],
        "false_negative_examples": false_negatives[:25],
        "category_error_examples": category_errors[:25],
        "level_error_examples": level_errors[:25],
        "rating_error_examples": rating_errors[:25],
    }


def compact_prediction(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "text": shorten(row.get("text", ""), 220),
        "expected": {
            "category": row.get("category"),
            "level": row.get("level"),
            "rating": row.get("rating"),
        },
        "predicted": {
            "category": row.get("predicted_category"),
            "level": row.get("predicted_level"),
            "rating": row.get("predicted_rating"),
        },
        "confidence": {
            "category": row.get("category_confidence"),
            "level": row.get("level_confidence"),
            "rating": row.get("rating_confidence"),
        },
    }


def shorten(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare current RuBERT with a candidate model on one dataset.")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--current-model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--candidate-model-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--max-len", type=int, default=256)
    parser.add_argument("--device", default=None)
    parser.add_argument("--min-rating-accuracy-delta", type=float, default=0.0)
    parser.add_argument("--max-level-mae-delta", type=float, default=0.0)
    args = parser.parse_args()

    report = run_compare(
        dataset_path=args.dataset,
        current_model_dir=args.current_model_dir,
        candidate_model_dir=args.candidate_model_dir,
        output_dir=args.output_dir,
        max_len=args.max_len,
        device=args.device,
        min_rating_accuracy_delta=args.min_rating_accuracy_delta,
        max_level_mae_delta=args.max_level_mae_delta,
    )
    print(json.dumps({
        "promote_recommended": report["promote_recommended"],
        "regression_count": len(report["regressions"]),
        "output": str(args.output_dir / "compare_summary.json"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
