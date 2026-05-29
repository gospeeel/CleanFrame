import json
import logging
import os
import time
from datetime import datetime, timezone

from llm.classification.rubert import get_model_manifest, load_model_and_tokenizer, predict_text
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
from llm.recommendations.service import generate_recommendation_package
from llm.rating import RATING_ORDER, get_rating_index
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

# ----------------- CONFIG -----------------
INPUT_SCRIPT = ".docx"
OUTPUT_ALL = OUTPUTS_DIR / "all_suspicious.json"
OUTPUT_MAX = OUTPUTS_DIR / "max_rating_scenes.json"
RUBERT_MODEL_DIR = DEFAULT_MODEL_DIR
MAX_LEN = 256
def resolve_category_with_rule_evidence(prediction: dict, natasha: dict) -> tuple[str, list[str]]:
    predicted_category = prediction["category"]
    return primary_category_from_evidence(predicted_category, natasha)


def target_rating_for(rating: str) -> str:
    rating_index = get_rating_index(rating)
    if rating_index <= 0:
        return "0+"
    return RATING_ORDER[max(0, rating_index - 1)]

def _elapsed(t0: float) -> float:
    return round(time.time() - t0, 3)


def _analysis_metadata(
    rubert_model_dir,
    analysis_id: str | None,
    request_id: str | None,
    stage_timings: dict[str, float],
) -> dict:
    manifest = get_model_manifest(rubert_model_dir)
    weights = manifest.get("weights", {}) if isinstance(manifest, dict) else {}
    rubert_registry = active_model_metadata("rubert")
    qwen_registry = active_model_metadata("qwen")
    return {
        "analysis_id": analysis_id,
        "request_id": request_id,
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
):
    t0 = time.time()
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

            # --- RuBERT inference ---
            stage_t0 = time.time()
            prediction = predict_text(
                full_text,
                model_path=rubert_model_dir,
                max_len=MAX_LEN,
                device=str(device),
            )
            rubert_inference_seconds += time.time() - stage_t0
            predicted_category, secondary_categories = resolve_category_with_rule_evidence(prediction, natasha)
            predicted_level = prediction["level"]

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

            # Генерация рекомендаций
            stage_t0 = time.time()
            recommendation_package = generate_recommendation_package(
                text=text,
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
            )
            recommendation_seconds += time.time() - stage_t0
            if recommendation_package["fallback_used"]:
                record_fallback(recommendation_package["fallback_reason"])
                log_event(
                    logger,
                    "analysis.recommendation.fallback",
                    analysis_id=analysis_id,
                    scene_id=scene_id,
                    element_index=element_index,
                    reason=recommendation_package["fallback_reason"],
                )

            # Данные для записи в JSON
            scene_data = {
                "scene_id": scene_id,
                "scene_header": header,
                "page": scene.get("page"),
                "element_index": element_index,
                "timeline_position": timeline_position,
                "text": text,
                "текст_сцены": text,
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
                    "model_category": prediction.get("category"),
                },
                "matched_terms": (
                    matched_terms_by_category.get(predicted_category, [])
                    if isinstance(natasha, dict)
                    else []
                ),
                "level_scores": prediction["level_scores"],
                "rating_scores": prediction["rating_scores"],
                "needs_review": review_required,
                "рекомендации_понижения": recommendation_package["text"],
                "recommendation": recommendation_package["recommendation"],
                "llm_recommendation": recommendation_package["llm_recommendation"],
                "fallback_used": recommendation_package["fallback_used"],
                "fallback_reason": recommendation_package["fallback_reason"],
                "llm_error": recommendation_package["llm_error"],
                "legal_context": recommendation_package["legal_context"],
                "policy_basis": recommendation_package["policy_basis"],
            }

            all_suspicious_data.append(scene_data)

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
    )

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
    )


if __name__ == "__main__":
    process_script(
        input_path="Трек 3 - тестовый образец.docx",
        output_all="all_suspicious.json",
        output_max="max_rating_scenes.json",
        rubert_model_dir="trained_model"
    )
