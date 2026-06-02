import json
import os
import time
from functools import lru_cache
from pathlib import Path

from llm.legal.policy import fallback_recommendation, get_policy_entry
from llm.legal.retrieval import retrieve_legal_context
from llm.llm_client import (
    BATCH_RECOMMENDATION_SCHEMA,
    FAST_BATCH_RECOMMENDATION_SCHEMA,
    GROUPED_RECOMMENDATION_SCHEMA,
    GROUPED_SUMMARY_RECOMMENDATION_SCHEMA,
    call_ollama_json,
    ollama_status,
)
from llm.taxonomy import category_label as get_category_label


DEFAULT_BATCH_SIZE = 6
DEFAULT_BATCH_NUM_PREDICT = 2200
DEFAULT_TIME_BUDGET_SECONDS = 120.0
DEFAULT_BATCH_TIMEOUT_SECONDS = 20.0
DEFAULT_EXAMPLES_LIMIT = 0
DEFAULT_EXAMPLES_MAX_ITEMS = 2500
DEFAULT_TEXT_MAX_CHARS = 650
DEFAULT_LEGAL_CONTEXT_MAX_CHARS = 220
DEFAULT_MODE = "fast"
DEFAULT_MAX_LLM_ITEMS = 0
DEFAULT_GROUP_MAX_ITEMS = 6
DEFAULT_GROUP_MAX_GROUPS = 24
DEFAULT_GROUP_NUM_PREDICT = 520
DEFAULT_GROUP_SUMMARY_NUM_PREDICT = 220


def recommendation_batch_size() -> int:
    value = int(os.getenv("LLM_RECOMMENDATION_BATCH_SIZE", str(DEFAULT_BATCH_SIZE)))
    return max(1, value)


def recommendation_batch_num_predict() -> int:
    value = int(os.getenv("LLM_RECOMMENDATION_BATCH_NUM_PREDICT", str(DEFAULT_BATCH_NUM_PREDICT)))
    return max(64, value)


def recommendation_time_budget_seconds() -> float:
    value = float(os.getenv("LLM_RECOMMENDATION_TIME_BUDGET_SECONDS", str(DEFAULT_TIME_BUDGET_SECONDS)))
    return max(0.0, value)


def recommendation_batch_timeout_seconds() -> float:
    value = float(os.getenv("LLM_RECOMMENDATION_BATCH_TIMEOUT_SECONDS", str(DEFAULT_BATCH_TIMEOUT_SECONDS)))
    return max(1.0, value)


def recommendation_examples_limit() -> int:
    value = int(os.getenv("LLM_RECOMMENDATION_EXAMPLES_LIMIT", str(DEFAULT_EXAMPLES_LIMIT)))
    return max(0, value)


def recommendation_examples_path() -> str:
    return os.getenv("LLM_RECOMMENDATION_EXAMPLES_PATH", "").strip()


def recommendation_text_max_chars() -> int:
    value = int(os.getenv("LLM_RECOMMENDATION_TEXT_MAX_CHARS", str(DEFAULT_TEXT_MAX_CHARS)))
    return max(160, value)


def recommendation_mode() -> str:
    value = os.getenv("LLM_RECOMMENDATION_MODE", DEFAULT_MODE).strip().lower()
    return value if value in {"fast", "full", "grouped"} else DEFAULT_MODE


def recommendation_max_llm_items() -> int:
    value = int(os.getenv("LLM_RECOMMENDATION_MAX_LLM_ITEMS", str(DEFAULT_MAX_LLM_ITEMS)))
    return max(0, value)


def recommendation_group_max_items() -> int:
    value = int(os.getenv("LLM_RECOMMENDATION_GROUP_MAX_ITEMS", str(DEFAULT_GROUP_MAX_ITEMS)))
    return max(1, value)


def recommendation_group_max_groups() -> int:
    value = int(os.getenv("LLM_RECOMMENDATION_GROUP_MAX_GROUPS", str(DEFAULT_GROUP_MAX_GROUPS)))
    return max(1, value)


def recommendation_group_num_predict() -> int:
    value = int(os.getenv("LLM_RECOMMENDATION_GROUP_NUM_PREDICT", str(DEFAULT_GROUP_NUM_PREDICT)))
    return max(220, value)


def recommendation_group_summary_only() -> bool:
    return os.getenv("LLM_RECOMMENDATION_GROUP_SUMMARY_ONLY", "false").lower() in {"1", "true", "yes"}


def recommendation_group_summary_num_predict() -> int:
    value = int(os.getenv("LLM_RECOMMENDATION_GROUP_SUMMARY_NUM_PREDICT", str(DEFAULT_GROUP_SUMMARY_NUM_PREDICT)))
    return max(96, value)


def generate_recommendation_package(
    text: str,
    category: str,
    category_label: str | None,
    secondary_categories: list[str] | None,
    level: int,
    level_label: str | None,
    rating: str,
    target_rating: str,
    evidence: list[dict] | None,
    confidence: dict,
    needs_review: bool,
    element_type: str = "action",
    character: str = "",
) -> dict:
    legal_context = retrieve_legal_context(
        category=category,
        level=level,
        rating=rating,
        text=text,
        evidence=evidence or [],
    )
    readable_category = category_label or get_category_label(category)
    secondary_labels = [get_category_label(item) for item in (secondary_categories or [])]
    fallback_text, fallback_payload = fallback_parts(
        text=text,
        category=category,
        category_label=readable_category,
        level=level,
        target_rating=target_rating,
        evidence=evidence or [],
        element_type=element_type,
        character=character,
        llm_error=None,
    )

    llm_result = call_ollama_json(build_messages(
        text=text,
        category=category,
        category_label=readable_category,
        secondary_categories=secondary_labels,
        level=level,
        level_label=level_label,
        rating=rating,
        target_rating=target_rating,
        evidence=evidence or [],
        confidence=confidence,
        needs_review=needs_review,
        legal_context=legal_context,
    ))

    if llm_result.payload is None:
        payload = {**fallback_payload, "uncertainty_note": llm_result.error}
    else:
        payload = llm_result.payload
        if not payload.get("self_check_passed", False) or not recommendation_self_check(payload, readable_category):
            payload = {
                **fallback_payload,
                "self_check_passed": False,
                "uncertainty_note": "LLM-рекомендация не прошла проверку соответствия категории.",
            }
            llm_result = type(llm_result)(
                payload=llm_result.payload,
                fallback_used=True,
                error="LLM recommendation failed category self-check",
            )

    return {
        "text": fallback_text if llm_result.fallback_used else format_recommendation_text(payload),
        "recommendation": {
            "summary": payload["summary"],
            "rewrite_suggestions": payload["rewrite_suggestions"],
            "fallback_used": llm_result.fallback_used,
            "self_check_passed": payload.get("self_check_passed", not llm_result.fallback_used),
        },
        "llm_recommendation": payload,
        "fallback_used": llm_result.fallback_used,
        "fallback_reason": llm_result.error if llm_result.fallback_used else None,
        "llm_error": llm_result.error,
        "legal_context": legal_context,
        "policy_basis": get_policy_entry(category)["basis"],
    }


def build_recommendation_context(
    item_id: str,
    text: str,
    category: str,
    category_label: str | None,
    secondary_categories: list[str] | None,
    level: int,
    level_label: str | None,
    rating: str,
    target_rating: str,
    evidence: list[dict] | None,
    confidence: dict,
    needs_review: bool,
    element_type: str = "action",
    character: str = "",
) -> dict:
    legal_context = retrieve_legal_context(
        category=category,
        level=level,
        rating=rating,
        text=text,
        evidence=evidence or [],
    )
    readable_category = category_label or get_category_label(category)
    fallback_text, fallback_payload = fallback_parts(
        text=text,
        category=category,
        category_label=readable_category,
        level=level,
        target_rating=target_rating,
        evidence=evidence or [],
        element_type=element_type,
        character=character,
        llm_error=None,
    )

    return {
        "id": item_id,
        "text": text,
        "category": category,
        "category_label": readable_category,
        "secondary_categories": secondary_categories or [],
        "secondary_labels": [get_category_label(item) for item in (secondary_categories or [])],
        "level": level,
        "level_label": level_label,
        "rating": rating,
        "target_rating": target_rating,
        "evidence": evidence or [],
        "confidence": confidence,
        "needs_review": needs_review,
        "element_type": element_type,
        "character": character,
        "legal_context": legal_context,
        "policy_basis": get_policy_entry(category)["basis"],
        "fallback_text": fallback_text,
        "fallback_payload": fallback_payload,
    }


def generate_recommendation_packages_batch(contexts: list[dict]) -> dict[str, dict]:
    if not contexts:
        return {}

    status = ollama_status()
    if not status.get("ready"):
        error = status.get("error") or status.get("status") or "Ollama is not ready"
        return {
            context["id"]: package_from_payload(
                context,
                {**context["fallback_payload"], "uncertainty_note": error},
                fallback_used=True,
                llm_error=error,
            )
            for context in contexts
        }

    results: dict[str, dict] = {}
    batch_size = recommendation_batch_size()
    deadline = time.monotonic() + recommendation_time_budget_seconds()
    batch_timeout = recommendation_batch_timeout_seconds()
    if recommendation_mode() == "grouped":
        return generate_grouped_recommendation_packages(
            contexts,
            deadline=deadline,
            timeout_seconds=batch_timeout,
        )

    llm_contexts, skipped_contexts = split_llm_contexts(contexts, recommendation_max_llm_items())
    if skipped_contexts:
        results.update(fallback_packages(skipped_contexts, "LLM recommendation skipped by production budget"))

    for start in range(0, len(llm_contexts), batch_size):
        batch = llm_contexts[start:start + batch_size]
        remaining = deadline - time.monotonic()
        if remaining <= 1:
            results.update(fallback_packages(batch, "LLM recommendation time budget exceeded"))
            continue

        results.update(_generate_recommendation_batch(
            batch,
            timeout_seconds=min(batch_timeout, remaining),
        ))
    return results


def split_llm_contexts(contexts: list[dict], limit: int) -> tuple[list[dict], list[dict]]:
    if limit <= 0:
        return contexts, []
    if len(contexts) <= limit:
        return contexts, []

    indexed = list(enumerate(contexts))
    indexed.sort(key=lambda item: recommendation_priority(item[1]), reverse=True)
    selected_indexes = {index for index, _context in indexed[:limit]}
    llm_contexts = [context for index, context in enumerate(contexts) if index in selected_indexes]
    skipped_contexts = [context for index, context in enumerate(contexts) if index not in selected_indexes]
    return llm_contexts, skipped_contexts


def recommendation_priority(context: dict) -> tuple[int, int, float]:
    rating_weight = {"18+": 4, "16+": 3, "12+": 2, "6+": 1, "0+": 0}.get(context.get("rating"), 0)
    evidence_weight = min(5, len(context.get("evidence") or []))
    confidence = context.get("confidence") if isinstance(context.get("confidence"), dict) else {}
    confidence_weight = float(confidence.get("rating", 0.0) or 0.0)
    return rating_weight, evidence_weight, confidence_weight


def generate_grouped_recommendation_packages(
    contexts: list[dict],
    deadline: float,
    timeout_seconds: float,
) -> dict[str, dict]:
    groups, skipped_groups = build_recommendation_groups(
        contexts,
        max_representatives=recommendation_group_max_items(),
        max_groups=recommendation_group_max_groups(),
    )
    results: dict[str, dict] = {}

    for group in skipped_groups:
        results.update(grouped_fallback_packages(group, "LLM recommendation group skipped by production budget"))

    for group in groups:
        remaining = deadline - time.monotonic()
        if remaining <= 1:
            results.update(grouped_fallback_packages(group, "LLM recommendation time budget exceeded"))
            continue

        summary_only = recommendation_group_summary_only()
        llm_result = call_ollama_json(
            build_grouped_summary_messages(group) if summary_only else build_grouped_messages(group),
            schema=GROUPED_SUMMARY_RECOMMENDATION_SCHEMA if summary_only else GROUPED_RECOMMENDATION_SCHEMA,
            num_predict=recommendation_group_summary_num_predict() if summary_only else recommendation_group_num_predict(),
            timeout_seconds=min(timeout_seconds, remaining),
        )
        if llm_result.payload is None:
            results.update(grouped_fallback_packages(group, llm_result.error))
            continue

        payload = grouped_payload_for(group, llm_result.payload)
        if payload is None:
            results.update(grouped_fallback_packages(group, "LLM grouped response missing group"))
            continue

        if not payload.get("self_check_passed", False) or not recommendation_self_check(payload, group["category_label"], group["category"]):
            results.update(grouped_fallback_packages(group, "LLM grouped recommendation failed category self-check"))
            continue

        for context in group["contexts"]:
            group_payload = dict(payload)
            group_payload["applies_to_ids"] = [item["id"] for item in group["contexts"]]
            if summary_only:
                group_payload["rewrite_suggestions"] = deterministic_rewrite_suggestions(context)
            results[context["id"]] = package_from_payload(
                context,
                group_payload,
                fallback_used=False,
                llm_error=None,
                grouped_recommendation_id=group["id"],
                grouped_recommendation_ids=group_payload["applies_to_ids"],
            )

    return results


def grouped_fallback_packages(group: dict, error: str | None) -> dict[str, dict]:
    group_ids = [context["id"] for context in group["contexts"]]
    return {
        context["id"]: package_from_payload(
            context,
            {**context["fallback_payload"], "uncertainty_note": error},
            fallback_used=True,
            llm_error=error,
            grouped_recommendation_id=group["id"],
            grouped_recommendation_ids=group_ids,
        )
        for context in group["contexts"]
    }


def build_recommendation_groups(
    contexts: list[dict],
    max_representatives: int,
    max_groups: int,
) -> tuple[list[dict], list[dict]]:
    buckets: dict[tuple, list[dict]] = {}
    for context in contexts:
        key = (
            context.get("category"),
            context.get("level"),
            context.get("rating"),
            context.get("target_rating"),
            evidence_signature(context),
        )
        buckets.setdefault(key, []).append(context)

    groups = []
    for index, (key, bucket_contexts) in enumerate(buckets.items(), start=1):
        category, level, rating, target_rating, signature = key
        representatives = sorted(bucket_contexts, key=recommendation_priority, reverse=True)[:max_representatives]
        groups.append({
            "id": f"group-{index}",
            "key": key,
            "category": category,
            "category_label": bucket_contexts[0]["category_label"],
            "level": level,
            "rating": rating,
            "target_rating": target_rating,
            "evidence_signature": signature,
            "contexts": bucket_contexts,
            "representatives": representatives,
            "priority": max(recommendation_priority(context) for context in bucket_contexts),
        })

    groups.sort(key=lambda group: (group["priority"], len(group["contexts"])), reverse=True)
    return groups[:max_groups], groups[max_groups:]


def evidence_signature(context: dict) -> str:
    terms = []
    for evidence in context.get("evidence", []):
        term = evidence.get("matched_term") if isinstance(evidence, dict) else None
        if term:
            terms.append(str(term).lower())
    if not terms:
        return "no-evidence"

    # Keep groups broad enough for production latency; evidence details still go
    # into representative scenes inside the grouped prompt.
    return "evidence"


def grouped_payload_for(group: dict, payload: dict) -> dict | None:
    groups = payload.get("groups", [])
    for item in groups:
        if item.get("group_id") == group["id"]:
            return {key: value for key, value in item.items() if key not in {"group_id"}}
    if len(groups) == 1 and isinstance(groups[0], dict):
        return {key: value for key, value in groups[0].items() if key not in {"group_id"}}
    return None


def _generate_recommendation_batch(contexts: list[dict], timeout_seconds: float | None = None) -> dict[str, dict]:
    if recommendation_mode() == "fast":
        return _generate_fast_recommendation_batch(contexts, timeout_seconds)

    llm_result = call_ollama_json(
        build_batch_messages(contexts),
        schema=BATCH_RECOMMENDATION_SCHEMA,
        num_predict=recommendation_batch_num_predict(),
        timeout_seconds=timeout_seconds,
    )

    if llm_result.payload is None:
        return fallback_packages(contexts, llm_result.error)

    payloads = {
        item["id"]: item
        for item in llm_result.payload.get("items", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    results = {}
    for context in contexts:
        payload = payloads.get(context["id"])
        error = None
        fallback_used = False
        if payload is None:
            payload = {
                **context["fallback_payload"],
                "uncertainty_note": "LLM batch response did not include this scene.",
            }
            error = "LLM batch response missing item"
            fallback_used = True
        else:
            payload = {key: value for key, value in payload.items() if key != "id"}
            if not payload.get("self_check_passed", False) or not recommendation_self_check(payload, context["category_label"], context["category"]):
                payload = {
                    **context["fallback_payload"],
                    "self_check_passed": False,
                    "uncertainty_note": "LLM recommendation failed category self-check.",
                }
                error = "LLM recommendation failed category self-check"
                fallback_used = True

        results[context["id"]] = package_from_payload(
            context,
            payload,
            fallback_used=fallback_used,
            llm_error=error,
        )

    return results


def _generate_fast_recommendation_batch(contexts: list[dict], timeout_seconds: float | None = None) -> dict[str, dict]:
    llm_result = call_ollama_json(
        build_fast_batch_messages(contexts),
        schema=FAST_BATCH_RECOMMENDATION_SCHEMA,
        num_predict=min(recommendation_batch_num_predict(), 220),
        timeout_seconds=timeout_seconds,
    )

    if llm_result.payload is None:
        return fallback_packages(contexts, llm_result.error)

    payloads = {
        item["id"]: item
        for item in llm_result.payload.get("items", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    results = {}
    for context in contexts:
        payload = payloads.get(context["id"])
        error = None
        fallback_used = False
        if payload is None:
            payload = {
                **context["fallback_payload"],
                "uncertainty_note": "LLM fast batch response did not include this scene.",
            }
            error = "LLM fast batch response missing item"
            fallback_used = True
        else:
            payload = {
                **context["fallback_payload"],
                "summary": payload["summary"],
                "explanation": payload["explanation"],
                "risk_factors": payload.get("risk_factors") or context["fallback_payload"].get("risk_factors", []),
                "self_check_passed": payload.get("self_check_passed", False),
                "uncertainty_note": payload.get("uncertainty_note"),
            }
            if not payload.get("self_check_passed", False) or not recommendation_self_check(payload, context["category_label"], context["category"]):
                payload = {
                    **context["fallback_payload"],
                    "self_check_passed": False,
                    "uncertainty_note": "LLM recommendation failed category self-check.",
                }
                error = "LLM recommendation failed category self-check"
                fallback_used = True

        results[context["id"]] = package_from_payload(
            context,
            payload,
            fallback_used=fallback_used,
            llm_error=error,
        )

    return results


def fallback_packages(contexts: list[dict], error: str | None) -> dict[str, dict]:
    return {
        context["id"]: package_from_payload(
            context,
            {**context["fallback_payload"], "uncertainty_note": error},
            fallback_used=True,
            llm_error=error,
        )
        for context in contexts
    }


def package_from_payload(
    context: dict,
    payload: dict,
    fallback_used: bool,
    llm_error: str | None,
    grouped_recommendation_id: str | None = None,
    grouped_recommendation_ids: list[str] | None = None,
) -> dict:
    return {
        "text": context["fallback_text"] if fallback_used else format_recommendation_text(payload),
        "recommendation": {
            "summary": payload["summary"],
            "rewrite_suggestions": payload["rewrite_suggestions"],
            "fallback_used": fallback_used,
            "self_check_passed": payload.get("self_check_passed", not fallback_used),
            "grouped_recommendation_id": grouped_recommendation_id,
            "grouped_recommendation_ids": grouped_recommendation_ids or [context["id"]],
        },
        "llm_recommendation": payload,
        "fallback_used": fallback_used,
        "fallback_reason": llm_error if fallback_used else None,
        "llm_error": llm_error,
        "legal_context": context["legal_context"],
        "policy_basis": context["policy_basis"],
        "grouped_recommendation_id": grouped_recommendation_id,
        "grouped_recommendation_ids": grouped_recommendation_ids or [context["id"]],
    }


def fallback_parts(
    text: str,
    category: str,
    category_label: str,
    level: int,
    target_rating: str,
    evidence: list[dict],
    element_type: str,
    character: str,
    llm_error: str | None,
) -> tuple[str, dict]:
    fallback_text = fallback_recommendation(
        category=category,
        level=level,
        target_rating=target_rating,
        element_type=element_type,
        character=character,
    )
    fallback_payload = build_fallback_payload(
        text=text,
        fallback_text=fallback_text,
        category_label=category_label,
        target_rating=target_rating,
        evidence=evidence,
        llm_error=llm_error,
    )
    return fallback_text, fallback_payload


def build_messages(
    text: str,
    category: str,
    category_label: str,
    secondary_categories: list[str],
    level: int,
    level_label: str | None,
    rating: str,
    target_rating: str,
    evidence: list[dict],
    confidence: dict,
    needs_review: bool,
    legal_context: list[dict],
) -> list[dict[str, str]]:
    context = "\n".join(f"- {item.get('text')}" for item in legal_context)
    prompt = f"""
Ты локальный редакторский ассистент ML_WINK для анализа возрастных рисков сценария.
Не меняй категорию, уровень, рейтинг и флаг проверки. Они уже рассчитаны отдельным rating engine.
Верни только JSON по заданной схеме.

Фрагмент сценария:
{text}

Факты rating engine:
primary_category_id={category}
primary_category_label={category_label}
secondary_categories={secondary_categories}
level={level}
level_label={level_label or level}
rating={rating}
target_rating={target_rating}
needs_review={needs_review}
confidence={confidence}
evidence={evidence}

Локальный policy context:
{context}

Сформулируй краткое объяснение риска, 1-4 фактора риска и ровно 3 практические редакторские правки для снижения к target_rating:
1) мягкая правка;
2) сильное снижение рейтинга;
3) сохранить драму, убрать риск.
Каждая правка должна содержать before/after и работать с конкретным фрагментом из evidence или исходного текста.
Поле self_check_passed поставь true только если рекомендации соответствуют primary_category_label и не меняют рассчитанный рейтинг.
""".strip()

    return [
        {
            "role": "system",
            "content": "Ты отвечаешь строго валидным JSON. Не добавляй markdown и не меняй рассчитанный рейтинг.",
        },
        {
            "role": "user",
            "content": prompt,
        },
    ]


def build_batch_messages(contexts: list[dict]) -> list[dict[str, str]]:
    compact_items = []
    text_limit = recommendation_text_max_chars()
    for context in contexts:
        compact_items.append({
            "id": context["id"],
            "text": _shorten(context["text"], text_limit),
            "primary_category_id": context["category"],
            "primary_category_label": context["category_label"],
            "secondary_categories": context["secondary_labels"],
            "level": context["level"],
            "level_label": context["level_label"] or context["level"],
            "rating": context["rating"],
            "target_rating": context["target_rating"],
            "needs_review": context["needs_review"],
            "confidence": context["confidence"],
            "evidence": context["evidence"][:3],
            "legal_context": [
                _shorten(item.get("text", ""), DEFAULT_LEGAL_CONTEXT_MAX_CHARS)
                for item in context["legal_context"][:2]
            ],
        })

    examples = select_recommendation_examples(contexts, recommendation_examples_limit())
    examples_block = ""
    if examples:
        examples_block = (
            "\n\nReference examples from the local pseudo-tuned dataset. "
            "Use their style and structure, but do not copy facts into unrelated items:\n"
            f"{json.dumps(examples, ensure_ascii=False)}"
        )

    prompt = f"""
You are a local editorial assistant for ML_WINK age-risk screenplay analysis.
Do not change category, level, rating, target_rating, needs_review, or evidence. These facts are already calculated by the rating engine.
Return only valid JSON matching the provided schema.

For each input item, return exactly one output item with the same id.
Each output item must contain a short explanation, 1-4 risk_factors, and exactly 3 practical rewrite_suggestions:
1. soft edit;
2. strong rating reduction;
3. keep drama while removing risk.
Each suggestion must include goal, before, after, rationale, expected_effect.
Set self_check_passed=true only if the recommendation matches primary_category_label and does not alter the calculated rating facts.
{examples_block}

Input items:
{json.dumps(compact_items, ensure_ascii=False)}
""".strip()

    return [
        {
            "role": "system",
            "content": "Return strict JSON only. Do not add markdown. Preserve every input id exactly.",
        },
        {
            "role": "user",
            "content": prompt,
        },
    ]


def build_fast_batch_messages(contexts: list[dict]) -> list[dict[str, str]]:
    compact_items = []
    text_limit = min(recommendation_text_max_chars(), 420)
    for context in contexts:
        compact_items.append({
            "id": context["id"],
            "text": _shorten(context["text"], text_limit),
            "category": context["category_label"],
            "rating": context["rating"],
            "target_rating": context["target_rating"],
            "evidence": context["evidence"][:2],
        })

    examples = select_recommendation_examples(contexts, min(recommendation_examples_limit(), 1))
    examples_block = ""
    if examples:
        compact_examples = [
            {
                    "input": example["input"],
                    "expected": {
                    "summary": _shorten(example["expected"].get("summary", ""), 140),
                    "explanation": _shorten(example["expected"].get("explanation", ""), 220),
                    "risk_factors": example["expected"].get("risk_factors", [])[:2],
                    "self_check_passed": True,
                },
            }
            for example in examples
        ]
        examples_block = f"\nExamples:\n{json.dumps(compact_examples, ensure_ascii=False)}\n"

    prompt = f"""
Return JSON only: {{"items":[...]}}.
For each input item, preserve id exactly and output:
id, summary, explanation, risk_factors, self_check_passed, uncertainty_note.
Do not change category, rating, target_rating or evidence.
Keep summary and explanation concise. self_check_passed=true only when text matches the given category.
{examples_block}
Input:
{json.dumps(compact_items, ensure_ascii=False)}
""".strip()

    return [
        {
            "role": "system",
            "content": "/no_think\nReturn strict JSON only. No markdown.",
        },
        {
            "role": "user",
            "content": prompt,
        },
    ]


def build_grouped_messages(group: dict) -> list[dict[str, str]]:
    representatives = []
    for context in group["representatives"]:
        representatives.append({
            "id": context["id"],
            "text": _shorten(context["text"], min(recommendation_text_max_chars(), 320)),
            "evidence": compact_evidence(context["evidence"], limit=2, text_limit=140),
        })

    prompt_payload = {
        "group_id": group["id"],
        "applies_to_ids": [context["id"] for context in group["contexts"]],
        "category": group["category_label"],
        "category_id": group["category"],
        "level": group["level"],
        "rating": group["rating"],
        "target_rating": group["target_rating"],
            "representative_scenes": representatives,
    }
    examples = select_recommendation_examples(group["contexts"], min(recommendation_examples_limit(), 1))
    examples_block = ""
    if examples:
        examples_block = (
            "\nReference style example from the local pseudo-tuned dataset. "
            "Use its structure and tone, but adapt the facts to this group:\n"
            f"{json.dumps(examples, ensure_ascii=False)}\n"
        )
    prompt = f"""
Return JSON only: {{"groups":[...]}}.
Write one compact grouped editorial recommendation for all applies_to_ids.
Use Russian only for summary, explanation, risk_factors and rewrite_suggestions.
Preserve group_id exactly. Preserve every applies_to_ids value exactly.
Do not change category, level, rating, target_rating or evidence.
Output exactly 3 rewrite_suggestions:
1. soft edit;
2. strong rating reduction;
3. keep drama while removing risk.
Each suggestion must include goal, before, after, rationale, expected_effect. Keep every field short.
self_check_passed=true only when the recommendation matches the category and rating facts.
{examples_block}

Input group:
{json.dumps(prompt_payload, ensure_ascii=False)}
""".strip()

    return [
        {
            "role": "system",
            "content": "/no_think\nReturn strict JSON only. No markdown.",
        },
        {
            "role": "user",
            "content": prompt,
        },
    ]


def build_grouped_summary_messages(group: dict) -> list[dict[str, str]]:
    representatives = []
    for context in group["representatives"][: min(3, len(group["representatives"]))]:
        representatives.append({
            "id": context["id"],
            "text": _shorten(context["text"], min(recommendation_text_max_chars(), 260)),
            "evidence": compact_evidence(context["evidence"], limit=1, text_limit=100),
        })

    prompt_payload = {
        "group_id": group["id"],
        "applies_to_ids": [context["id"] for context in group["contexts"]],
        "category": group["category_label"],
        "category_id": group["category"],
        "level": group["level"],
        "rating": group["rating"],
        "target_rating": group["target_rating"],
        "representative_scenes": representatives,
    }
    prompt = f"""
Return JSON only: {{"groups":[...]}}.
Write one compact risk summary for this group.
Use Russian only for summary, explanation and risk_factors.
Preserve group_id exactly and every applies_to_ids value exactly.
Do not write rewrite_suggestions.
Output fields: group_id, applies_to_ids, summary, explanation, risk_factors, self_check_passed, uncertainty_note.
Keep summary under 120 characters, explanation under 240 characters, risk_factors 1-3 short strings.
self_check_passed=true only when the text matches category and rating facts.

Input group:
{json.dumps(prompt_payload, ensure_ascii=False)}
""".strip()

    return [
        {
            "role": "system",
            "content": "/no_think\nReturn strict JSON only. No markdown.",
        },
        {
            "role": "user",
            "content": prompt,
        },
    ]


def compact_evidence(evidence: list[dict], limit: int, text_limit: int) -> list[dict]:
    compact = []
    for item in evidence[:limit]:
        if not isinstance(item, dict):
            continue
        compact.append({
            "text": _shorten(item.get("text", ""), text_limit),
            "matched_term": item.get("matched_term"),
        })
    return compact


def deterministic_rewrite_suggestions(context: dict) -> list[dict]:
    suggestions = context.get("fallback_payload", {}).get("rewrite_suggestions")
    if isinstance(suggestions, list) and suggestions:
        return suggestions[:3]

    _fallback_text, fallback_payload = fallback_parts(
        text=context.get("text", ""),
        category=context.get("category", ""),
        category_label=context.get("category_label", ""),
        level=int(context.get("level") or 1),
        target_rating=context.get("target_rating", "12+"),
        evidence=context.get("evidence", []),
        element_type=context.get("element_type", "action"),
        character=context.get("character", ""),
        llm_error=None,
    )
    return fallback_payload["rewrite_suggestions"][:3]


def select_recommendation_examples(contexts: list[dict], limit: int) -> list[dict]:
    if limit <= 0:
        return []

    examples = load_recommendation_examples(recommendation_examples_path())
    if not examples:
        return []

    scored = []
    context_terms = set()
    categories = set()
    ratings = set()
    for context in contexts:
        categories.add(context.get("category"))
        ratings.add(context.get("rating"))
        context_terms.update(_terms(context.get("text", "")))
        for evidence in context.get("evidence", []):
            context_terms.update(_terms(str(evidence.get("text", ""))))

    for example in examples:
        input_payload = example.get("input", {})
        score = 0
        if input_payload.get("category") in categories:
            score += 6
        if input_payload.get("rating") in ratings:
            score += 3
        score += min(4, len(context_terms & _terms(input_payload.get("text", ""))))
        if score > 0:
            scored.append((score, example))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [compact_recommendation_example(example) for _score, example in scored[:limit]]


@lru_cache(maxsize=8)
def load_recommendation_examples(path_value: str) -> tuple[dict, ...]:
    if not path_value:
        return ()

    path = Path(path_value)
    if not path.exists():
        return ()

    examples = []
    max_items = int(os.getenv("LLM_RECOMMENDATION_EXAMPLES_MAX_ITEMS", str(DEFAULT_EXAMPLES_MAX_ITEMS)))
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict) and isinstance(item.get("input"), dict) and isinstance(item.get("expected"), dict):
                examples.append(item)
            if len(examples) >= max_items:
                break
    return tuple(examples)


def compact_recommendation_example(example: dict) -> dict:
    input_payload = example.get("input", {})
    expected = example.get("expected", {})
    return {
        "input": {
            "category": input_payload.get("category"),
            "category_label": input_payload.get("category_label"),
            "level": input_payload.get("level"),
            "rating": input_payload.get("rating"),
            "target_rating": input_payload.get("target_rating"),
            "evidence": input_payload.get("evidence", [])[:2],
            "text": _shorten(input_payload.get("text", ""), 260),
        },
        "expected": {
            "summary": expected.get("summary"),
            "explanation": _shorten(expected.get("explanation", ""), 260),
            "risk_factors": expected.get("risk_factors", [])[:3],
            "rewrite_suggestions": expected.get("rewrite_suggestions", [])[:3],
            "self_check_passed": expected.get("self_check_passed", True),
        },
    }


def _terms(text: str) -> set[str]:
    return {token.lower() for token in text.split() if len(token) > 4}


def _shorten(text: str, limit: int) -> str:
    text = " ".join(str(text).split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def format_recommendation_text(payload: dict) -> str:
    parts = [payload["explanation"].strip()]
    risk_factors = [item.strip() for item in payload.get("risk_factors", []) if item.strip()]
    suggestions = [
        item for item in payload.get("rewrite_suggestions", [])
        if isinstance(item, (str, dict))
    ]
    uncertainty = payload.get("uncertainty_note")

    if risk_factors:
        parts.append("Факторы риска:\n" + "\n".join(f"- {item}" for item in risk_factors))
    if suggestions:
        parts.append("Редакторские правки:\n" + "\n".join(format_suggestion(item) for item in suggestions))
    if uncertainty:
        parts.append(f"Примечание: {uncertainty}")

    return "\n\n".join(parts)


def format_suggestion(item: str | dict) -> str:
    if isinstance(item, str):
        return f"- {item}"
    return (
        f"- {item.get('goal', 'Правка')}\n"
        f"  Что изменить: {item.get('after', '').strip()}\n"
        f"  Почему: {item.get('rationale', '').strip()}\n"
        f"  Эффект: {item.get('expected_effect', '').strip()}"
    )


def build_fallback_payload(
    text: str,
    fallback_text: str,
    category_label: str,
    target_rating: str,
    evidence: list[dict],
    llm_error: str | None,
) -> dict:
    before = evidence[0]["text"] if evidence else text[:180]
    return {
        "summary": f"{category_label}: требуется редакторская правка для снижения до {target_rating}.",
        "explanation": fallback_text,
        "risk_factors": [item["text"] for item in evidence[:4]],
        "rewrite_suggestions": [
            {
                "goal": "Мягкая правка",
                "before": before,
                "after": "Событие остаётся в сцене, но риск передаётся через реакцию персонажей без подробного описания действия.",
                "rationale": "Снижается детализация рискованного действия.",
                "expected_effect": f"Может приблизить сцену к рейтингу {target_rating}.",
            },
            {
                "goal": "Сильное снижение рейтинга",
                "before": before,
                "after": "Рискованное действие происходит за кадром; в тексте остаются только его нейтральные последствия.",
                "rationale": "Убирается прямой триггер возрастного риска.",
                "expected_effect": f"Сильнее снижает вероятность рейтинга выше {target_rating}.",
            },
            {
                "goal": "Сохранить драму, убрать риск",
                "before": before,
                "after": "Напряжение сохраняется через паузу, взгляд, звук или монтажный переход без прямого описания риска.",
                "rationale": "Драматическая функция сцены сохраняется без усиления риск-контента.",
                "expected_effect": "Сохраняет конфликт и уменьшает спорность сцены.",
            },
        ],
        "self_check_passed": True,
        "uncertainty_note": llm_error,
    }


def recommendation_self_check(payload: dict, category_label: str, category_id: str | None = None) -> bool:
    text = " ".join([
        payload.get("summary", ""),
        payload.get("explanation", ""),
        " ".join(payload.get("risk_factors", [])),
        " ".join(
            " ".join(str(value) for value in item.values())
            for item in payload.get("rewrite_suggestions", [])
            if isinstance(item, dict)
        ),
    ]).lower()
    category_tokens = [token.lower() for token in category_label.split() if len(token) > 3]
    semantic_tokens = {
        "violence": ["насил", "драк", "удар", "оруж", "violence", "violent"],
        "profanity": ["лексик", "бран", "ругател", "мат", "profan", "swear", "language"],
        "substance": ["алког", "табак", "наркот", "substance", "drug", "alcohol"],
        "sexual": ["интим", "сексу", "эрот", "sexual", "intim"],
        "fear": ["пуга", "страх", "тревог", "fear", "scary"],
    }.get(str(category_id or ""), [])
    tokens = category_tokens + semantic_tokens
    return bool(tokens) and any(token in text for token in tokens)
