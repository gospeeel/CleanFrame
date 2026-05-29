import argparse
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

from sklearn.metrics import (
    accuracy_score,
    classification_report,
    cohen_kappa_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
)

from llm.paths import DEFAULT_MODEL_DIR
from llm.classification.rubert import get_model_manifest, predict_text, validate_model_dir


REQUIRED_FIELDS = {"id", "text", "category", "level"}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc

            missing = REQUIRED_FIELDS - row.keys()
            if missing:
                raise ValueError(f"{path}:{line_no}: missing fields: {', '.join(sorted(missing))}")

            row["level"] = int(row["level"])
            rows.append(row)

    if not rows:
        raise ValueError(f"Dataset is empty: {path}")
    return rows


def confidence_bucket(value: float) -> str:
    lower = int(value * 10) / 10
    upper = min(1.0, lower + 0.1)
    return f"{lower:.1f}-{upper:.1f}"


def summarize_confidence(rows: list[dict[str, Any]], target_key: str, prediction_key: str, confidence_key: str):
    buckets: dict[str, list[bool]] = defaultdict(list)
    for row in rows:
        buckets[confidence_bucket(row[confidence_key])].append(row[target_key] == row[prediction_key])

    return {
        bucket: {
            "count": len(values),
            "accuracy": round(sum(values) / len(values), 4),
        }
        for bucket, values in sorted(buckets.items())
    }


def evaluate(dataset_path: Path, model_dir: Path, output_path: Path, max_len: int, device: str | None):
    t0 = time.time()
    model_dir = validate_model_dir(model_dir)
    examples = load_jsonl(dataset_path)

    categories = sorted(get_model_manifest(model_dir).get("categories", {}).keys())
    if not categories:
        categories = sorted({row["category"] for row in examples})

    predictions = []
    for row in examples:
        prediction = predict_text(
            row["text"],
            model_path=model_dir,
            max_len=max_len,
            device=device,
        )
        predictions.append(
            {
                **row,
                "predicted_category": prediction["category"],
                "predicted_level": prediction["level"],
                "predicted_rating": prediction["rating"],
                "category_confidence": prediction["category_confidence"],
                "level_confidence": prediction["level_confidence"],
                "rating_confidence": prediction["rating_confidence"],
                "category_scores": prediction["category_scores"],
                "level_scores": prediction["level_scores"],
                "rating_scores": prediction["rating_scores"],
            }
        )

    y_category_true = [row["category"] for row in predictions]
    y_category_pred = [row["predicted_category"] for row in predictions]
    y_level_true = [row["level"] for row in predictions]
    y_level_pred = [row["predicted_level"] for row in predictions]
    has_rating = all("rating" in row for row in predictions)

    category_labels = sorted(set(categories) | set(y_category_true) | set(y_category_pred))
    observed_category_labels = sorted(set(y_category_true) | set(y_category_pred))
    level_labels = sorted(set(y_level_true) | set(y_level_pred))
    category_cm = confusion_matrix(y_category_true, y_category_pred, labels=category_labels)
    level_cm = confusion_matrix(y_level_true, y_level_pred, labels=level_labels)

    category_errors = [
        row for row in predictions
        if row["category"] != row["predicted_category"]
    ]
    level_errors = [
        row for row in predictions
        if row["level"] != row["predicted_level"]
    ]
    low_confidence = [
        row for row in predictions
        if row["category_confidence"] < 0.7 or row["level_confidence"] < 0.7
    ]

    category_support = Counter(y_category_true)
    level_support = Counter(y_level_true)
    rating_metrics = None
    if has_rating:
        y_rating_true = [row["rating"] for row in predictions]
        y_rating_pred = [row["predicted_rating"] for row in predictions]
        rating_labels = ["0+", "6+", "12+", "16+", "18+"]
        rating_cm = confusion_matrix(y_rating_true, y_rating_pred, labels=rating_labels)
        rating_metrics = {
            "accuracy": round(accuracy_score(y_rating_true, y_rating_pred), 4),
            "macro_f1": round(f1_score(y_rating_true, y_rating_pred, labels=rating_labels, average="macro", zero_division=0), 4),
            "support": dict(sorted(Counter(y_rating_true).items())),
            "confusion_matrix": {
                "labels": rating_labels,
                "matrix": rating_cm.tolist(),
            },
        }

    report = {
        "dataset": str(dataset_path),
        "model_dir": str(model_dir),
        "model_manifest": get_model_manifest(model_dir),
        "created_at_unix": int(time.time()),
        "elapsed_seconds": round(time.time() - t0, 3),
        "sample_count": len(predictions),
        "category_metrics": {
            "accuracy": round(accuracy_score(y_category_true, y_category_pred), 4),
            "macro_f1": round(f1_score(y_category_true, y_category_pred, labels=category_labels, average="macro", zero_division=0), 4),
            "observed_macro_f1": round(f1_score(y_category_true, y_category_pred, labels=observed_category_labels, average="macro", zero_division=0), 4),
            "weighted_f1": round(f1_score(y_category_true, y_category_pred, labels=category_labels, average="weighted", zero_division=0), 4),
            "support": dict(sorted(category_support.items())),
            "classification_report": classification_report(
                y_category_true,
                y_category_pred,
                labels=category_labels,
                zero_division=0,
                output_dict=True,
            ),
            "confusion_matrix": {
                "labels": category_labels,
                "matrix": category_cm.tolist(),
            },
            "confidence_buckets": summarize_confidence(
                predictions,
                target_key="category",
                prediction_key="predicted_category",
                confidence_key="category_confidence",
            ),
        },
        "level_metrics": {
            "accuracy": round(accuracy_score(y_level_true, y_level_pred), 4),
            "macro_f1": round(f1_score(y_level_true, y_level_pred, labels=level_labels, average="macro", zero_division=0), 4),
            "mae": round(mean_absolute_error(y_level_true, y_level_pred), 4),
            "quadratic_weighted_kappa": round(cohen_kappa_score(y_level_true, y_level_pred, weights="quadratic"), 4),
            "support": {str(k): v for k, v in sorted(level_support.items())},
            "confusion_matrix": {
                "labels": level_labels,
                "matrix": level_cm.tolist(),
            },
            "confidence_buckets": summarize_confidence(
                predictions,
                target_key="level",
                prediction_key="predicted_level",
                confidence_key="level_confidence",
            ),
        },
        "rating_metrics": rating_metrics,
        "confidence_summary": {
            "mean_category_confidence": round(mean(row["category_confidence"] for row in predictions), 4),
            "mean_level_confidence": round(mean(row["level_confidence"] for row in predictions), 4),
        },
        "errors": {
            "category_count": len(category_errors),
            "level_count": len(level_errors),
            "low_confidence_count": len(low_confidence),
            "category_examples": category_errors[:50],
            "level_examples": level_errors[:50],
            "low_confidence_examples": low_confidence[:50],
        },
        "predictions": predictions,
    }

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except PermissionError as exc:
        raise PermissionError(
            f"Нет прав на запись отчёта в {output_path}. "
            "Если папка была создана Docker-контейнером, исправьте владельца: "
            f"sudo chown -R $(id -u):$(id -g) {output_path.parent}"
        ) from exc
    return report


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate ML_WINK RuBERT model on a JSONL golden dataset.")
    parser.add_argument("--dataset", required=True, type=Path, help="Path to JSONL dataset.")
    parser.add_argument("--model-dir", default=DEFAULT_MODEL_DIR, type=Path, help="Path to trained_model directory.")
    parser.add_argument("--output", default=Path("evaluation_report.json"), type=Path, help="Where to write JSON report.")
    parser.add_argument("--max-len", default=256, type=int, help="Tokenizer max length.")
    parser.add_argument("--device", default=None, help="Torch device, e.g. cpu or cuda.")
    return parser.parse_args()


def main():
    args = parse_args()
    report = evaluate(
        dataset_path=args.dataset,
        model_dir=args.model_dir,
        output_path=args.output,
        max_len=args.max_len,
        device=args.device,
    )
    print(json.dumps({
        "sample_count": report["sample_count"],
        "category_accuracy": report["category_metrics"]["accuracy"],
        "category_macro_f1": report["category_metrics"]["macro_f1"],
        "category_observed_macro_f1": report["category_metrics"]["observed_macro_f1"],
        "level_accuracy": report["level_metrics"]["accuracy"],
        "level_mae": report["level_metrics"]["mae"],
        "rating_accuracy": report["rating_metrics"]["accuracy"] if report["rating_metrics"] else None,
        "output": str(args.output),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
