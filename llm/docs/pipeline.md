# Pipeline Анализа

## 1. Parsing

`parse_script()` извлекает сцены и элементы из `.docx`/`.pdf`/`.txt`. Важно сохранять границу между репликой и действием: action-строки не должны приклеиваться к предыдущему персонажу.

Для `.txt` без явного заголовка сцены сервис добавляет технический заголовок на этапе parsing, чтобы ручные smoke-файлы не отбрасывались целиком.

## 2. Risk Detection

`is_suspicious_scene()` ищет первичные сигналы риска по curated lexicon и yargy-правилам. Результат содержит:

- `is_suspicious`
- `normalized_flags`
- `category_scores`
- `matched_terms`

Для бытовых контекстов есть safe exceptions: например `ударил по мячу`, `страшно опоздать`, `ножом для торта`.

## 3. Classification

RuBERT возвращает category/level/rating scores. Затем deterministic policy выбирает `primary_category` по evidence-score и precedence. Если rules явно видят драку, `violence` должен стать primary даже при слабом model-сигнале `fear`.

## 4. Rating Policy

`rating.calculate_rating()` и `legal_policy.calculate_simple_rating()` определяют возрастной рейтинг. LLM не участвует в этом решении.

## 5. Recommendations

`recommendation_service` передаёт Qwen только уже рассчитанные факты: category, labels, level, rating, target_rating, evidence и legal context. Если Qwen недоступна, JSON невалиден или self-check провален, используется deterministic fallback.

## 6. Response

Каждая risky-сцена возвращает старые поля для совместимости и новые поля:

- `risk_detected`
- `primary_category`
- `primary_category_label`
- `secondary_categories`
- `level_label`
- `target_rating`
- `evidence`
- `recommendation`
