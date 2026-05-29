from __future__ import annotations

import re
from dataclasses import dataclass


CATEGORY_ALIASES = {
    "drugs_alcohol": "substance",
    "substance": "substance",
    "erotic": "sexual",
    "sexual": "sexual",
    "scary": "fear",
    "fear": "fear",
    "violence": "violence",
    "profanity": "profanity",
    "safe": "safe",
}

TAXONOMY_VERSION = "2026-05-28"

CATEGORY_LABELS = {
    "violence": "Насилие",
    "profanity": "Грубая лексика",
    "substance": "Алкоголь, табак и вещества",
    "sexual": "Интимный контент",
    "fear": "Пугающие сцены",
    "safe": "Без риска",
}

LEVEL_LABELS = {
    0: "нет риска",
    1: "слабый сигнал",
    2: "умеренный риск",
    3: "выраженный риск",
    4: "высокий риск",
}

CATEGORY_PRIORITY = {
    "violence": 50,
    "profanity": 45,
    "substance": 40,
    "sexual": 35,
    "fear": 30,
    "safe": 0,
}

CURATED_TERMS = {
    "violence": {
        "драка": 3.0,
        "потасовка": 3.0,
        "удар": 2.5,
        "ударить": 2.5,
        "ударил": 2.5,
        "ударила": 2.5,
        "удары": 2.5,
        "бьет": 2.5,
        "избить": 3.5,
        "избивает": 3.5,
        "хватает": 2.0,
        "схватил": 2.0,
        "падает": 1.5,
        "упал": 1.5,
        "рана": 3.0,
        "кровь": 3.5,
        "нож": 3.0,
        "пистолет": 3.0,
        "оружие": 3.0,
        "труп": 4.0,
        "убить": 4.0,
        "застрелить": 4.0,
    },
    "fear": {
        "страшно": 2.0,
        "страх": 2.0,
        "ужас": 2.5,
        "паника": 2.5,
        "панике": 2.5,
        "в панике": 2.5,
        "тень": 1.5,
        "тени": 1.5,
        "преследует": 2.5,
        "пугает": 2.0,
        "пугающий": 2.0,
        "жуткий": 2.5,
        "кошмар": 2.5,
        "призрак": 3.0,
        "зомби": 3.0,
        "маньяк": 3.0,
    },
    "profanity": {
        "блядь": 4.0,
        "хуй": 4.0,
        "пизда": 4.0,
        "ебать": 4.0,
        "сука": 2.5,
        "нахрен": 1.5,
        "бля": 2.0,
        "хер": 1.5,
    },
    "substance": {
        "алкоголь": 2.0,
        "водка": 2.0,
        "пиво": 1.5,
        "табак": 2.0,
        "сигарета": 2.0,
        "сигарету": 2.0,
        "наркотик": 3.5,
        "героин": 4.0,
        "косяк": 3.0,
        "спайс": 4.0,
    },
    "sexual": {
        "секс": 3.0,
        "поцелуй": 1.0,
        "поцелуем": 1.0,
        "страсть": 1.0,
        "голая": 2.5,
        "интим": 2.5,
        "эротический": 3.0,
        "сексуальный": 3.0,
    },
}

SAFE_CONTEXT_PATTERNS = {
    "violence": [
        "ударил по мячу",
        "ударила по мячу",
        "удар по мячу",
        "ударил по клавиш",
        "ударила по клавиш",
        "нож для торта",
        "ножом для торта",
    ],
    "fear": [
        "страшно опоздать",
        "страшно ошибиться",
        "страшно подумать",
    ],
    "substance": [
        "героиня",
        "героини",
        "героиню",
        "героиней",
    ],
    "sexual": [
        "страсть к музыке",
        "страсть к работе",
        "страсть к театру",
        "поцелуй в щеку от бабушки",
        "поцелуй в щеку от мамы",
    ],
}

EVIDENCE_REASONS = {
    "violence": "физический конфликт или последствия насилия",
    "profanity": "грубая или ненормативная лексика",
    "substance": "алкоголь, табак, наркотики или употребление веществ",
    "sexual": "интимный или сексуализированный контент",
    "fear": "пугающая атмосфера или выраженный страх",
    "safe": "явные факторы риска не найдены",
}


@dataclass(frozen=True)
class CategoryPresentation:
    id: str
    label: str


def normalize_category(category: str | None) -> str:
    if not category:
        return "safe"
    return CATEGORY_ALIASES.get(str(category), str(category))


def category_label(category: str | None) -> str:
    normalized = normalize_category(category)
    return CATEGORY_LABELS.get(normalized, str(category or "Без риска"))


def level_label(level: int | None) -> str:
    if level is None:
        return "уровень не определён"
    return LEVEL_LABELS.get(int(level), f"уровень {level}")


def dedupe_categories(categories: list[str]) -> list[str]:
    result = []
    seen = set()
    for category in categories:
        normalized = normalize_category(category)
        if normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def score_curated_terms(text: str) -> tuple[dict[str, float], dict[str, list[str]]]:
    lowered = text.lower()
    scores = {category: 0.0 for category in CURATED_TERMS}
    matches = {category: [] for category in CURATED_TERMS}

    for category, terms in CURATED_TERMS.items():
        for term, weight in terms.items():
            if _term_found(lowered, term):
                scores[category] += weight
                matches[category].append(term)

    for category, patterns in SAFE_CONTEXT_PATTERNS.items():
        if any(pattern in lowered for pattern in patterns):
            scores[category] = 0.0
            matches[category] = []

    return scores, matches


def safe_context_categories(text: str) -> set[str]:
    lowered = text.lower()
    return {
        category
        for category, patterns in SAFE_CONTEXT_PATTERNS.items()
        if any(pattern in lowered for pattern in patterns)
    }


def _term_found(text: str, term: str) -> bool:
    escaped = re.escape(term.lower())
    if " " in term:
        return re.search(rf"(?<!\w){escaped}(?!\w)", text) is not None
    return re.search(rf"(?<!\w){escaped}\w*(?!\w)", text) is not None


def evidence_items(text: str, matched_terms: dict[str, list[str]]) -> list[dict[str, str]]:
    items = []
    lowered = text.lower()
    for category, terms in matched_terms.items():
        normalized = normalize_category(category)
        for term in terms:
            snippet = _evidence_snippet(text, lowered, term)
            items.append({
                "category": normalized,
                "category_label": category_label(normalized),
                "text": snippet or term,
                "matched_term": term,
                "reason": EVIDENCE_REASONS.get(normalized, "потенциальный фактор риска"),
            })
    return items


def _evidence_snippet(original: str, lowered: str, term: str) -> str:
    match = re.search(rf"(?<!\w){re.escape(term.lower())}\w*(?!\w)", lowered)
    if not match:
        return term

    start = max(0, match.start() - 32)
    end = min(len(original), match.end() + 32)
    return original[start:end].strip(" .,;:!?")


def primary_category_from_evidence(predicted_category: str, natasha: dict) -> tuple[str, list[str]]:
    predicted = normalize_category(predicted_category)
    flags = natasha.get("flags", {}) if isinstance(natasha, dict) else {}
    scores = natasha.get("category_scores", {}) if isinstance(natasha, dict) else {}

    active = [
        normalize_category(category)
        for category, is_active in flags.items()
        if is_active
    ]
    active = dedupe_categories(active)
    if not active:
        return predicted, []

    def sort_key(category: str) -> tuple[float, int]:
        score = float(scores.get(category, 0.0))
        return score, CATEGORY_PRIORITY.get(category, 0)

    primary = max(active, key=sort_key)
    if predicted in active and float(scores.get(predicted, 0.0)) >= float(scores.get(primary, 0.0)):
        primary = predicted

    secondary = [category for category in active if category != primary]
    return primary, secondary
