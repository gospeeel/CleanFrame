# ML_WINK LLM Service

Локальный FastAPI-сервис анализа сценариев. Сервис принимает `.docx/.pdf/.txt`, выделяет рискованные фрагменты, определяет категорию/уровень/рейтинг через deterministic policy и RuBERT, а затем просит локальную Qwen через Ollama сформировать редакторские рекомендации.

## Главное

- LLM не принимает решение о рейтинге.
- Qwen используется только для объяснений и вариантов замены.
- При недоступной Ollama сервис возвращает fallback-рекомендации.
- Runtime upload-файлы удаляются после обработки.

## Документация

- `docs/architecture.md` — архитектура и зоны ответственности.
- `docs/pipeline.md` — полный pipeline анализа.
- `docs/recommendations.md` — Qwen JSON Schema, fallback и self-check.
- `docs/datasets.md` — golden/silver datasets и evaluation.
- `docs/local-dev.md` — локальный запуск и частые ошибки.
- `docs/v1-e2e.md` — v1.1 acceptance checklist и ручной E2E-сценарий.
- `docs/backlog.md` — backlog v1.1/v2.

## Быстрый запуск

```bash
cd llm
source .venv/bin/activate

LLM_RECOMMENDATIONS_ENABLED=true \
OLLAMA_BASE_URL=http://127.0.0.1:11434 \
OLLAMA_MODEL=qwen2.5:3b-instruct \
python -m uvicorn main:app --host 127.0.0.1 --port 8001
```

## Проверки

```bash
python3 -m compileall llm tests
./.venv/bin/python -m unittest tests.test_taxonomy
./.venv/bin/python -m llm.evaluate_golden
```

## V1.1 Checklist

- Frontend использует backend `/api/analyses`.
- Backend сохраняет async analysis job и результат в истории.
- Backend вызывает Python через `POST /api/analysis/run`.
- Старый прямой LLM endpoint удалён.
- Поддерживаемые форматы v1.1: `.pdf`, `.docx`, `.txt`.
- Golden regression должен проходить с `failed = 0`.
- Qwen генерирует рекомендации, но не меняет рейтинг.
- При недоступной Ollama используется fallback.
