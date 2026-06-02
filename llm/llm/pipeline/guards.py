from __future__ import annotations

from copy import deepcopy

from llm.rating import calculate_rating
from llm.taxonomy import normalize_category, primary_category_from_evidence


def apply_evidence_guard(prediction: dict, natasha: dict, text: str) -> tuple[dict, list[str]]:
    """Reduce unsupported model-only risks before rating/recommendation output.

    Rule evidence is treated as the primary source for category grounding. RuBERT can
    still classify risk, but high-risk categories without matching evidence are
    downgraded to safe unless the text carries explicit category terms.
    """
    guarded = deepcopy(prediction)
    reasons: list[str] = []
    matched_terms = natasha.get("matched_terms", {}) if isinstance(natasha, dict) else {}
    category, secondary = primary_category_from_evidence(guarded.get("category", "safe"), natasha)
    category = normalize_category(category)

    if category != "safe" and not matched_terms_for(category, matched_terms):
        if should_suppress_model_only_category(category, guarded, text):
            guarded["category"] = "safe"
            guarded["level"] = 0
            guarded["rating"] = "0+"
            guarded["category_confidence"] = min(float(guarded.get("category_confidence", 0.0) or 0.0), 0.49)
            guarded["level_confidence"] = min(float(guarded.get("level_confidence", 0.0) or 0.0), 0.49)
            guarded["rating_confidence"] = min(float(guarded.get("rating_confidence", 0.0) or 0.0), 0.49)
            reasons.append(f"model_only_{category}_without_evidence")
            return guarded, reasons

    if guarded.get("category") != category:
        guarded["category"] = category
        reasons.append("category_replaced_by_rule_evidence")

    if category == "safe":
        guarded["level"] = 0
        guarded["rating"] = "0+"
    elif "rating" not in guarded or guarded.get("rating") == "0+":
        guarded["rating"] = calculate_rating(category, int(guarded.get("level") or 1))

    return guarded, reasons


def matched_terms_for(category: str, matched_terms: dict[str, list[str]]) -> list[str]:
    normalized = normalize_category(category)
    return [
        str(term).lower()
        for key, terms in (matched_terms or {}).items()
        if normalize_category(key) == normalized
        for term in terms
    ]


def should_suppress_model_only_category(category: str, prediction: dict, text: str) -> bool:
    lowered = text.lower()
    confidence = float(prediction.get("category_confidence", 0.0) or 0.0)
    level = int(prediction.get("level") or 0)

    if category == "sexual":
        explicit_terms = (
            "секс",
            "сексу",
            "эрот",
            "интим",
            "голая",
            "голый",
            "обнаж",
            "постел",
            "поцел",
        )
        neutral_terms = (
            "машина",
            "двигател",
            "механизм",
            "система",
            "реагирует",
            "усили",
            "управлен",
            "рычаг",
            "педаль",
            "руль",
        )
        if not any(term in lowered for term in explicit_terms):
            return True
        if any(term in lowered for term in neutral_terms) and confidence < 0.95:
            return True

    if level >= 3 and confidence < 0.85:
        return True

    return confidence < 0.75
