RATING_ORDER = ["0+", "6+", "12+", "16+", "18+"]
RATING_TO_ID = {rating: index for index, rating in enumerate(RATING_ORDER)}
ID_TO_RATING = {index: rating for rating, index in RATING_TO_ID.items()}

TERM_LEVELS = {
    "violence": {
        4: {"кровь", "рана", "труп", "убить", "застрелить"},
        3: {"нож", "пистолет", "оружие"},
        2: {"драка", "потасовка", "удар", "ударить", "ударил", "ударила", "удары", "бьет", "избить", "избивает", "хватает", "схватил", "падает", "упал"},
    },
    "fear": {
        4: {"зомби"},
        3: {"преследует", "жуткий", "кошмар", "призрак", "ужас", "паника", "панике", "в панике", "маньяк"},
        2: {"страшно", "страх", "тень", "тени", "пугает", "пугающий"},
    },
    "profanity": {
        4: {"хуй", "пизда", "ебать"},
        3: {"блядь", "сука"},
        2: {"бля"},
        1: {"нахрен", "хер"},
    },
    "substance": {
        4: {"героин", "спайс"},
        3: {"наркотик", "косяк"},
        2: {"табак", "сигарета", "сигарету", "водка", "алкоголь"},
        1: {"пиво"},
    },
    "sexual": {
        4: {"секс"},
        3: {"эротический", "сексуальный"},
        2: {"голая", "интим"},
        1: {"поцелуй", "поцелуем", "страсть"},
    },
}


def get_rating_index(rating: str) -> int:
    return RATING_TO_ID.get(rating, 0)


def max_rating(ratings: list[str]) -> str:
    if not ratings:
        return "0+"
    return max(ratings, key=get_rating_index)


def calculate_rating(category: str, level: int) -> str:
    from llm.taxonomy import normalize_category

    category = normalize_category(category)
    if category == "safe" or level <= 0:
        return "0+"

    rules = {
        "sexual": {1: "6+", 2: "12+", 3: "16+", 4: "18+"},
        "erotic": {1: "6+", 2: "12+", 3: "16+", 4: "18+"},
        "violence": {1: "6+", 2: "12+", 3: "16+", 4: "18+"},
        "profanity": {1: "6+", 2: "12+", 3: "16+", 4: "18+"},
        "drugs_alcohol": {1: "6+", 2: "12+", 3: "16+", 4: "18+"},
        "substance": {1: "6+", 2: "12+", 3: "16+", 4: "18+"},
        "scary": {1: "6+", 2: "12+", 3: "16+", 4: "18+"},
        "fear": {1: "6+", 2: "12+", 3: "16+", 4: "18+"},
    }
    return rules.get(category, {}).get(level, "6+")


def calibrate_level_from_evidence(category: str, model_level: int, matched_terms: dict[str, list[str]]) -> int:
    from llm.taxonomy import normalize_category

    normalized = normalize_category(category)
    terms = {
        str(term).lower()
        for key, values in (matched_terms or {}).items()
        if normalize_category(key) == normalized
        for term in values
    }
    if not terms:
        return model_level

    evidence_level = 0
    for level, level_terms in TERM_LEVELS.get(normalized, {}).items():
        if terms & level_terms:
            evidence_level = max(evidence_level, level)

    if normalized == "violence" and {"кровь", "рана"}.issubset(terms):
        evidence_level = max(evidence_level, 4)
    if normalized == "profanity" and len(terms & TERM_LEVELS["profanity"][4]) >= 2:
        evidence_level = max(evidence_level, 4)
    if normalized == "fear" and "зомби" in terms:
        evidence_level = max(evidence_level, 4)
    if normalized == "substance" and terms & {"героин", "спайс"}:
        evidence_level = max(evidence_level, 4)

    if evidence_level <= 0:
        return model_level
    return evidence_level


def aggregate_project_rating(items: list[dict]) -> dict:
    if not items:
        return {
            "rating": "0+",
            "rating_index": 0,
            "technical_max_rating": "0+",
            "technical_max_index": 0,
            "policy": "aggregate-v1",
            "reason": "no_risks",
            "counts": {rating: 0 for rating in RATING_ORDER},
        }

    counts = {rating: 0 for rating in RATING_ORDER}
    reliable_counts = {rating: 0 for rating in RATING_ORDER}
    category_counts: dict[str, int] = {}
    technical_max_index = 0

    for item in items:
        rating = item.get("rating") or item.get("рейтинг") or "0+"
        rating_index = get_rating_index(rating)
        technical_max_index = max(technical_max_index, rating_index)
        counts[RATING_ORDER[rating_index]] += 1
        category = item.get("category_id") or item.get("primary_category") or item.get("category")
        if category and category != "safe":
            category_counts[str(category)] = category_counts.get(str(category), 0) + 1

        confidence = item.get("confidence") if isinstance(item.get("confidence"), dict) else {}
        rating_confidence = float(confidence.get("rating", 0.0) or 0.0)
        level_confidence = float(confidence.get("level", 0.0) or 0.0)
        evidence_count = len(item.get("evidence") or [])
        reliable = rating_confidence >= 0.60 and level_confidence >= 0.60 and evidence_count > 0
        if reliable:
            reliable_counts[RATING_ORDER[rating_index]] += 1

    severe_reliable = reliable_counts["18+"]
    strong_reliable = reliable_counts["16+"] + reliable_counts["18+"]
    adult_signal_count = (
        category_counts.get("profanity", 0)
        + category_counts.get("substance", 0)
        + category_counts.get("sexual", 0)
    )
    category_diversity = sum(1 for count in category_counts.values() if count > 0)

    if (
        category_counts.get("profanity", 0) >= 25
        or (category_counts.get("sexual", 0) >= 4 and category_counts.get("fear", 0) >= 4)
        or (category_counts.get("substance", 0) >= 8 and category_diversity >= 3)
        or (adult_signal_count >= 20 and category_diversity >= 4)
    ):
        final_index = 4
        reason = "document_level_adult_pattern"
    elif severe_reliable >= 2:
        if (
            adult_signal_count >= 5
            or category_counts.get("sexual", 0) >= 2
            or category_counts.get("profanity", 0) >= 2
            or category_counts.get("substance", 0) >= 5
        ):
            final_index = 4
            reason = "repeated_reliable_18_plus"
        else:
            final_index = 3
            reason = "repeated_reliable_18_plus_action_context"
    elif strong_reliable >= 3:
        if (
            category_counts.get("violence", 0) >= 10
            and category_counts.get("profanity", 0) == 0
            and category_counts.get("sexual", 0) <= 1
            and category_counts.get("substance", 0) <= 2
            and adult_signal_count < 5
        ):
            final_index = 2
            reason = "action_violence_moderated_to_12_plus"
        else:
            final_index = 3
            reason = "repeated_reliable_16_plus"
    elif category_counts.get("violence", 0) >= 10 and (
        category_counts.get("substance", 0) >= 3 or category_counts.get("profanity", 0) >= 1
    ):
        final_index = 3
        reason = "document_level_16_plus_pattern"
    elif counts["18+"] >= 4 or (counts["18+"] + counts["16+"]) >= 8:
        final_index = 3
        reason = "many_unreliable_high_risk_signals"
    elif counts["12+"] or counts["16+"] or counts["18+"]:
        final_index = 2
        reason = "dominant_moderate_risk"
    elif counts["6+"]:
        final_index = 1
        reason = "mild_risk"
    else:
        final_index = 0
        reason = "no_rating_signal"

    return {
        "rating": RATING_ORDER[final_index],
        "rating_index": final_index,
        "technical_max_rating": RATING_ORDER[technical_max_index],
        "technical_max_index": technical_max_index,
        "policy": "aggregate-v1",
        "reason": reason,
        "counts": counts,
        "reliable_counts": reliable_counts,
        "category_counts": category_counts,
    }
