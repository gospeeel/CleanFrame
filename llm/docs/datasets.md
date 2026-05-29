# Datasets And Evaluation

## Golden Dataset

Golden-примеры лежат в `datasets/golden`. Это ручные regression-кейсы, которые нельзя ломать при изменении rules, taxonomy или prompt.

Минимальная строка:

```json
{
  "id": "golden-violence-001",
  "text": "Завязывается короткая драка, слышен удар...",
  "expected_primary_category": "violence",
  "expected_secondary_categories": [],
  "expected_level": 2,
  "expected_rating": "12+",
  "expected_risk_detected": true,
  "notes": "Физическое насилие без крови."
}
```

## Как запускать

Из папки `llm`:

```bash
./.venv/bin/python -m llm.evaluate_golden
```

Отчёт показывает:

- risk detection accuracy;
- category accuracy;
- rating accuracy;
- список failures.

## Silver Dataset

Silver-данные можно использовать для экспериментов, но они не должны быть acceptance-критерием. Production-изменения проверяются golden-набором.

## Генерация кандидатов по всем категориям

Для расширения набора используйте кандидаты, а не чужие сценарии целиком:

```bash
./.venv/bin/python -m llm.tools.generate_golden_candidates --count-per-category 10
```

Если локальная Qwen доступна:

```bash
OLLAMA_BASE_URL=http://127.0.0.1:11434 \
OLLAMA_MODEL=qwen2.5:3b-instruct \
./.venv/bin/python -m llm.tools.generate_golden_candidates --use-ollama --count-per-category 10
```

Команда пишет `datasets/golden/candidates.generated.jsonl`. Этот файл намеренно не коммитится: строки из него нужно вручную проверить и только потом переносить в `datasets/golden/regression.jsonl`.

Категории, которые должны быть покрыты в golden:

- `violence`
- `fear`
- `profanity`
- `substance`
- `sexual`
- `safe`

Для каждой risky-категории нужны положительные примеры разных уровней и negative cases, где похожие слова не должны срабатывать.
