import json
import re
from functools import lru_cache
from typing import Any

from llm.paths import LLM_DIR
from llm.legal.policy import get_policy_entry
from llm.taxonomy import normalize_category


POLICY_PATH = LLM_DIR / "legal_knowledge" / "policy.jsonl"


@lru_cache(maxsize=1)
def load_policy_documents() -> list[dict]:
    if not POLICY_PATH.exists():
        return []

    rows = []
    with POLICY_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def retrieve_legal_context(
    category: str,
    level: int,
    rating: str,
    text: str,
    evidence: list[dict[str, Any]] | None = None,
    limit: int = 3,
) -> list[dict]:
    docs = load_policy_documents()
    normalized_category = normalize_category(category)
    evidence_terms = _evidence_terms(evidence, text)
    scored = [
        (
            doc,
            _score_doc(
                doc=doc,
                category=normalized_category,
                level=level,
                rating=rating,
                evidence_terms=evidence_terms,
            ),
        )
        for doc in docs
    ]
    ranked = sorted(scored, key=lambda item: item[1], reverse=True)
    selected = [(doc, score) for doc, score in ranked if score > 0][:limit]

    if not selected:
        entry = get_policy_entry(normalized_category)
        selected = [({
            "id": f"policy-{normalized_category}",
            "category": normalized_category,
            "text": entry["basis"],
            "retrieval_reason": "fallback_policy_basis",
        }, 0.0)]

    return [
        {
            **doc,
            "level": level,
            "rating": rating,
            "retrieval_score": round(score, 3),
            "retrieval_reason": _retrieval_reason(
                doc=doc,
                category=normalized_category,
                level=level,
                rating=rating,
                evidence_terms=evidence_terms,
            ),
            "matched_evidence_terms": sorted(
                _doc_terms(doc).intersection(evidence_terms)
            ),
        }
        for doc, score in selected
    ]


def _retrieval_reason(
    doc: dict,
    category: str,
    level: int,
    rating: str,
    evidence_terms: set[str],
) -> str:
    reasons = []
    if normalize_category(doc.get("category")) == category:
        reasons.append("category")
    if _level_in_doc_range(doc, level):
        reasons.append("level")
    if doc.get("rating") == rating:
        reasons.append("rating")
    if _doc_terms(doc).intersection(evidence_terms):
        reasons.append("evidence")
    return "+".join(reasons) or doc.get("retrieval_reason") or "fallback"


def _score_doc(
    doc: dict,
    category: str,
    level: int,
    rating: str,
    evidence_terms: set[str],
) -> float:
    if normalize_category(doc.get("category")) != category:
        return 0.0

    score = 10.0

    if _level_in_doc_range(doc, level):
        score += 5.0
    else:
        score -= _level_distance_penalty(doc, level)

    if doc.get("rating") == rating:
        score += 4.0
    elif doc.get("rating"):
        score -= 1.0

    overlap = _doc_terms(doc).intersection(evidence_terms)
    score += min(len(overlap), 6) * 2.0
    return max(score, 0.0)


def _level_in_doc_range(doc: dict, level: int) -> bool:
    min_level = doc.get("min_level")
    max_level = doc.get("max_level")
    if not isinstance(min_level, int) or not isinstance(max_level, int):
        return False
    return min_level <= level <= max_level


def _level_distance_penalty(doc: dict, level: int) -> float:
    min_level = doc.get("min_level")
    max_level = doc.get("max_level")
    if not isinstance(min_level, int) or not isinstance(max_level, int):
        return 0.0
    if level < min_level:
        return float(min_level - level) * 2.0
    if level > max_level:
        return float(level - max_level) * 2.0
    return 0.0


def _evidence_terms(evidence: list[dict[str, Any]] | None, text: str) -> set[str]:
    terms = set()
    for item in evidence or []:
        matched = item.get("matched_term")
        if isinstance(matched, str) and matched.strip():
            terms.add(matched.lower().strip())
        snippet = item.get("text")
        if isinstance(snippet, str):
            terms.update(_tokens(snippet))
    if not terms:
        terms.update(_tokens(text))
    return terms


def _doc_terms(doc: dict) -> set[str]:
    terms = set()
    for key in ("evidence_terms", "keywords"):
        values = doc.get(key)
        if isinstance(values, list):
            terms.update(str(value).lower() for value in values)
    text = doc.get("text")
    if isinstance(text, str):
        terms.update(_tokens(text))
    return terms


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[а-яёa-z0-9_-]{3,}", text.lower())
        if token
    }
