import argparse
import json
import subprocess
import sys
from pathlib import Path


DEFAULT_BASE_MODELS = [
    "DeepPavlov/rubert-base-cased",
    "ai-forever/ruBert-base",
    "cointegrated/rubert-tiny2",
]


def safe_name(model_name: str) -> str:
    return model_name.replace("/", "__").replace(":", "_")


def run_command(command: list[str]) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, check=True)


def main():
    parser = argparse.ArgumentParser(description="Train and evaluate several base models on ML_WINK JSONL datasets.")
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--test", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("model_candidates"))
    parser.add_argument("--report-dir", type=Path, default=Path("reports/model_comparison"))
    parser.add_argument("--base-model", action="append", dest="base_models", default=None)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--device", default=None)
    args = parser.parse_args()

    base_models = args.base_models or DEFAULT_BASE_MODELS
    summary = []
    for base_model in base_models:
        candidate_dir = args.output_dir / safe_name(base_model)
        report_path = args.report_dir / f"{safe_name(base_model)}.json"
        run_command([
            sys.executable,
            "-m",
            "llm.tools.training.train_jsonl",
            "--train",
            str(args.train),
            "--validation",
            str(args.validation),
            "--output-dir",
            str(candidate_dir),
            "--base-model",
            base_model,
            "--epochs",
            str(args.epochs),
            "--batch-size",
            str(args.batch_size),
            *([] if args.device is None else ["--device", args.device]),
        ])
        run_command([
            sys.executable,
            "-m",
            "llm.evaluate",
            "--dataset",
            str(args.test),
            "--model-dir",
            str(candidate_dir),
            "--output",
            str(report_path),
            *([] if args.device is None else ["--device", args.device]),
        ])
        report = json.loads(report_path.read_text(encoding="utf-8"))
        summary.append({
            "base_model": base_model,
            "candidate_dir": str(candidate_dir),
            "report": str(report_path),
            "category_macro_f1": report["category_metrics"]["macro_f1"],
            "level_macro_f1": report["level_metrics"]["macro_f1"],
            "level_mae": report["level_metrics"]["mae"],
            "rating_macro_f1": report["rating_metrics"]["macro_f1"] if report["rating_metrics"] else None,
            "rating_accuracy": report["rating_metrics"]["accuracy"] if report["rating_metrics"] else None,
        })

    args.report_dir.mkdir(parents=True, exist_ok=True)
    summary_path = args.report_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"summary": str(summary_path), "results": summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
