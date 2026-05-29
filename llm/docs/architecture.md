# Архитектура LLM-сервиса

`llm` отвечает за локальный анализ сценариев и не принимает пользовательских решений о доступе или хранении истории. Историю анализов хранит backend, а Python-сервис возвращает только результат анализа конкретного файла.

## Runtime-путь

1. `main.py` поднимает FastAPI и подключает router.
2. `llm.service.run_analysis()` принимает `.docx/.pdf/.txt`, сохраняет временный файл и вызывает pipeline.
3. `llm.pipeline.full_pipeline.process_script()` оркестрирует анализ:
   - парсинг документа;
   - rule-based detection;
   - RuBERT classification;
   - deterministic rating policy;
   - локальные Qwen-рекомендации через Ollama;
   - fallback, если Qwen недоступна.
4. Исходный upload-файл удаляется в `finally`.

## Целевая структура

Пакеты `api`, `pipeline`, `parsing`, `detection`, `classification`, `recommendations`, `legal`, `core`, `tools` являются публичными зонами ответственности. Runtime-код физически разнесён по этим пакетам; исследовательские и training CLI находятся в `llm.tools`.

## Границы ответственности

- Rules/RuBERT/rating policy определяют риск, категорию, уровень и рейтинг.
- Qwen генерирует объяснения и редакторские варианты замены.
- Qwen не может менять `primary_category`, `level`, `rating`, `needs_review`.
- Frontend показывает нормализованные русские labels, а не технические ключи.

## Что не должно попадать в git

`.venv`, `__pycache__`, `uploads`, `outputs`, локальные отчёты, временные модели и runtime-файлы. Они уже закрыты `.gitignore`; при необходимости их можно удалить локально без изменения исходного кода.
