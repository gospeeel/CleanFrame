# Qwen Recommendations

Qwen используется как локальный редакторский ассистент. Она не классифицирует сцену и не меняет рейтинг.

## Input

В prompt передаются:

- исходный фрагмент;
- `primary_category_id` и `primary_category_label`;
- `secondary_categories`;
- `level`, `level_label`, `rating`, `target_rating`;
- `needs_review`;
- `confidence`;
- `evidence`;
- локальный legal policy context.

## Output Schema

```json
{
  "summary": "Насилие: требуется смягчить прямое описание удара.",
  "explanation": "Фрагмент содержит физический конфликт...",
  "risk_factors": ["короткая драка", "слышен удар"],
  "rewrite_suggestions": [
    {
      "goal": "Мягкая правка",
      "before": "слышен удар, незнакомец падает на пол",
      "after": "слышен шум борьбы, незнакомец отступает к стене",
      "rationale": "Убрано прямое описание удара и падения",
      "expected_effect": "Может снизить интенсивность сцены"
    }
  ],
  "self_check_passed": true,
  "uncertainty_note": null
}
```

## Fallback

Fallback используется, если:

- Ollama недоступна;
- Qwen вернула невалидный JSON;
- schema validation не прошла;
- self-check показал несоответствие primary category.

Fallback всегда возвращает структурированные варианты правки, чтобы frontend не зависел от доступности Qwen.

## Fine-tune Policy

Дообучение Qwen не входит в v1. Для v1 golden dataset используется как regression-набор качества. Fine-tune рассматривается для v2 после накопления 200-500 проверенных примеров рекомендаций. Fine-tune должен улучшать стиль и формат рекомендаций, но не должен переносить рейтинг в LLM.
