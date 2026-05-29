# Backlog V1.1 И V2 Для LLM-Сервиса

## Summary
V1.1 — стабилизационный релиз после ручного E2E: убрать legacy API, расширить форматы/качество, улучшить наблюдаемость и удобство разработки.

V2 — почти финальная версия LLM-сервиса: отдельный production-grade analysis service с очередью, evaluation pipeline, расширенным golden dataset, подготовкой/дообучением Qwen для рекомендаций и полноценной архитектурой без legacy-слоёв.

`/api/llm/send` больше не считаем нужным даже как deprecated endpoint: в V1.1 заменяем его на нормальный service endpoint и удаляем старый путь.

## Open TODO По Текущему Состоянию

Ниже только то, что осталось доделать после текущей реализации. На момент ревизии уже есть `POST /api/analysis/run`, поддержка `.pdf/.docx/.txt`, backend BullMQ/Redis queue, Sentry во frontend/backend, `/api/analysis/health`, fallback без Ollama и golden regression `28/28 failed=0`.

### V1.1 Closure TODO

- [ ] Расширить `llm/datasets/golden/regression.jsonl` с 28 до 50-80 ручных проверенных примеров.
- [ ] Добавить больше false-positive кейсов:
  - [ ] бытовое/спортивное насилие без риска;
  - [ ] бытовая тревога без horror/fear риска;
  - [ ] нейтральные слова, похожие на substance/sexual terms;
  - [ ] семейная/романтическая сцена без сексуализированной подачи.
- [ ] Добавить реальные ручные фрагменты из собственных сценариев без копирования чужих защищённых текстов.
- [ ] Прогнать ручной E2E на `.pdf`, `.docx`, `.txt` и зафиксировать результат в `llm/docs/v1-e2e.md`.
- [ ] Проверить вручную, что `/api/llm/send` возвращает 404 в Python и backend runtime.
- [ ] Проверить fallback-сценарий при выключенной или недоступной Ollama.
- [ ] Проверить сценарий недоступной RuBERT-модели и текст ошибки для пользователя.
- [ ] Убедиться, что `self_check_passed` не показывается как пользовательский шум во всех frontend-состояниях.
- [x] Добавить локальный gate-скрипт для `python -m llm.evaluate_golden`: `scripts/verify-llm.sh`.
- [x] Подключить `scripts/verify-llm.sh` к реальному CI, чтобы merge блокировался при `failed > 0`.
- [x] Добавить CI/скрипт для минимального набора проверок:
  - [x] Python compile/unit/golden;
  - [x] backend build;
  - [x] frontend typecheck/build.

### Observability TODO

- [x] Расширить Sentry/observability на Python LLM service.
- [x] Протянуть `x-request-id`/`analysisId` из backend queue в Python `/api/analysis/run`.
- [x] Добавить structured logs в Python по этапам:
  - [x] upload validation;
  - [x] parsing;
  - [x] rule-based detection;
  - [x] RuBERT inference;
  - [x] rating policy;
  - [x] Qwen recommendation;
  - [x] fallback.
- [x] Добавить latency breakdown по этапам анализа в result или diagnostic metadata.
- [x] Логировать `fallback_reason` отдельно от общего `llm_error`.
- [x] Добавить счётчики/метрики:
  - [x] сколько анализов завершилось fallback;
  - [x] сколько ошибок RuBERT/Ollama;
  - [x] длительность inference;
  - [x] количество suspicious elements на анализ.
- [x] Добавить model/policy/taxonomy metadata в каждый analysis result:
  - [x] `rubert_model_name`;
  - [x] `rubert_model_version` или hash весов;
  - [x] `qwen_model`;
  - [x] `policy_version`;
  - [x] `taxonomy_version`.
- [ ] Расширить Sentry-контекст для backend queue/worker:
  - [ ] добавлять `analysisId`, `queueJobId`, `workerId`, `attemptsMade`, `maxAttempts` в Sentry scope/tags;
  - [ ] добавлять Sentry breadcrumbs для стадий `queued`, `processing`, `retry`, `dead-letter`, `done`;
  - [ ] явно отправлять `captureException` при переводе job в `DEAD_LETTER`;
  - [ ] связать trace `frontend -> backend API -> Redis/BullMQ job -> backend-worker -> Python LLM`;
  - [ ] проверить, что Sentry events не содержат исходный текст сценария и содержимое загруженного файла.

### V2 Architecture TODO

- [x] Разделить backend API process и backend worker process на уровне deploy/runtime, даже если кодовые классы уже разделены.
- [x] Добавить явный dead-letter статус или dead-letter handling для analysis jobs.
- [x] Добавить тест, что queue переживает restart backend/worker.
- [x] Добавить тест, что analysis не теряется при падении worker process.
- [x] Добавить load test на несколько параллельных анализов.
- [x] Сформулировать границу ответственности Python service:
  - [x] оставить Python синхронным internal analysis endpoint;
  - [x] backend durable queue остаётся владельцем retries/dead-letter/cancellation.

  ### LLM Package Cleanup TODO

- [x] Физически перенести runtime-код в целевые пакеты:
  - [x] `llm/api`;
  - [x] `llm/pipeline`;
  - [x] `llm/parsing`;
  - [x] `llm/detection`;
  - [x] `llm/classification`;
  - [x] `llm/recommendations`;
  - [x] `llm/legal`;
  - [x] `llm/core`;
  - [x] `llm/tools`.
- [x] Переходный этап со старыми модулями (`full_pipeline.py`, `parser.py`, `predict_new.py`, `main_natasha_filter.py`, `recommendation_service.py`) завершён.
- [x] Удалить thin wrappers после обновления импортов и тестов.
- [x] Разобраться с историческим названием `main_natasha_filter.py`: модуль удалён, runtime использует `llm.detection.rule_detector`.
- [x] Вынести research/training scripts из runtime package:
  - [x] `rubert_models/train_model.py` -> `llm.tools.experiments.rubert_train_model`;
  - [x] `rubert_models/predict_rubert.py` -> `llm.tools.experiments.rubert_predict`;
  - [x] экспериментальные генераторы датасетов -> `llm.tools.datasets`.
- [x] Удалить или перенести legacy wrapper `rag_law.py`.
- [x] Убрать старые example/runtime artifacts из package tree.

### Dataset And Evaluation TODO

- [ ] Довести human-labeled golden dataset до 200-500 проверенных примеров.
- [ ] Разделить datasets:
  - [ ] `golden/regression`;
  - [ ] `golden/recommendations`;
  - [ ] `eval/holdout`;
  - [ ] `silver`.
- [x] Добавить full-pipeline evaluation, а не только deterministic rules evaluation.
- [ ] Добавить RuBERT evaluation gate:
  - [ ] category accuracy;
  - [ ] level accuracy/MAE;
  - [ ] rating accuracy;
  - [ ] confidence calibration.
- [ ] Исправить качество RuBERT/rating на full-pipeline golden:
  - [ ] текущий замер `python -m llm.evaluate_golden --mode pipeline`: `rating_accuracy = 0.4286` (`12/28 passed`, `16/28 failed`);
  - [ ] category/evidence/risk сейчас проходят (`1.0`), основной провал именно в rating/level;
  - [ ] разобрать failed cases по категориям violence/fear/profanity/substance/sexual;
  - [ ] решить, исправлять через level calibration, deterministic rating override по evidence-score или дообучение RuBERT;
  - [ ] довести full-pipeline `rating_accuracy` до согласованного threshold перед включением в обязательный CI gate.
- [ ] Добавить evidence quality evaluation:
  - [ ] expected evidence terms;
  - [ ] evidence snippets;
  - [ ] false-positive/false-negative evidence.
- [ ] Добавить recommendation quality evaluation:
  - [ ] schema validity;
  - [ ] соответствие primary category;
  - [ ] наличие 3 редакторских правок;
  - [ ] качество `before/after`;
  - [ ] отсутствие попытки менять rating/category.
- [ ] Сохранять evaluation reports в стабильную папку `llm/reports` или CI artifacts.

### Qwen Fine-Tune TODO

- [ ] Накопить 200-500 проверенных recommendation examples до начала fine-tune.
- [ ] Подготовить SFT/LoRA dataset:
  - [ ] input facts из rating engine;
  - [ ] legal context;
  - [ ] expected structured recommendation;
  - [ ] self-check target.
- [ ] Зафиксировать правило: Qwen не принимает решения по rating/category.
- [ ] Подготовить training script для LoRA/SFT.
- [ ] Подготовить inference config для fine-tuned Qwen.
- [ ] Сравнить base Qwen vs fine-tuned Qwen на holdout.
- [ ] Оставить schema validation, self-check и deterministic fallback обязательными после fine-tune.

### Legal/RAG TODO

- [x] Расширить локальную legal knowledge base.
- [x] Добавить `policy_version`.
- [x] Добавить retrieval по `category + level + evidence`, а не только по category.
- [x] Добавить базовый тест retrieval по evidence terms.
- [x] Рассмотреть vector search только после оценки качества keyword/category retrieval: решение зафиксировано в `llm/docs/legal-rag.md`, пока оставляем проверяемый keyword/category retrieval.

### Model Lifecycle TODO

- [x] Ввести model registry или единый manifest для RuBERT/Qwen.
- [x] Хранить и возвращать:
  - [x] `model_name`;
  - [x] `model_version`;
  - [x] `weights_hash`;
  - [x] `policy_version`;
  - [x] `taxonomy_version`;
  - [x] `created_at`;
  - [ ] `evaluation_report_path`.
- [x] Добавить rollback модели.
- [ ] Добавить offline evaluation перед переключением модели.
- [ ] Добавить compare report для candidate model vs current production model.

### Security And Data Handling TODO

- [ ] Проверить, что исходные файлы удаляются после успешного анализа и после ошибки во всех ветках backend/Python.
- [ ] Добавить configurable retention для analysis history.
- [ ] Хранить только рискованные фрагменты и результат анализа, если product/legal требования не требуют иного.
- [ ] Добавить audit log для production-событий:
  - [ ] analysis created;
  - [ ] analysis cancelled;
  - [ ] analysis failed;
  - [ ] model switched;
  - [ ] policy switched;
  - [ ] retention cleanup.
- [ ] Проверить, что Sentry events не содержат исходный текст сценария, токены, cookies и authorization headers.

## V1.1 Backlog

- Заменить Python endpoint:
  - добавить `POST /api/analysis/run` в Python LLM service;
  - переименовать service-функцию `send_llm` в `run_analysis`;
  - backend `LlmService` перевести с `/api/llm/send` на `/api/analysis/run`;
  - удалить Python router `/api/llm/send`;
  - удалить/закрыть backend legacy controller `/api/llm/send`, если frontend и ручной dev-flow больше его не используют;
  - обновить README/docs: frontend только `/api/analyses`, backend-to-LLM только `/api/analysis/run`.

- Расширить поддерживаемые форматы:
  - добавить `.txt`;
  - `.doc` оставить только если будет выбран надёжный converter, иначе явно не поддерживать;
  - backend и Python должны иметь одинаковый список supported extensions.

- Улучшить V1.1 качество анализа:
  - увеличить `golden/regression.jsonl` до 50-80 проверенных примеров;
  - добавить больше false-positive кейсов;
  - добавить проверку `expected_evidence`;
  - добавить ручные реальные фрагменты из ваших сценариев без копирования чужих защищённых текстов.

- Улучшить E2E UX:
  - в UI явно показывать `target_rating`;
  - показывать `self_check_passed` только как внутренний/diagnostic marker, не как пользовательский шум;
  - сделать аккуратные empty/error states для `FAILED`;
  - добавить понятную ошибку, если LLM service или RuBERT недоступны.

- Улучшить operational readiness:
  - добавить backend timeout/status text для долгих анализов;
  - добавить `/api/analysis/health` или расширенный `/ready` в Python с Ollama/RuBERT статусом;
  - логировать `analysisId`, model metadata, fallback reason;
  - проверить, что uploads всегда удаляются после ошибки.

- V1.1 acceptance:
  - `/api/llm/send` больше не существует;
  - backend успешно вызывает `/api/analysis/run`;
  - frontend E2E работает через `/api/analyses`;
  - `.pdf`, `.docx`, `.txt` проходят ручной тест;
  - fallback без Ollama работает;
  - golden regression `failed = 0`.

## V2 Backlog

- Production architecture:
  - заменить in-process worker на Redis/BullMQ или другой durable queue;
  - добавить retry policy, dead-letter статус, cancellation;
  - разделить API service и worker process;
  - добавить structured logs, metrics, tracing, latency breakdown;
  - добавить model/version metadata в каждый analysis result.

- LLM service architecture cleanup:
  - физически перенести runtime-код в целевые пакеты:
    - `api`
    - `pipeline`
    - `parsing`
    - `detection`
    - `classification`
    - `recommendations`
    - `legal`
    - `core`
    - `tools`
  - research/training scripts вынесены в `tools/training`, `tools/datasets`, `tools/experiments`;
  - legacy wrappers вроде `rag_law.py` удалены после обновления импортов;
  - старые example/runtime artifacts убраны из package tree.

- Dataset and evaluation:
  - довести golden dataset до 200-500 проверенных примеров;
  - разделить datasets:
    - `golden/regression`
    - `golden/recommendations`
    - `eval/holdout`
    - `silver`
  - добавить отчёты по category accuracy, rating accuracy, evidence accuracy, recommendation quality;
  - добавить CI gate: regression не должен падать перед merge.

- Qwen fine-tune:
  - дообучать Qwen только на recommendation examples;
  - не переносить rating/category decision в LLM;
  - подготовить SFT/LoRA dataset с input facts и expected structured recommendation;
  - сравнить base Qwen vs fine-tuned Qwen на holdout;
  - оставить fallback и schema validation обязательными даже после fine-tune.

- RAG/legal layer:
  - расширить локальную legal knowledge base;
  - добавить версионирование policy;
  - добавить retrieval по category + level + evidence;
  - в V2 можно рассмотреть vector search, если keyword retrieval перестанет хватать.

- Model lifecycle:
  - model registry или manifest для RuBERT/Qwen;
  - хранить `model_name`, `model_version`, `policy_version`, `taxonomy_version`;
  - добавить rollback модели;
  - добавить offline evaluation перед обновлением модели.

- Security and data handling:
  - не хранить исходные файлы;
  - хранить только рискованные фрагменты и результат анализа;
  - добавить configurable retention для analysis history;
  - добавить audit log для production-событий.

- V2 acceptance:
  - queue переживает restart backend/worker;
  - analysis не теряется при падении процесса;
  - 200-500 golden examples проходят заданный threshold;
  - fine-tuned Qwen улучшает recommendation score на holdout;
  - rating/category остаются deterministic;
  - все legacy endpoints и wrappers удалены.

## API Plan

- V1.1:
  - Python:
    - удалить `POST /api/llm/send`;
    - добавить `POST /api/analysis/run`.
  - Backend:
    - `POST /api/analyses` остаётся пользовательским API;
    - backend worker вызывает `LLM_SERVICE_URL/api/analysis/run`.
  - Frontend:
    - без изменений: использует только `/api/analyses`.

- V2:
  - внешний пользовательский API остаётся backend-owned;
  - Python LLM service остаётся внутренним worker/service API;
  - публичный frontend никогда не ходит напрямую в Python.

## Test Plan

- V1.1:
  - Python compile/unit/golden;
  - backend build;
  - frontend typecheck/build;
  - ручной E2E `.pdf`, `.docx`, `.txt`;
  - fallback без Ollama;
  - проверка, что `/api/llm/send` возвращает 404.

- V2:
  - queue restart test;
  - worker retry/failure test;
  - holdout evaluation;
  - Qwen base vs fine-tuned comparison;
  - load test на несколько параллельных анализов;
  - retention/privacy checks.

## Assumptions

- `/api/llm/send` можно удалить в V1.1 без внешней совместимости.
- Frontend уже не зависит от `/api/llm/send`.
- Backend остаётся единственным публичным API для пользовательского анализа.
- Fine-tune Qwen делаем только после накопления качественного recommendation dataset.
- V2 не обязан менять продуктовый UX радикально; основной фокус V2 — надёжность, качество и lifecycle моделей.
