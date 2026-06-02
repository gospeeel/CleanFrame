from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from llm.recommendations.service import (
    build_recommendation_context,
    generate_recommendation_packages_batch,
    load_recommendation_examples,
)


def read_jsonl(path: Path, limit: int, require_evidence: bool = False) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            if require_evidence and not row.get("input", {}).get("evidence"):
                continue
            rows.append(row)
            if len(rows) >= limit:
                break
    return rows


def example_to_context(row: dict) -> dict:
    payload = row["input"]
    return build_recommendation_context(
        item_id=row["id"],
        text=payload["text"],
        category=payload["category"],
        category_label=payload.get("category_label"),
        secondary_categories=payload.get("secondary_categories", []),
        level=int(payload["level"]),
        level_label=payload.get("level_label"),
        rating=payload["rating"],
        target_rating=payload["target_rating"],
        evidence=payload.get("evidence", []),
        confidence={"category": 1.0, "level": 1.0, "rating": 1.0},
        needs_review=True,
    )


def run_variant(name: str, contexts: list[dict], examples_path: Path | None, examples_limit: int) -> dict:
    previous_path = os.environ.get("LLM_RECOMMENDATION_EXAMPLES_PATH")
    previous_limit = os.environ.get("LLM_RECOMMENDATION_EXAMPLES_LIMIT")
    try:
        if examples_path is None:
            os.environ["LLM_RECOMMENDATION_EXAMPLES_LIMIT"] = "0"
            os.environ.pop("LLM_RECOMMENDATION_EXAMPLES_PATH", None)
        else:
            os.environ["LLM_RECOMMENDATION_EXAMPLES_PATH"] = str(examples_path)
            os.environ["LLM_RECOMMENDATION_EXAMPLES_LIMIT"] = str(examples_limit)
        load_recommendation_examples.cache_clear()

        started = time.monotonic()
        packages = generate_recommendation_packages_batch(contexts)
        elapsed = time.monotonic() - started
    finally:
        if previous_path is None:
            os.environ.pop("LLM_RECOMMENDATION_EXAMPLES_PATH", None)
        else:
            os.environ["LLM_RECOMMENDATION_EXAMPLES_PATH"] = previous_path
        if previous_limit is None:
            os.environ.pop("LLM_RECOMMENDATION_EXAMPLES_LIMIT", None)
        else:
            os.environ["LLM_RECOMMENDATION_EXAMPLES_LIMIT"] = previous_limit
        load_recommendation_examples.cache_clear()

    items = []
    for context in contexts:
        package = packages[context["id"]]
        recommendation = package.get("recommendation", {})
        payload = package.get("llm_recommendation", {})
        items.append({
            "id": context["id"],
            "fallback_used": package.get("fallback_used"),
            "self_check_passed": recommendation.get("self_check_passed"),
            "summary": recommendation.get("summary"),
            "suggestion_count": len(payload.get("rewrite_suggestions", [])),
            "fallback_reason": package.get("fallback_reason"),
        })

    return {
        "variant": name,
        "elapsed_seconds": round(elapsed, 3),
        "fallback_count": sum(1 for item in items if item["fallback_used"]),
        "self_check_passed_count": sum(1 for item in items if item["self_check_passed"]),
        "items": items,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare default Qwen recommendations with pseudo few-shot mode.")
    parser.add_argument("--examples", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=2)
    parser.add_argument("--few-shot-limit", type=int, default=2)
    parser.add_argument("--require-evidence", action="store_true")
    args = parser.parse_args()

    rows = read_jsonl(args.examples, args.limit, require_evidence=args.require_evidence)
    contexts = [example_to_context(row) for row in rows]
    report = {
        "examples": str(args.examples),
        "input_count": len(contexts),
        "default": run_variant("default", contexts, None, 0),
        "pseudo_few_shot": run_variant("pseudo_few_shot", contexts, args.examples, args.few_shot_limit),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
