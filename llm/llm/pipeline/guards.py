from __future__ import annotations

from copy import deepcopy

from llm.rating import calculate_rating
from llm.taxonomy import normalize_category, primary_category_from_evidence


STRONG_EVIDENCE_TERMS = {
    "violence": {
        "убил",
        "убить",
        "застрел",
        "нож",
        "пистолет",
        "оружие",
        "избил",
        "душит",
        "кровь",
        "рана",
        "труп",
    },
    "fear": {"зомби", "маньяк", "призрак", "кошмар", "преследует"},
    "sexual": {"секс", "сексу", "эрот", "обнаж", "постел", "интим"},
    "substance": {"наркотик", "героин", "спайс", "дилер", "косяк"},
    "profanity": {"блядь", "сука", "хуй", "пизд", "еба"},
}


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

    suppression_reason = safe_context_suppression_reason(category, text, matched_terms)
    if suppression_reason and not has_danger_evidence(category, matched_terms, suppression_reason):
        guarded["category"] = "safe"
        guarded["level"] = 0
        guarded["rating"] = "0+"
        guarded["category_confidence"] = min(float(guarded.get("category_confidence", 0.0) or 0.0), 0.49)
        guarded["level_confidence"] = min(float(guarded.get("level_confidence", 0.0) or 0.0), 0.49)
        guarded["rating_confidence"] = min(float(guarded.get("rating_confidence", 0.0) or 0.0), 0.49)
        reasons.append(suppression_reason)
        return guarded, reasons

    if category != "safe" and not matched_terms_for(category, matched_terms):
        if should_suppress_model_only_category(category, guarded, text):
            guarded["category"] = "safe"
            guarded["level"] = 0
            guarded["rating"] = "0+"
            guarded["category_confidence"] = min(float(guarded.get("category_confidence", 0.0) or 0.0), 0.49)
            guarded["level_confidence"] = min(float(guarded.get("level_confidence", 0.0) or 0.0), 0.49)
            guarded["rating_confidence"] = min(float(guarded.get("rating_confidence", 0.0) or 0.0), 0.49)
            reasons.append("model_only_high_risk_without_evidence")
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


def safe_context_suppression_reason(category: str, text: str, matched_terms: dict[str, list[str]]) -> str | None:
    normalized = normalize_category(category)
    lowered = " ".join(str(text or "").lower().split())

    if normalized == "violence":
        if any(pattern in lowered for pattern in (
            "кровь из носу",
            "глаза налиты кровью",
            "глаза залиты кровью",
            "горячая кровь",
            "анализ крови",
            "сдать кровь",
            "берёт кровь",
            "берет кровь",
        )):
            return "safe_context_idiom" if "кровь из носу" in lowered or "горячая кровь" in lowered else "medical_context"
        if "психологическая травма" in lowered or "травма детства" in lowered:
            return "medical_context"
        if any(term in lowered for term in ("тренировк", "матч", "мяч", "шайб", "ринг", "стадион", "фигурист", "спорт")):
            if any(term in lowered for term in ("ударил по мячу", "удар по мячу", "падает на лёд", "падает на лед", "упал на лёд", "упал на лед")):
                return "sport_context"

    if normalized == "fear":
        if any(pattern in lowered for pattern in (
            "страшно опоздать",
            "боится опоздать",
            "боится провалить",
            "страх экзамен",
            "переживает за экзамен",
        )):
            return "safe_context_idiom"

    if normalized == "sexual":
        if any(pattern in lowered for pattern in (
            "поцелуем и смущ",
            "держатся за руки",
            "на свидании",
            "романтическ",
            "тепло обнимаются",
        )):
            if not has_strong_evidence("sexual", matched_terms):
                return "romantic_non_sexual_context"

    if normalized == "substance":
        if any(pattern in lowered for pattern in (
            "вывеск",
            "музейн",
            "витрин",
            "проходят мимо",
            "старая пачка сигарет",
            "нарисована кружка пива",
        )):
            return "safe_context_idiom"

    return None


def has_strong_evidence(category: str, matched_terms: dict[str, list[str]]) -> bool:
    normalized = normalize_category(category)
    strong_terms = STRONG_EVIDENCE_TERMS.get(normalized, set())
    if not strong_terms:
        return False
    terms = matched_terms_for(normalized, matched_terms)
    return any(strong in term for term in terms for strong in strong_terms)


def has_danger_evidence(category: str, matched_terms: dict[str, list[str]], suppression_reason: str) -> bool:
    normalized = normalize_category(category)
    terms = matched_terms_for(normalized, matched_terms)
    if normalized == "violence" and suppression_reason in {"safe_context_idiom", "medical_context", "sport_context"}:
        danger_terms = STRONG_EVIDENCE_TERMS["violence"] - {"кровь", "рана"}
        return any(strong in term for term in terms for strong in danger_terms)
    return has_strong_evidence(normalized, matched_terms)
