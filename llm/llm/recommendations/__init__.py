"""Local policy-based recommendation layer."""

from llm.recommendations.service import generate_recommendation_package, generate_recommendation_packages_batch

__all__ = ["generate_recommendation_package", "generate_recommendation_packages_batch"]
