import json
import logging
import os
import time
from datetime import datetime, timezone

from llm.classification.rubert import get_model_manifest, load_model_and_tokenizer, predict_texts_batch
from llm.core.metrics import (
    metrics_snapshot,
    record_analysis_completed,
    record_fallback,
    record_stage_timing,
)
from llm.core.model_registry import active_model_metadata, resolve_model_dir
from llm.core.structured_logging import log_event
from llm.detection.rule_detector import analyze_parsed_script
from llm.legal.policy import POLICY_VERSION, calculate_simple_rating
from llm.llm_client import DEFAULT_OLLAMA_MODEL
from llm.paths import DEFAULT_MODEL_DIR, OUTPUTS_DIR, resolve_project_path
from llm.parsing.script_parser import parse_script
from llm.pipeline.guards import apply_evidence_guard
from llm.recommendations.service import build_recommendation_context, generate_recommendation_packages_batch, recommendation_mode
from llm.rating import RATING_ORDER, aggregate_project_rating, calibrate_level_from_evidence, get_rating_index
from llm.risk_policy import needs_human_review
from llm.taxonomy import (
    TAXONOMY_VERSION,
    category_label,
    evidence_items,
    level_label,
    primary_category_from_evidence,
)

import torch


logger = logging.getLogger(__name__)
RATING_INDEX_KEY = "\u0438\u043d\u0434\u0435\u043a\u0441_\u0440\u0435\u0439\u0442\u0438\u043d\u0433\u0430"
ANALYSIS_TARGET_VALUES = {"6+", "12+", "16+", "18+"}

# ----------------- CONFIG -----------------
INPUT_SCRIPT = ".docx"
OUTPUT_ALL = OUTPUTS_DIR / "all_suspicious.json"
OUTPUT_MAX = OUTPUTS_DIR / "max_rating_scenes.json"
RUBERT_MODEL_DIR = DEFAULT_MODEL_DIR
MAX_LEN = 256
RUBERT_BATCH_SIZE = int(os.getenv("RUBERT_BATCH_SIZE", "16"))
def resolve_category_with_rule_evidence(prediction: dict, natasha: dict) -> tuple[str, list[str]]:
    predicted_category = prediction["category"]
    return primary_category_from_evidence(predicted_category, natasha)


def target_rating_for(rating: str) -> str:
    rating_index = get_rating_index(rating)
    if rating_index <= 0:
        return "0+"
    return RATING_ORDER[max(0, rating_index - 1)]


def normalize_analysis_target_rating(value: str | None) -> str | None:
    normalized = str(value or "raw").strip()
    if not normalized or normalized.lower() == "raw":
        return None
    if normalized not in ANALYSIS_TARGET_VALUES:
        raise ValueError("Invalid target_rating. Use raw, 6+, 12+, 16+ or 18+.")
    return normalized

def _elapsed(t0: float) -> float:
    return round(time.time() - t0, 3)


def drop_mojibake_keys(payload: dict) -> None:
    for key in list(payload.keys()):
        if isinstance(key, str) and any(marker in key for marker in ("Ð", "Ñ", "Р")):
            payload.pop(key, None)


def summarize_fallback_reasons(items: list[dict]) -> dict:
    reasons: dict[str, int] = {}
    groups = {
        "budget": 0,
        "timeout": 0,
        "unavailable": 0,
        "validation": 0,
        "disabled": 0,
        "other": 0,
    }

    for item in items:
        if not item.get("fallback_used"):
            continue
        reason = public_fallback_reason(str(item.get("fallback_reason") or item.get("llm_error") or "unknown"))
        reasons[reason] = reasons.get(reason, 0) + 1
        lowered = reason.lower()
        if "production budget" in lowered or "time budget" in lowered:
            groups["budget"] += 1
        elif "timed out" in lowered or "timeout" in lowered or "read timed out" in lowered:
            groups["timeout"] += 1
        elif "unavailable" in lowered or "not ready" in lowered or "connection" in lowered or "model_not_pulled" in lowered:
            groups["unavailable"] += 1
        elif "self-check" in lowered or "schema" in lowered or "missing item" in lowered or "unterminated string" in lowered:
            groups["validation"] += 1
        elif "disabled" in lowered:
            groups["disabled"] += 1
        else:
            groups["other"] += 1

    total = sum(reasons.values())
    if total == 0:
        user_message = None
    elif groups["timeout"] or groups["unavailable"]:
        user_message = "Часть рекомендаций сформирована шаблонно из-за недоступности или таймаута LLM."
    elif groups["budget"]:
        user_message = "Часть рекомендаций сформирована шаблонно из-за ограничения времени анализа."
    else:
        user_message = "Часть рекомендаций сформирована шаблонно."

    return {
        "total": total,
        "groups": {key: value for key, value in groups.items() if value},
        "reasons": reasons,
        "user_message": user_message,
    }


def public_fallback_reason(reason: str) -> str:
    lowered = reason.lower()
    if "production budget" in lowered or "time budget" in lowered:
        return "LLM recommendation time budget exceeded"
    if "timed out" in lowered or "timeout" in lowered or "read timed out" in lowered:
        return "LLM recommendation timed out"
    if "connection" in lowered or "unavailable" in lowered or "not ready" in lowered:
        return "LLM service unavailable"
    if "missing item" in lowered:
        return "LLM batch response missing item"
    if "unterminated string" in lowered or "json" in lowered:
        return "LLM recommendation returned invalid JSON"
    if "self-check" in lowered or "self check" in lowered:
        return "LLM recommendation failed self-check"
    if "disabled" in lowered:
        return "LLM recommendations disabled"
    return reason[:160]


def display_risk_text(text: str, evidence: list[dict], max_sentences: int = 3) -> str:
    """Return a compact user-facing fragment around the strongest evidence."""
    text = " ".join(str(text or "").split())
    if not text:
        return ""

    anchors = [
        str(item.get("matched_term") or item.get("text") or "").strip()
        for item in evidence or []
        if isinstance(item, dict)
    ]
    sentences = split_sentences_for_display(text)

    for anchor in anchors:
        if not anchor:
            continue
        lowered_anchor = anchor.lower()
        for index, sentence in enumerate(sentences):
            if lowered_anchor in sentence.lower():
                return sentence_window(sentences, index, max_sentences=max_sentences)

    return " ".join(sentences[:max_sentences]).strip()


def split_sentences_for_display(text: str) -> list[str]:
    import re

    parts = re.split(r"(?<=[.!?\u2026])\s+", text)
    return [part.strip() for part in parts if part.strip()] or [text.strip()]


def sentence_window(sentences: list[str], index: int, max_sentences: int = 3) -> str:
    if not sentences:
        return ""
    left = max(0, index - 1)
    right = min(len(sentences), left + max_sentences)
    if index >= right:
        right = min(len(sentences), index + 1)
        left = max(0, right - max_sentences)
    return " ".join(sentences[left:right]).strip()


def _analysis_metadata(
    rubert_model_dir,
    analysis_id: str | None,
    request_id: str | None,
    stage_timings: dict[str, float],
    analysis_target_rating: str | None,
) -> dict:
    manifest = get_model_manifest(rubert_model_dir)
    weights = manifest.get("weights", {}) if isinstance(manifest, dict) else {}
    rubert_registry = active_model_metadata("rubert")
    qwen_registry = active_model_metadata("qwen")
    return {
        "analysis_id": analysis_id,
        "request_id": request_id,
        "analysis_mode": "targeted" if analysis_target_rating else "raw",
        "target_rating": analysis_target_rating,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stage_timings_seconds": stage_timings,
        "models": {
            "rubert": {
                "model_name": rubert_registry.get("model_name") or manifest.get("model_name"),
                "base_model": rubert_registry.get("base_model") or manifest.get("base_model"),
                "model_version": manifest.get("generated_at") or manifest.get("created_at_unix"),
                "weights_hash": weights.get("sha256"),
                "model_dir": str(rubert_model_dir),
                "created_at": rubert_registry.get("created_at") or manifest.get("generated_at"),
            },
            "qwen": {
                "model_name": qwen_registry.get("model_name") or os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
                "created_at": qwen_registry.get("created_at"),
            },
        },
        "policy_version": POLICY_VERSION,
        "taxonomy_version": TAXONOMY_VERSION,
        "metrics_snapshot": metrics_snapshot(),
    }


def run_pipeline(
    input_path: str,
    output_all: str,
    output_max: str,
    rubert_model_dir: str = RUBERT_MODEL_DIR,
    analysis_id: str | None = None,
    request_id: str | None = None,
    target_rating: str | None = None,
):
    t0 = time.time()
    analysis_target_rating = normalize_analysis_target_rating(target_rating)
    analysis_target_index = get_rating_index(analysis_target_rating) if analysis_target_rating else None
    stage_timings = {}
    input_path = resolve_project_path(input_path)
    output_all = resolve_project_path(output_all)
    output_max = resolve_project_path(output_max)
    rubert_model_dir = resolve_project_path(resolve_model_dir("rubert", rubert_model_dir))
    log_event(
        logger,
        "analysis.pipeline.started",
        analysis_id=analysis_id,
        request_id=request_id,
        input_path=str(input_path),
        target_rating=analysis_target_rating,
        rubert_model_dir=str(rubert_model_dir),
    )

    if not input_path.exists():
        raise FileNotFoundError(f"Файл сценария не найден: {input_path}")
    if not rubert_model_dir.exists():
        raise FileNotFoundError(
            f"RuBERT модель не найдена: {rubert_model_dir}. "
            "Для Docker смонтируйте llm/trained_model в /models/trained_model. "
            "Для локального запуска положите модель в llm/trained_model."
        )

    output_all.parent.mkdir(parents=True, exist_ok=True)
    output_max.parent.mkdir(parents=True, exist_ok=True)

    print("1) Парсинг сценария...")
    stage_t0 = time.time()
    parsed = parse_script(input_path)
    stage_timings["parsing"] = _elapsed(stage_t0)
    record_stage_timing("parsing", stage_timings["parsing"])
    log_event(logger, "analysis.stage.completed", stage="parsing", seconds=stage_timings["parsing"])
    print(f"   -> найдено сцен: {len(parsed.get('scenes', []))}")

    print("2) Первичная фильтрация (наташа)...")
    stage_t0 = time.time()
    filtered = analyze_parsed_script(parsed)
    stage_timings["rule_detection"] = _elapsed(stage_t0)
    record_stage_timing("rule_detection", stage_timings["rule_detection"])
    log_event(logger, "analysis.stage.completed", stage="rule_detection", seconds=stage_timings["rule_detection"])
    print("   -> фильтрация завершена.")

    print("3) Загружаем RuBERT модель...")
    stage_t0 = time.time()
    load_model_and_tokenizer(str(rubert_model_dir))
    stage_timings["rubert_load"] = _elapsed(stage_t0)
    record_stage_timing("rubert_load", stage_timings["rubert_load"])
    log_event(logger, "analysis.stage.completed", stage="rubert_load", seconds=stage_timings["rubert_load"])

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("   -> RuBERT загружен.")

    all_suspicious_data = []  # Для всех подозрительных сцен
    total = 0
    suspicious_total = 0

    # ПЕРВЫЙ ПРОХОД: собираем ВСЕ подозрительные сцены + рекомендации
    timeline_position = 0
    rubert_inference_seconds = 0.0
    recommendation_seconds = 0.0
    recommendation_contexts = []
    rubert_candidates = []
    for scene in filtered.get("scenes", []):
        scene_id = scene.get("scene_id")
        header = scene.get("header", "")
        for element_index, element in enumerate(scene.get("elements", [])):
            total += 1
            timeline_position += 1
            text = element.get("text", "").strip()
            if not text:
                continue

            natasha = element.get("natasha_flags", {})
            is_suspicious = natasha.get("is_suspicious", False) if isinstance(natasha, dict) else False

            if not is_suspicious:
                continue

            suspicious_total += 1
            full_text = " ".join(filter(None, [element.get("character", ""), text]))
            natasha = natasha if isinstance(natasha, dict) else {}
            rubert_candidates.append({
                "scene": scene,
                "scene_id": scene_id,
                "header": header,
                "element_index": element_index,
                "timeline_position": timeline_position,
                "element": element,
                "text": text,
                "full_text": full_text,
                "natasha": natasha,
            })
            continue

            # --- RuBERT inference ---
            stage_t0 = time.time()
            prediction = predict_text(
                full_text,
                model_path=rubert_model_dir,
                max_len=MAX_LEN,
                device=str(device),
            )
            rubert_inference_seconds += time.time() - stage_t0
            original_model_category = prediction.get("category")
            prediction, guard_reasons = apply_evidence_guard(prediction, natasha, text)
            predicted_category, secondary_categories = resolve_category_with_rule_evidence(prediction, natasha)
            predicted_level = prediction["level"]
            if predicted_category == "safe" or predicted_level <= 0:
                suspicious_total -= 1
                continue

            # Определяем рейтинг
            simple_rating = prediction.get("rating") or calculate_simple_rating(predicted_category, predicted_level)
            rating_index = get_rating_index(simple_rating)
            target_rating = target_rating_for(simple_rating)
            review_required = needs_human_review(prediction)
            log_event(
                logger,
                "analysis.rating_policy.completed",
                analysis_id=analysis_id,
                scene_id=scene_id,
                element_index=element_index,
                category=predicted_category,
                level=predicted_level,
                rating=simple_rating,
                needs_review=review_required,
            )

            # Формируем category_scores
            cat_scores = prediction["category_scores"]

            # Поиск оригинального элемента для типа и персонажа
            original_element = None
            for s in filtered.get("scenes", []):
                if s.get("scene_id") == scene_id:
                    for elem in s.get("elements", []):
                        if elem.get("text", "").strip() == text:
                            original_element = elem
                            break
                    if original_element:
                        break

            element_type = original_element.get("type", "action") if original_element else "action"
            character = original_element.get("character", "") if original_element else ""
            matched_terms_by_category = natasha.get("matched_terms", {}) if isinstance(natasha, dict) else {}
            evidence = evidence_items(text, matched_terms_by_category)
            display_text = display_risk_text(text, evidence)

            recommendation_id = f"rec-{len(recommendation_contexts) + 1}"
            recommendation_contexts.append(build_recommendation_context(
                item_id=recommendation_id,
                text=display_text,
                category=predicted_category,
                category_label=category_label(predicted_category),
                secondary_categories=secondary_categories,
                level=predicted_level,
                level_label=level_label(predicted_level),
                rating=simple_rating,
                target_rating=target_rating,
                evidence=evidence,
                confidence={
                    "category": prediction["category_confidence"],
                    "level": prediction["level_confidence"],
                    "rating": prediction["rating_confidence"],
                },
                needs_review=review_required,
                element_type=element_type,
                character=character
            ))

            # Данные для записи в JSON
            scene_data = {
                "_recommendation_id": recommendation_id,
                "scene_id": scene_id,
                "scene_header": header,
                "page": scene.get("page"),
                "element_index": element_index,
                "timeline_position": timeline_position,
                "text": display_text,
                "текст_сцены": display_text,
                "risk_detected": True,
                "rating": simple_rating,
                "рейтинг": simple_rating,
                "индекс_рейтинга": rating_index,
                "категория": predicted_category,
                "category_id": predicted_category,
                "category_label": category_label(predicted_category),
                "primary_category": predicted_category,
                "primary_category_label": category_label(predicted_category),
                "secondary_categories": secondary_categories,
                "category_labels": {
                    category: category_label(category)
                    for category in [predicted_category, *secondary_categories]
                },
                "level": predicted_level,
                "уровень": predicted_level,
                "level_label": level_label(predicted_level),
                "target_rating": target_rating,
                "confidence": {
                    "category": prediction["category_confidence"],
                    "level": prediction["level_confidence"],
                    "rating": prediction["rating_confidence"],
                },
                "category_scores": cat_scores,
                "evidence": evidence,
                "evidence_meta": {
                    "matched_terms": matched_terms_by_category,
                    "rule_scores": natasha.get("category_scores", {}) if isinstance(natasha, dict) else {},
                    "model_category": original_model_category,
                    "guarded_model_category": prediction.get("category"),
                    "guard_reasons": guard_reasons,
                },
                "matched_terms": (
                    matched_terms_by_category.get(predicted_category, [])
                    if isinstance(natasha, dict)
                    else []
                ),
                "level_scores": prediction["level_scores"],
                "rating_scores": prediction["rating_scores"],
                "needs_review": review_required,
            }

            all_suspicious_data.append(scene_data)

    stage_t0 = time.time()
    predictions = predict_texts_batch(
        [candidate["full_text"] for candidate in rubert_candidates],
        model_path=rubert_model_dir,
        max_len=MAX_LEN,
        device=str(device),
        batch_size=RUBERT_BATCH_SIZE,
    )
    rubert_inference_seconds += time.time() - stage_t0

    for candidate, prediction in zip(rubert_candidates, predictions):
        scene = candidate["scene"]
        scene_id = candidate["scene_id"]
        header = candidate["header"]
        element_index = candidate["element_index"]
        timeline_position = candidate["timeline_position"]
        element = candidate["element"]
        text = candidate["text"]
        natasha = candidate["natasha"]
        original_model_category = prediction.get("category")
        prediction, guard_reasons = apply_evidence_guard(prediction, natasha, text)
        predicted_category, secondary_categories = resolve_category_with_rule_evidence(prediction, natasha)
        matched_terms_by_category = natasha.get("matched_terms", {}) if isinstance(natasha, dict) else {}
        predicted_level = calibrate_level_from_evidence(
            predicted_category,
            prediction["level"],
            matched_terms_by_category,
        )
        if predicted_category == "safe" or predicted_level <= 0:
            suspicious_total -= 1
            continue
        simple_rating = calculate_simple_rating(predicted_category, predicted_level)
        rating_index = get_rating_index(simple_rating)
        effective_target_rating = analysis_target_rating or target_rating_for(simple_rating)
        exceeds_target = (
            analysis_target_index is not None
            and rating_index > analysis_target_index
        )
        target_delta = rating_index - analysis_target_index if analysis_target_index is not None else 0
        should_generate_recommendation = analysis_target_rating is None or exceeds_target
        review_required = needs_human_review(prediction)
        log_event(
            logger,
            "analysis.rating_policy.completed",
            analysis_id=analysis_id,
            scene_id=scene_id,
            element_index=element_index,
            category=predicted_category,
            level=predicted_level,
            rating=simple_rating,
            needs_review=review_required,
        )

        cat_scores = prediction["category_scores"]
        element_type = element.get("type", "action")
        character = element.get("character", "")
        evidence = evidence_items(text, matched_terms_by_category)
        display_text = display_risk_text(text, evidence)

        recommendation_id = None
        if should_generate_recommendation:
            recommendation_id = f"rec-{len(recommendation_contexts) + 1}"
            recommendation_contexts.append(build_recommendation_context(
                item_id=recommendation_id,
                text=display_text,
                category=predicted_category,
                category_label=category_label(predicted_category),
                secondary_categories=secondary_categories,
                level=predicted_level,
                level_label=level_label(predicted_level),
                rating=simple_rating,
                target_rating=effective_target_rating,
                evidence=evidence,
                confidence={
                    "category": prediction["category_confidence"],
                    "level": prediction["level_confidence"],
                    "rating": prediction["rating_confidence"],
                },
                needs_review=review_required,
                element_type=element_type,
                character=character
            ))

        scene_data = {
            "_recommendation_id": recommendation_id,
            "scene_id": scene_id,
            "scene_header": header,
            "page": scene.get("page"),
            "element_index": element_index,
            "timeline_position": timeline_position,
            "text": display_text,
            "\u0442\u0435\u043a\u0441\u0442_\u0441\u0446\u0435\u043d\u044b": display_text,
                "С‚РµРєСЃС‚_СЃС†РµРЅС‹": display_text,
            "risk_detected": True,
            "rating": simple_rating,
            "\u0440\u0435\u0439\u0442\u0438\u043d\u0433": simple_rating,
            "\u0438\u043d\u0434\u0435\u043a\u0441_\u0440\u0435\u0439\u0442\u0438\u043d\u0433\u0430": rating_index,
            "\u043a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u044f": predicted_category,
            "СЂРµР№С‚РёРЅРі": simple_rating,
            "РёРЅРґРµРєСЃ_СЂРµР№С‚РёРЅРіР°": rating_index,
            "РєР°С‚РµРіРѕСЂРёСЏ": predicted_category,
            "category_id": predicted_category,
            "category_label": category_label(predicted_category),
            "primary_category": predicted_category,
            "primary_category_label": category_label(predicted_category),
            "secondary_categories": secondary_categories,
            "category_labels": {
                category: category_label(category)
                for category in [predicted_category, *secondary_categories]
            },
            "level": predicted_level,
            "\u0443\u0440\u043e\u0432\u0435\u043d\u044c": predicted_level,
            "СѓСЂРѕРІРµРЅСЊ": predicted_level,
            "level_label": level_label(predicted_level),
            "target_rating": effective_target_rating,
            "analysis_target_rating": analysis_target_rating,
            "exceeds_target": exceeds_target,
            "target_delta": target_delta,
            "recommendation_skipped_reason": None if should_generate_recommendation else "within_target",
            "confidence": {
                "category": prediction["category_confidence"],
                "level": prediction["level_confidence"],
                "rating": prediction["rating_confidence"],
            },
            "category_scores": cat_scores,
            "evidence": evidence,
            "evidence_meta": {
                "matched_terms": matched_terms_by_category,
                "rule_scores": natasha.get("category_scores", {}) if isinstance(natasha, dict) else {},
                "model_category": original_model_category,
                "guarded_model_category": prediction.get("category"),
                "guard_reasons": guard_reasons,
            },
            "matched_terms": (
                matched_terms_by_category.get(predicted_category, [])
                if isinstance(natasha, dict)
                else []
            ),
            "level_scores": prediction["level_scores"],
            "rating_scores": prediction["rating_scores"],
            "needs_review": review_required,
        }
        all_suspicious_data.append(scene_data)

    stage_t0 = time.time()
    recommendation_packages = generate_recommendation_packages_batch(recommendation_contexts)
    recommendation_seconds += time.time() - stage_t0
    for scene_data in all_suspicious_data:
        recommendation_id = scene_data.pop("_recommendation_id", None)
        recommendation_package = recommendation_packages.get(recommendation_id) if recommendation_id else None
        if not recommendation_package:
            scene_data.update({
                "\u0440\u0435\u043a\u043e\u043c\u0435\u043d\u0434\u0430\u0446\u0438\u0438_\u043f\u043e\u043d\u0438\u0436\u0435\u043d\u0438\u044f": "",
                "СЂРµРєРѕРјРµРЅРґР°С†РёРё_РїРѕРЅРёР¶РµРЅРёСЏ": "",
                "recommendation": None,
                "llm_recommendation": None,
                "fallback_used": False,
                "fallback_reason": None,
                "llm_error": None,
                "legal_context": None,
                "policy_basis": None,
                "grouped_recommendation_id": None,
                "grouped_recommendation_ids": None,
            })
            drop_mojibake_keys(scene_data)
            continue
        if recommendation_package["fallback_used"]:
            record_fallback(recommendation_package["fallback_reason"])
            log_event(
                logger,
                "analysis.recommendation.fallback",
                analysis_id=analysis_id,
                scene_id=scene_data.get("scene_id"),
                element_index=scene_data.get("element_index"),
                reason=recommendation_package["fallback_reason"],
            )
        scene_data.update({
            "\u0440\u0435\u043a\u043e\u043c\u0435\u043d\u0434\u0430\u0446\u0438\u0438_\u043f\u043e\u043d\u0438\u0436\u0435\u043d\u0438\u044f": recommendation_package["text"],
            "рекомендации_понижения": recommendation_package["text"],
            "recommendation": recommendation_package["recommendation"],
            "llm_recommendation": recommendation_package["llm_recommendation"],
            "fallback_used": recommendation_package["fallback_used"],
            "fallback_reason": public_fallback_reason(recommendation_package["fallback_reason"]) if recommendation_package["fallback_reason"] else None,
            "llm_error": public_fallback_reason(recommendation_package["llm_error"]) if recommendation_package["llm_error"] else None,
            "legal_context": recommendation_package["legal_context"],
            "policy_basis": recommendation_package["policy_basis"],
            "grouped_recommendation_id": recommendation_package.get("grouped_recommendation_id"),
            "grouped_recommendation_ids": recommendation_package.get("grouped_recommendation_ids"),
        })
        drop_mojibake_keys(scene_data)

    fallback_summary = summarize_fallback_reasons(all_suspicious_data)
    group_ids = {
        item.get("grouped_recommendation_id")
        for item in all_suspicious_data
        if item.get("grouped_recommendation_id")
    }
    fallback_group_ids = {
        item.get("grouped_recommendation_id") or f"fallback-{item.get('scene_id')}-{item.get('element_index')}"
        for item in all_suspicious_data
        if item.get("fallback_used")
    }
    target_blocking_data = [
        item for item in all_suspicious_data
        if item.get("exceeds_target") is True
    ]
    target_compliant_count = (
        sum(1 for item in all_suspicious_data if item.get("exceeds_target") is False)
        if analysis_target_rating
        else 0
    )
    recommendation_skipped_within_target = sum(
        1 for item in all_suspicious_data
        if item.get("recommendation_skipped_reason") == "within_target"
    )

    # Если нет подозрительных — выходим
    stage_timings["rubert_inference"] = round(rubert_inference_seconds, 3)
    stage_timings["recommendations"] = round(recommendation_seconds, 3)
    stage_timings["total"] = _elapsed(t0)
    record_stage_timing("rubert_inference", stage_timings["rubert_inference"])
    record_stage_timing("recommendations", stage_timings["recommendations"])
    record_stage_timing("total", stage_timings["total"])
    log_event(logger, "analysis.stage.completed", stage="rubert_inference", seconds=stage_timings["rubert_inference"])
    log_event(logger, "analysis.stage.completed", stage="recommendations", seconds=stage_timings["recommendations"])
    record_analysis_completed(
        suspicious_count=len(all_suspicious_data),
        duration_seconds=stage_timings["total"],
    )
    log_event(
        logger,
        "analysis.pipeline.completed",
        analysis_id=analysis_id,
        request_id=request_id,
        suspicious_count=len(all_suspicious_data),
        total_elements=total,
        seconds=stage_timings["total"],
    )
    metadata = _analysis_metadata(
        rubert_model_dir=rubert_model_dir,
        analysis_id=analysis_id,
        request_id=request_id,
        stage_timings=stage_timings,
        analysis_target_rating=analysis_target_rating,
    )
    metadata["fallback_summary"] = fallback_summary
    metadata["target_blocking_count"] = len(target_blocking_data) if analysis_target_rating else None
    metadata["target_compliant_risk_count"] = target_compliant_count
    metadata["llm_recommendation_total"] = len(recommendation_contexts)
    metadata["llm_recommendation_fallback_count"] = fallback_summary["total"]
    metadata["llm_recommendation_skipped_because_within_target"] = recommendation_skipped_within_target
    metadata["llm_recommendation_mode"] = recommendation_mode()
    metadata["llm_recommendation_group_count"] = len(group_ids)
    metadata["llm_recommendation_group_fallback_count"] = len(fallback_group_ids)

    if not all_suspicious_data:
        print("Нет подозрительных сцен для обработки")
        return {
            "обработанные_сцены": [],
            "статистика": {
                "всего_элементов": total,
                "всего_подозрительных": 0,
                "максимальный_рейтинг": "0+",
                "время_обработки": round(time.time() - t0, 1)
            },
            "metadata": metadata,
        }

    print(f"✅ Найдено подозрительных элементов: {len(all_suspicious_data)}")

    # === ФАЙЛ 1: Все подозрительные сцены ===
    out_all = {
        "все_подозрительные_сцены": all_suspicious_data,
        "статистика": {
            "всего_элементов": total,
            "обработано_подозрительных": len(all_suspicious_data),
            "время_обработки": round(time.time() - t0, 1)
        },
        "metadata": metadata,
    }

    # === ФАЙЛ 2: Только сцены с МАКСИМАЛЬНЫМ рейтингом ===
    max_rating_index = max(item["индекс_рейтинга"] for item in all_suspicious_data)
    max_rating_scenes = [
        item for item in all_suspicious_data
        if item["индекс_рейтинга"] == max_rating_index
    ]

    max_rating_str = RATING_ORDER[max_rating_index]

    rating_aggregation = aggregate_project_rating(all_suspicious_data)
    max_rating_index = rating_aggregation["rating_index"]
    max_rating_scenes = [
        item for item in all_suspicious_data
        if item.get(RATING_INDEX_KEY) == max_rating_index
    ]
    max_rating_str = rating_aggregation["rating"]
    metadata["rating_aggregation"] = rating_aggregation
    metadata["fallback_summary"] = fallback_summary
    metadata["target_blocking_count"] = len(target_blocking_data) if analysis_target_rating else None
    metadata["target_compliant_risk_count"] = target_compliant_count
    metadata["llm_recommendation_total"] = len(recommendation_contexts)
    metadata["llm_recommendation_fallback_count"] = fallback_summary["total"]
    metadata["llm_recommendation_skipped_because_within_target"] = recommendation_skipped_within_target
    metadata["llm_recommendation_mode"] = recommendation_mode()
    metadata["llm_recommendation_group_count"] = len(group_ids)
    metadata["llm_recommendation_group_fallback_count"] = len(fallback_group_ids)

    out_max = {
        "обработанные_сцены": all_suspicious_data,
        "сцены_с_максимальным_рейтингом": max_rating_scenes,
        "все_подозрительные_сцены": all_suspicious_data,
        "статистика": {
            "всего_подозрительных": len(all_suspicious_data),
            "обработано_подозрительных": len(all_suspicious_data),
            "сцен_с_максимальным_рейтингом": len(max_rating_scenes),
            "сцен_требующих_проверки": sum(1 for item in all_suspicious_data if item.get("needs_review")),
            "максимальный_рейтинг": max_rating_str,
            "время_обработки": round(time.time() - t0, 1)
        },
        "metadata": metadata,
    }

    dt = time.time() - t0
    print(f"Готово. Общее время: {dt:.1f} сек.")
    return out_max


def process_script(
    input_path: str = INPUT_SCRIPT,
    output_all: str = OUTPUT_ALL,
    output_max: str = OUTPUT_MAX,
    rubert_model_dir: str = RUBERT_MODEL_DIR,
    analysis_id: str | None = None,
    request_id: str | None = None,
    target_rating: str | None = None,
):
    """
    Функция для запуска пайплайна с переданными параметрами.

    Args:
        input_path (str): Путь к .docx или .pdf файлу.
        output_all (str): Куда сохранить все подозрительные сцены.
        output_max (str): Куда сохранить сцены с максимальным рейтингом.
        rubert_model_dir (str): Путь к папке с моделью RuBERT.
    """
    return run_pipeline(
        str(input_path),
        str(output_all),
        str(output_max),
        str(rubert_model_dir),
        analysis_id=analysis_id,
        request_id=request_id,
        target_rating=target_rating,
    )


if __name__ == "__main__":
    process_script(
        input_path="Трек 3 - тестовый образец.docx",
        output_all="all_suspicious.json",
        output_max="max_rating_scenes.json",
        rubert_model_dir="trained_model"
    )
