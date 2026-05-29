from dataclasses import dataclass


@dataclass(frozen=True)
class RiskPolicy:
    category_confidence_threshold: float = 0.70
    level_confidence_threshold: float = 0.70
    high_risk_min_level: int = 3
    always_review_ratings: tuple[str, ...] = ("16+", "18+")


DEFAULT_RISK_POLICY = RiskPolicy()


def needs_human_review(prediction: dict, policy: RiskPolicy = DEFAULT_RISK_POLICY) -> bool:
    if prediction.get("category") == "safe":
        return False

    if prediction.get("rating") in policy.always_review_ratings:
        return True

    if int(prediction.get("level", 0)) >= policy.high_risk_min_level:
        return True

    if float(prediction.get("category_confidence", 0.0)) < policy.category_confidence_threshold:
        return True

    if float(prediction.get("level_confidence", 0.0)) < policy.level_confidence_threshold:
        return True

    return False
