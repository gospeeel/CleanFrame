from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any


SYSTEM_PROMPT = (
    "Ты локальный редакторский ассистент ML_WINK для анализа возрастных рисков сценария. "
    "Не меняй категорию, уровень, рейтинг, target_rating, evidence и флаг проверки: "
    "они рассчитаны отдельным rating engine. Верни только валидный JSON."
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row.get("input"), dict) or not isinstance(row.get("expected"), dict):
                raise ValueError(f"{path}:{line_no}: expected recommendation row with input and expected objects")
            rows.append(row)
    if not rows:
        raise ValueError(f"Dataset is empty: {path}")
    return rows


def to_sft_example(row: dict[str, Any], include_metadata: bool = True) -> dict[str, Any]:
    input_payload = row["input"]
    expected = normalized_expected(row["expected"])
    example = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(input_payload)},
            {"role": "assistant", "content": json.dumps(expected, ensure_ascii=False, separators=(",", ":"))},
        ]
    }
    if include_metadata:
        example["metadata"] = {
            "id": row.get("id"),
            "source_document": row.get("source_document"),
            "label_source": row.get("label_source"),
            "needs_human_review": row.get("needs_human_review", True),
            "category": input_payload.get("category"),
            "rating": input_payload.get("rating"),
            "target_rating": input_payload.get("target_rating"),
        }
    return example


def build_user_prompt(input_payload: dict[str, Any]) -> str:
    compact = {
        "text": input_payload.get("text", ""),
        "primary_category_id": input_payload.get("category"),
        "primary_category_label": input_payload.get("category_label"),
        "secondary_categories": input_payload.get("secondary_categories", []),
        "level": input_payload.get("level"),
        "level_label": input_payload.get("level_label"),
        "rating": input_payload.get("rating"),
        "target_rating": input_payload.get("target_rating"),
        "evidence": input_payload.get("evidence", []),
        "legal_context": [
            {
                "id": item.get("id"),
                "policy_version": item.get("policy_version"),
                "text": item.get("text"),
                "retrieval_reason": item.get("retrieval_reason"),
            }
            for item in input_payload.get("legal_context", [])[:3]
            if isinstance(item, dict)
        ],
    }
    return (
        "Сформулируй краткое объяснение риска, 1-4 risk_factors и ровно 3 rewrite_suggestions "
        "для снижения к target_rating. Каждая правка должна иметь goal, before, after, rationale, "
        "expected_effect и опираться на evidence или исходный текст.\n\n"
        f"Rating engine facts:\n{json.dumps(compact, ensure_ascii=False, indent=2)}"
    )


def normalized_expected(expected: dict[str, Any]) -> dict[str, Any]:
    suggestions = expected.get("rewrite_suggestions", [])
    if not isinstance(suggestions, list):
        suggestions = []
    return {
        "summary": expected.get("summary", ""),
        "explanation": expected.get("explanation", ""),
        "risk_factors": expected.get("risk_factors", []) if isinstance(expected.get("risk_factors"), list) else [],
        "rewrite_suggestions": suggestions[:3],
        "self_check_passed": bool(expected.get("self_check_passed", True)),
        "uncertainty_note": expected.get("uncertainty_note"),
    }


def split_rows(rows: list[dict[str, Any]], validation_ratio: float, test_ratio: float, seed: int) -> dict[str, list[dict[str, Any]]]:
    shuffled = list(rows)
    random.Random(seed).shuffle(shuffled)
    validation_count = int(len(shuffled) * validation_ratio)
    test_count = int(len(shuffled) * test_ratio)
    train_count = len(shuffled) - validation_count - test_count
    return {
        "train": shuffled[:train_count],
        "validation": shuffled[train_count:train_count + validation_count],
        "test": shuffled[train_count + validation_count:],
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def build_dataset(
    input_path: Path,
    output_dir: Path,
    validation_ratio: float = 0.1,
    test_ratio: float = 0.1,
    seed: int = 42,
    source_label: str = "pseudo",
) -> dict[str, Any]:
    rows = read_jsonl(input_path)
    splits = split_rows(rows, validation_ratio=validation_ratio, test_ratio=test_ratio, seed=seed)
    output_dir.mkdir(parents=True, exist_ok=True)
    for split_name, split_rows_value in splits.items():
        write_jsonl(output_dir / f"{split_name}.jsonl", [to_sft_example(row) for row in split_rows_value])

    manifest = {
        "dataset_type": "qwen_recommendation_sft",
        "source": str(input_path),
        "source_label": source_label,
        "warning": "Use pseudo/silver labels only for rehearsal. Production LoRA/SFT requires human-verified labels.",
        "splits": {name: len(items) for name, items in splits.items()},
        "validation_ratio": validation_ratio,
        "test_ratio": test_ratio,
        "seed": seed,
        "format": "chat_messages_jsonl",
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert recommendation examples into Qwen chat-SFT JSONL splits.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("llm/datasets/silver/qwen_sft"))
    parser.add_argument("--validation-ratio", type=float, default=0.1)
    parser.add_argument("--test-ratio", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--source-label", default="pseudo")
    args = parser.parse_args()

    manifest = build_dataset(
        input_path=args.input,
        output_dir=args.output_dir,
        validation_ratio=args.validation_ratio,
        test_ratio=args.test_ratio,
        seed=args.seed,
        source_label=args.source_label,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
