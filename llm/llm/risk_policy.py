from dataclasses import dataclass


@dataclass(frozen=True)
class RiskPolicy:
    category_confidence_threshold: float = 0.70
    level_confidence_threshold: float = 0.70
    high_risk_min_level: int = 3
    always_review_ratings: tuple[str, ...] = ("16+", "18+")


DEFAULT_RISK_POLICY = RiskPolicy()


SUPPRESSION_REASONS = {
    "safe_context_idiom",
    "medical_context",
    "sport_context",
    "romantic_non_sexual_context",
    "model_only_high_risk_without_evidence",
}


def needs_human_review(
    prediction: dict,
    policy: RiskPolicy = DEFAULT_RISK_POLICY,
    guard_reasons: list[str] | None = None,
) -> bool:
    if guard_reasons and any(reason in SUPPRESSION_REASONS for reason in guard_reasons):
        return False

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
