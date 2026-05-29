from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import requests

from llm.llm_client import DEFAULT_OLLAMA_BASE_URL, DEFAULT_OLLAMA_MODEL


CATEGORIES = ["violence", "fear", "profanity", "substance", "sexual", "safe"]
DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "datasets" / "golden" / "candidates.generated.jsonl"

SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "expected_primary_category": {"type": "string"},
                    "expected_secondary_categories": {"type": "array", "items": {"type": "string"}},
                    "expected_level": {"type": "integer"},
                    "expected_rating": {"type": "string"},
                    "expected_risk_detected": {"type": "boolean"},
                    "expected_evidence": {"type": "array", "items": {"type": "string"}},
                    "notes": {"type": "string"},
                },
                "required": [
                    "text",
                    "expected_primary_category",
                    "expected_secondary_categories",
                    "expected_level",
                    "expected_rating",
                    "expected_risk_detected",
                    "expected_evidence",
                    "notes",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["items"],
    "additionalProperties": False,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate human-review golden dataset candidates.")
    parser.add_argument("--count-per-category", type=int, default=5)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--use-ollama", action="store_true")
    args = parser.parse_args()

    rows = []
    for category in CATEGORIES:
        items = generate_with_ollama(category, args.count_per_category) if args.use_ollama else []
        if not items:
            items = fallback_items(category, args.count_per_category)
        for index, item in enumerate(items, start=1):
            rows.append({
                "id": f"candidate-{category}-{index:03d}",
                **item,
                "source": "qwen_candidate" if args.use_ollama else "template_candidate",
                "review_status": "needs_human_review",
            })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(rows)} candidates to {args.output}")


def generate_with_ollama(category: str, count: int) -> list[dict[str, Any]]:
    base_url = os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).rstrip("/")
    model = os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
    prompt = f"""
Сгенерируй {count} коротких русских сценарных фрагментов для golden dataset категории {category}.
Каждый фрагмент должен быть 1-2 предложения, без копирования известных фильмов или чужих сценариев.
Верни JSON по схеме. Для safe используй false positive cases.
Рейтинги: level 0 -> 0+, 1 -> 6+, 2 -> 12+, 3 -> 16+, 4 -> 18+.
""".strip()
    try:
        response = requests.post(
            f"{base_url}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "Ты генерируешь только валидный JSON для ручной проверки датасета."},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "format": SCHEMA,
                "options": {"temperature": 0.4},
            },
            timeout=60,
        )
        response.raise_for_status()
        payload = json.loads(response.json()["message"]["content"])
        return payload.get("items", [])[:count]
    except Exception:
        return []


def fallback_items(category: str, count: int) -> list[dict[str, Any]]:
    templates = {
        "violence": [
            ("Герой хватает соперника за куртку, слышен удар о дверь.", 2, ["хватает", "удар"]),
            ("На полу видна кровь, охранник держится за рану.", 4, ["кровь", "рана"]),
            ("В драке персонаж падает на пол и тяжело дышит.", 2, ["драка", "падает"]),
        ],
        "fear": [
            ("Марине страшно: в конце коридора мелькает тень.", 2, ["страшно", "тень"]),
            ("Жуткий силуэт преследует героя до закрытой двери.", 3, ["жуткий", "преследует"]),
            ("В кошмаре появляется призрак, ребёнок просыпается в ужасе.", 3, ["кошмар", "призрак", "ужас"]),
        ],
        "profanity": [
            ("Персонаж тихо говорит: «нахрен всё это».", 1, ["нахрен"]),
            ("В споре звучит грубое «бля, хватит».", 2, ["бля"]),
            ("Герой выкрикивает обсценное слово «блядь».", 3, ["блядь"]),
        ],
        "substance": [
            ("На столе стоит пиво, взрослые спорят о последствиях вечеринки.", 1, ["пиво"]),
            ("Персонажу предлагают наркотик, но он отказывается.", 3, ["наркотик"]),
            ("На столе дилера лежат героин и спайс.", 4, ["героин", "спайс"]),
        ],
        "sexual": [
            ("Герои обмениваются коротким поцелуем и смущённо отходят.", 1, ["поцелуй"]),
            ("Диалог намекает на интим, но сцена остаётся за кадром.", 2, ["интим"]),
            ("Персонажи прямо обсуждают секс без метафор.", 4, ["секс"]),
        ],
        "safe": [
            ("Олег ударил по мячу, и команда продолжила игру.", 0, []),
            ("Ане страшно опоздать на поезд, поэтому она ускоряет шаг.", 0, []),
            ("У героя настоящая страсть к музыке и старым пластинкам.", 0, []),
        ],
    }
    items = []
    source = templates[category]
    for index in range(count):
        text, level, evidence = source[index % len(source)]
        items.append({
            "text": text,
            "expected_primary_category": category if category != "safe" else "safe",
            "expected_secondary_categories": [],
            "expected_level": level,
            "expected_rating": rating_for(level),
            "expected_risk_detected": category != "safe",
            "expected_evidence": evidence,
            "notes": "Синтетический кандидат, требуется ручная проверка перед переносом в regression.jsonl.",
        })
    return items


def rating_for(level: int) -> str:
    return ["0+", "6+", "12+", "16+", "18+"][level]


if __name__ == "__main__":
    main()
