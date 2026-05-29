"""Legal policy and local retrieval helpers."""

from llm.legal.policy import fallback_recommendation, get_policy_entry
from llm.legal.retrieval import retrieve_legal_context

__all__ = ["fallback_recommendation", "get_policy_entry", "retrieve_legal_context"]
