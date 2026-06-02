from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

import torch

from llm.classification.rubert import predict_texts_batch
from llm.detection.rule_detector import analyze_parsed_script
from llm.legal.policy import calculate_simple_rating
from llm.parsing.script_parser import parse_script
from llm.paths import DEFAULT_MODEL_DIR, resolve_project_path
from llm.rating import aggregate_project_rating
from llm.recommendations.service import build_recommendation_context, fallback_parts
from llm.taxonomy import category_label, evidence_items, level_label, primary_category_from_evidence


DEFAULT_PROJECT_RATINGS = {
    "Аватар.txt": "12+",
    "Большая_Маленькая_Ложь.txt": "18+",
    "Довод.txt": "16+",
    "Железный человек.txt": "12+",
    "Матрица.txt": "16+",
    "Нарко_Серия№101.txt": "18+",
    "Паразиты.txt": "18+",
    "Почему_Женщины_Убивают.txt": "18+",
    "Убийца.txt": "18+",
    "Чернобыль.txt": "18+",
}


def main() -> None:
    args = parse_args()
    rng = random.Random(args.seed)
    input_dir = resolve_project_path(args.input_dir)
    output_dir = resolve_project_path(args.output_dir)
    model_dir = resolve_project_path(args.model_dir)

    files = sorted(path for path in input_dir.rglob("*") if path.suffix.lower() in {".txt", ".pdf", ".docx"})
    if not files:
        raise FileNotFoundError(f"No supported scripts found in {input_dir}")

    all_rows = []
    document_rows = []
    for script_path in files:
        document, rows = build_document_rows(
            script_path=script_path,
            model_dir=model_dir,
            batch_size=args.rubert_batch_size,
            max_len=args.max_len,
            safe_per_document=args.safe_per_document,
            rng=rng,
        )
        document_rows.append(document)
        all_rows.extend(rows)

    selected_rows = select_balanced_rows(all_rows, target_rows=args.target_rows, rng=rng)
    splits = split_rows(selected_rows, args.validation_ratio, args.test_ratio)
    recommendation_splits = {
        name: [build_recommendation_example(row) for row in rows if row["category"] != "safe" and row.get("evidence")]
        for name, rows in splits.items()
    }

    write_jsonl(output_dir / "documents.jsonl", document_rows)
    for split_name, rows in splits.items():
        write_jsonl(output_dir / "rubert" / f"{split_name}.jsonl", rows)
    for split_name, rows in recommendation_splits.items():
        write_jsonl(output_dir / "recommendations" / f"{split_name}.jsonl", rows)

    report = build_report(document_rows, selected_rows, splits, recommendation_splits, args)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def build_document_rows(
    script_path: Path,
    model_dir: Path,
    batch_size: int,
    max_len: int,
    safe_per_document: int,
    rng: random.Random,
) -> tuple[dict, list[dict]]:
    parsed = parse_script(script_path)
    filtered = analyze_parsed_script(parsed)
    expected_project_rating = DEFAULT_PROJECT_RATINGS.get(script_path.name)

    risky_candidates = []
    safe_candidates = []
    total_elements = 0
    for scene in filtered.get("scenes", []):
        for element_index, element in enumerate(scene.get("elements", [])):
            total_elements += 1
            text = (element.get("text") or "").strip()
            if not text:
                continue
            natasha = element.get("natasha_flags", {})
            is_suspicious = natasha.get("is_suspicious", False) if isinstance(natasha, dict) else False
            payload = {
                "source_document": script_path.name,
                "scene_id": scene.get("scene_id"),
                "scene_header": scene.get("header", ""),
                "element_index": element_index,
                "element_type": element.get("type", "action"),
                "character": element.get("character", ""),
                "text": text,
                "expected_project_rating": expected_project_rating,
                "natasha": natasha if isinstance(natasha, dict) else {},
            }
            if is_suspicious:
                risky_candidates.append(payload)
            else:
                safe_candidates.append(payload)

    predictions = predict_texts_batch(
        [" ".join(filter(None, [row.get("character", ""), row["text"]])) for row in risky_candidates],
        model_path=model_dir,
        max_len=max_len,
        device="cuda" if torch.cuda.is_available() else "cpu",
        batch_size=batch_size,
    )

    rows = []
    scene_level_items = []
    for row, prediction in zip(risky_candidates, predictions):
        natasha = row.pop("natasha")
        category, secondary_categories = primary_category_from_evidence(prediction["category"], natasha)
        level = int(prediction["level"])
        rating = prediction.get("rating") or calculate_simple_rating(category, level)
        matched_terms = natasha.get("matched_terms", {}) if isinstance(natasha, dict) else {}
        evidence = evidence_items(row["text"], matched_terms)
        pseudo_row = {
            "id": make_row_id(row["source_document"], row["scene_id"], row["element_index"]),
            **row,
            "category": category,
            "secondary_categories": secondary_categories,
            "level": level,
            "rating": rating,
            "risk_detected": True,
            "evidence": evidence,
            "matched_terms": matched_terms,
            "confidence": {
                "category": prediction["category_confidence"],
                "level": prediction["level_confidence"],
                "rating": prediction["rating_confidence"],
            },
            "label_source": "pseudo_model_rules",
            "needs_human_review": True,
        }
        rows.append(pseudo_row)
        scene_level_items.append({
            "rating": rating,
            "рейтинг": rating,
            "индекс_рейтинга": rating_index(rating),
            "category": category,
            "confidence": pseudo_row["confidence"],
            "evidence": evidence,
        })

    rng.shuffle(safe_candidates)
    for row in safe_candidates[:safe_per_document]:
        row.pop("natasha", None)
        rows.append({
            "id": make_row_id(row["source_document"], row["scene_id"], row["element_index"]),
            **row,
            "category": "safe",
            "secondary_categories": [],
            "level": 0,
            "rating": "0+",
            "risk_detected": False,
            "evidence": [],
            "matched_terms": {},
            "confidence": {"category": 1.0, "level": 1.0, "rating": 1.0},
            "label_source": "pseudo_safe_rule",
            "needs_human_review": True,
        })

    aggregation = aggregate_project_rating(scene_level_items)
    document = {
        "id": script_path.stem,
        "file": script_path.name,
        "expected_project_rating": expected_project_rating,
        "pseudo_project_rating": aggregation["rating"],
        "technical_max_rating": aggregation["technical_max_rating"],
        "aggregation": aggregation,
        "scene_count": len(parsed.get("scenes", [])),
        "total_elements": total_elements,
        "pseudo_rows": len(rows),
        "risky_rows": len(risky_candidates),
        "safe_rows": min(len(safe_candidates), safe_per_document),
        "source": "real_text_pseudo",
    }
    return document, rows


def build_recommendation_example(row: dict) -> dict:
    context = build_recommendation_context(
        item_id=row["id"],
        text=row["text"],
        category=row["category"],
        category_label=category_label(row["category"]),
        secondary_categories=row.get("secondary_categories", []),
        level=row["level"],
        level_label=level_label(row["level"]),
        rating=row["rating"],
        target_rating=lower_rating(row["rating"]),
        evidence=row.get("evidence", []),
        confidence=row.get("confidence", {}),
        needs_review=True,
        element_type=row.get("element_type", "action"),
        character=row.get("character", ""),
    )
    fallback_text, fallback_payload = fallback_parts(
        text=row["text"],
        category=row["category"],
        category_label=context["category_label"],
        level=row["level"],
        target_rating=context["target_rating"],
        evidence=row.get("evidence", []),
        element_type=row.get("element_type", "action"),
        character=row.get("character", ""),
        llm_error=None,
    )
    return {
        "id": row["id"],
        "source_document": row["source_document"],
        "input": {
            "text": row["text"],
            "category": row["category"],
            "category_label": context["category_label"],
            "secondary_categories": row.get("secondary_categories", []),
            "level": row["level"],
            "level_label": context["level_label"],
            "rating": row["rating"],
            "target_rating": context["target_rating"],
            "evidence": row.get("evidence", []),
            "legal_context": context["legal_context"],
        },
        "expected": {
            **fallback_payload,
            "text": fallback_text,
        },
        "label_source": "deterministic_policy_pseudo",
        "needs_human_review": True,
    }


def select_balanced_rows(rows: list[dict], target_rows: int, rng: random.Random) -> list[dict]:
    buckets = defaultdict(list)
    for row in rows:
        buckets[row["category"]].append(row)
    for bucket in buckets.values():
        rng.shuffle(bucket)

    selected = []
    categories = sorted(buckets)
    while len(selected) < target_rows and any(buckets.values()):
        for category in categories:
            if buckets[category] and len(selected) < target_rows:
                selected.append(buckets[category].pop())
    rng.shuffle(selected)
    return selected


def split_rows(rows: list[dict], validation_ratio: float, test_ratio: float) -> dict[str, list[dict]]:
    validation_count = int(len(rows) * validation_ratio)
    test_count = int(len(rows) * test_ratio)
    train_count = len(rows) - validation_count - test_count
    return {
        "train": rows[:train_count],
        "validation": rows[train_count:train_count + validation_count],
        "test": rows[train_count + validation_count:],
    }


def build_report(document_rows: list[dict], selected_rows: list[dict], splits: dict, recommendation_splits: dict, args) -> dict:
    rating_counts = Counter(row["rating"] for row in selected_rows)
    category_counts = Counter(row["category"] for row in selected_rows)
    project_matches = sum(
        1 for row in document_rows
        if row["expected_project_rating"] and row["expected_project_rating"] == row["pseudo_project_rating"]
    )
    project_total = sum(1 for row in document_rows if row["expected_project_rating"])
    return {
        "dataset_type": "real_text_pseudo",
        "warning": "Pseudo-labeled from local scripts and current model/rules. Treat as silver until human-reviewed.",
        "input_dir": str(args.input_dir),
        "target_rows": args.target_rows,
        "selected_rows": len(selected_rows),
        "rubert_splits": {name: len(rows) for name, rows in splits.items()},
        "recommendation_splits": {name: len(rows) for name, rows in recommendation_splits.items()},
        "category_counts": dict(category_counts),
        "rating_counts": dict(rating_counts),
        "project_rating_match_rate": round(project_matches / project_total, 4) if project_total else None,
        "documents": document_rows,
    }


def make_row_id(document: str, scene_id, element_index: int) -> str:
    safe_name = Path(document).stem.lower().replace(" ", "_")
    return f"real-text-{safe_name}-{scene_id}-{element_index}"


def rating_index(rating: str) -> int:
    return {"0+": 0, "6+": 1, "12+": 2, "16+": 3, "18+": 4}.get(rating, 0)


def lower_rating(rating: str) -> str:
    ratings = ["0+", "6+", "12+", "16+", "18+"]
    index = max(0, rating_index(rating) - 1)
    return ratings[index]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build pseudo-labeled datasets from local Real_Text scripts.")
    parser.add_argument("--input-dir", type=Path, default=Path("doc/Real_Text"))
    parser.add_argument("--output-dir", type=Path, default=Path("llm/datasets/silver/real_text_pseudo"))
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--target-rows", type=int, default=500)
    parser.add_argument("--safe-per-document", type=int, default=20)
    parser.add_argument("--validation-ratio", type=float, default=0.15)
    parser.add_argument("--test-ratio", type=float, default=0.15)
    parser.add_argument("--rubert-batch-size", type=int, default=16)
    parser.add_argument("--max-len", type=int, default=256)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


if __name__ == "__main__":
    main()
