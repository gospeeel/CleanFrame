# Backlog V1.1 И V2

## V1.1

Цель V1.1: стабилизировать локальный E2E после ручных проверок и убрать legacy-слои из runtime.

- API: backend-to-LLM использует только `POST /api/analysis/run`; старый прямой LLM route удалён.
- Форматы: `.pdf`, `.docx`, `.txt` поддерживаются в backend и Python одинаково. `.doc` остаётся вне acceptance до выбора converter.
- Качество: расширить `golden/regression.jsonl` до 50-80 проверенных примеров, добавить false-positive кейсы и проверку `expected_evidence`.
- UX: явно показывать `target_rating`, evidence и варианты `было/стало`; diagnostic-поля не должны шуметь в пользовательском отчёте.
- Operations: расширенный `/api/analysis/health`, таймауты, понятные ошибки при недоступном RuBERT/LLM service, логирование `analysisId`, metadata модели и fallback reason.
- Acceptance: regression `failed = 0`, E2E проходит на `.pdf/.docx/.txt`, fallback без Ollama работает, технические labels не видны пользователю.

## V2

Цель V2: production-grade LLM service с устойчивой очередью, evaluation pipeline, lifecycle моделей и возможным fine-tune Qwen только для рекомендаций.

- Architecture: заменить in-process worker на durable queue, разделить API service и worker, добавить retry/dead-letter/cancellation.
- Observability: structured logs, metrics, tracing, latency breakdown, model/policy/taxonomy metadata в каждом result.
- Package cleanup: физически разнести runtime-код по `api`, `pipeline`, `parsing`, `detection`, `classification`, `recommendations`, `legal`, `core`, `tools`.
- Dataset: довести golden до 200-500 проверенных примеров, выделить regression/recommendations/holdout/silver и добавить CI gate.
- Qwen fine-tune: делать LoRA/SFT только на structured recommendation examples; rating/category остаются deterministic.
- Legal/RAG: версионировать policy, расширить локальную legal knowledge base, добавить retrieval по category + level + evidence.
- Security: не хранить исходные файлы, настроить retention истории, добавить audit log для production-событий.
- Acceptance: очередь переживает restart, анализ не теряется при падении процесса, fine-tuned Qwen улучшает recommendation score на holdout, legacy wrappers удалены.
