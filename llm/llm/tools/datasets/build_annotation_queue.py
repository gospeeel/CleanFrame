import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Build annotation queue from evaluation report errors.")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("datasets/golden/annotation_queue.jsonl"))
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()

    report = json.loads(args.report.read_text(encoding="utf-8"))
    seen = set()
    rows = []
    for section in ("category_examples", "level_examples", "low_confidence_examples"):
        for item in report.get("errors", {}).get(section, []):
            item_id = item.get("id") or item.get("text")
            if item_id in seen:
                continue
            seen.add(item_id)
            rows.append({
                "id": item.get("id"),
                "text": item.get("text"),
                "category": item.get("category"),
                "level": item.get("level"),
                "rating": item.get("rating"),
                "model_prediction": {
                    "category": item.get("predicted_category"),
                    "level": item.get("predicted_level"),
                    "rating": item.get("predicted_rating"),
                    "category_confidence": item.get("category_confidence"),
                    "level_confidence": item.get("level_confidence"),
                    "rating_confidence": item.get("rating_confidence"),
                },
                "review": {
                    "category": None,
                    "level": None,
                    "rating": None,
                    "comment": None,
                },
                "source": "evaluation_error_queue",
            })
            if len(rows) >= args.limit:
                break
        if len(rows) >= args.limit:
            break

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(json.dumps({"output": str(args.output), "count": len(rows)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
