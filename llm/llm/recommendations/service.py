from llm.legal.policy import fallback_recommendation, get_policy_entry
from llm.legal.retrieval import retrieve_legal_context
from llm.llm_client import call_ollama_json
from llm.taxonomy import category_label as get_category_label


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
        category_label=readable_category,
        target_rating=target_rating,
        evidence=evidence or [],
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
        f"  Было: {item.get('before', '').strip()}\n"
        f"  Стало: {item.get('after', '').strip()}\n"
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
                "after": "Смягчите прямое описание риска и оставьте событие через реакцию персонажей.",
                "rationale": "Снижается детализация рискованного действия.",
                "expected_effect": f"Может приблизить сцену к рейтингу {target_rating}.",
            },
            {
                "goal": "Сильное снижение рейтинга",
                "before": before,
                "after": "Перенесите рискованное действие за кадр или замените его нейтральным конфликтом.",
                "rationale": "Убирается прямой триггер возрастного риска.",
                "expected_effect": f"Сильнее снижает вероятность рейтинга выше {target_rating}.",
            },
            {
                "goal": "Сохранить драму, убрать риск",
                "before": before,
                "after": "Оставьте напряжение через паузу, взгляд, звук или последствия без прямого описания действия.",
                "rationale": "Драматическая функция сцены сохраняется без усиления риск-контента.",
                "expected_effect": "Сохраняет конфликт и уменьшает спорность сцены.",
            },
        ],
        "self_check_passed": True,
        "uncertainty_note": llm_error,
    }


def recommendation_self_check(payload: dict, category_label: str) -> bool:
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
    return bool(category_tokens) and any(token in text for token in category_tokens)
