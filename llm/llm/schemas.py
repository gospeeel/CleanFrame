from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RecommendationPayload(BaseModel):
    summary: str | None = None
    explanation: str
    risk_factors: list[str]
    rewrite_suggestions: list[dict[str, str] | str]
    self_check_passed: bool | None = None
    uncertainty_note: str | None = None


class RecommendationSummary(BaseModel):
    summary: str
    rewrite_suggestions: list[dict[str, str]]
    fallback_used: bool = False
    self_check_passed: bool = True


class SuspiciousScene(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    text: str = Field(alias="текст_сцены")
    risk_detected: bool = True
    rating: str = Field(alias="рейтинг")
    target_rating: str | None = None
    rating_index: int = Field(alias="индекс_рейтинга")
    category: str = Field(alias="категория")
    category_id: str | None = None
    category_label: str | None = None
    primary_category: str | None = None
    secondary_categories: list[str] = Field(default_factory=list)
    category_labels: dict[str, str] = Field(default_factory=dict)
    level: int = Field(alias="уровень")
    level_label: str | None = None
    confidence: dict[str, float] | None = None
    category_scores: dict[str, float] | None = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    evidence_meta: dict[str, Any] | None = None
    matched_terms: list[str] = Field(default_factory=list)
    level_scores: dict[str, float] | None = None
    rating_scores: dict[str, float] | None = None
    needs_review: bool = False
    recommendation: str = Field(alias="рекомендации_понижения")
    recommendation_structured: RecommendationSummary | None = Field(default=None, alias="recommendation")
    llm_recommendation: RecommendationPayload | None = None
    fallback_used: bool = False
    fallback_reason: str | None = None
    llm_error: str | None = None
    legal_context: list[dict[str, Any]] | None = None
    policy_basis: str | None = None


class RatingStats(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    total_elements: int | None = Field(default=None, alias="всего_элементов")
    total_suspicious: int | None = Field(default=None, alias="всего_подозрительных")
    processed_suspicious: int | None = Field(default=None, alias="обработано_подозрительных")
    max_rating_scenes: int | None = Field(default=None, alias="сцен_с_максимальным_рейтингом")
    review_scenes: int | None = Field(default=None, alias="сцен_требующих_проверки")
    max_rating: str | None = Field(default=None, alias="максимальный_рейтинг")
    processing_time: float | None = Field(default=None, alias="время_обработки")


class AnalysisResult(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    processed_scenes: list[SuspiciousScene] = Field(default_factory=list, alias="обработанные_сцены")
    max_rating_scenes: list[SuspiciousScene] = Field(default_factory=list, alias="сцены_с_максимальным_рейтингом")
    all_suspicious_scenes: list[SuspiciousScene] = Field(default_factory=list, alias="все_подозрительные_сцены")
    stats: RatingStats | None = Field(default=None, alias="статистика")


class Allm(BaseModel):
    detail: str
    result: AnalysisResult
