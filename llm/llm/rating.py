RATING_ORDER = ["0+", "6+", "12+", "16+", "18+"]
RATING_TO_ID = {rating: index for index, rating in enumerate(RATING_ORDER)}
ID_TO_RATING = {index: rating for rating, index in RATING_TO_ID.items()}


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
