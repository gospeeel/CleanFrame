# V1.1 E2E Checklist

V1.1 фиксирует локальный поток:

```text
upload -> backend analysis job -> Python LLM service -> rules/RuBERT -> Qwen recommendations/fallback -> saved report -> history -> reopen
```

Backend ставит анализы в Redis/BullMQ queue. Worker обрабатывает job, вызывает Python service и создаёт in-app notification после терминального статуса.

## Scope

Поддерживаемые форматы v1.1:

- `.pdf`
- `.docx`
- `.txt`

`.doc` не входит в acceptance v1.1: для него нужен отдельный надёжный converter.

## API Boundaries

- Frontend использует только backend `/api/analyses`.
- Backend вызывает Python service через `LLM_SERVICE_URL`.
- Backend-to-LLM endpoint: `POST /api/analysis/run`.
- Старый LLM route удалён и должен возвращать 404.

## Preflight Checks

Из корня проекта:

```bash
cd llm
python3 -m compileall llm tests
./.venv/bin/python -m unittest tests.test_taxonomy
./.venv/bin/python -m llm.evaluate_golden
```

```bash
cd backend
pnpm build
```

```bash
cd frontend
pnpm typecheck
pnpm build
```

## Start Services

Ollama:

```bash
ollama pull qwen2.5:3b-instruct
ollama serve
```

LLM service:

```bash
cd llm
source .venv/bin/activate
LLM_RECOMMENDATIONS_ENABLED=true \
OLLAMA_BASE_URL=http://127.0.0.1:11434 \
OLLAMA_MODEL=qwen2.5:3b-instruct \
OLLAMA_TIMEOUT_SECONDS=45 \
OLLAMA_RETRY_COUNT=0 \
OLLAMA_NUM_PREDICT=700 \
python -m uvicorn main:app --host 127.0.0.1 --port 8001
```

Backend:

```bash
cd backend
pnpm prisma:migrate
docker compose up -d redis
LLM_SERVICE_URL=http://127.0.0.1:8001 \
REDIS_URL=redis://127.0.0.1:6379 \
ANALYSIS_QUEUE_CONCURRENCY=1 \
pnpm start:dev
```

Frontend:

```bash
cd frontend
pnpm dev
```

## Health Checks

LLM:

```bash
curl http://127.0.0.1:8001/health
curl http://127.0.0.1:8001/ready
curl http://127.0.0.1:8001/api/analysis/health
```

Backend:

```bash
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/ready
```

`/ready` должен вернуть `ready: true`, если RuBERT-модель доступна.
`/api/analysis/health` дополнительно показывает статус RuBERT и Ollama.
Backend `/api/ready` проверяет DB, Redis и LLM service.

## Manual E2E Scenario

1. Открыть frontend.
2. Авторизоваться.
3. Загрузить `.pdf`, `.docx` или `.txt`.
4. Проверить переход статусов `QUEUED -> PROCESSING -> DONE`.
5. Открыть отчёт.
6. Проверить, что в header появился notification о завершении.
7. Открыть отчёт из notification center.
8. Проверить, что UI показывает русские labels: например `Насилие`, а не `violence`.
9. Проверить category cards, timeline chart, evidence-блок и варианты `было/стало`.
10. Открыть историю.
11. Открыть тот же отчёт из истории.
12. Перезагрузить страницу и убедиться, что сохранённый отчёт доступен.

## Fallback Scenario

1. Остановить Ollama или запустить LLM service с:

```bash
LLM_RECOMMENDATIONS_ENABLED=false
```

2. Загрузить `.pdf`, `.docx` или `.txt`.
3. Проверить, что анализ завершился со статусом `DONE`.
4. Проверить, что в отчёте есть `Шаблонная рекомендация`.
5. Проверить, что rating/category/level рассчитаны и сохранены.

## V1.1 Acceptance Criteria

- Golden regression: `failed = 0`.
- Старый LLM route возвращает 404.
- Backend build проходит.
- Frontend typecheck/build проходят.
- Redis доступен, backend `/api/ready` показывает `redis.ready: true`.
- LLM `/ready` возвращает `ready: true`.
- Анализ сохраняется и открывается из истории после перезагрузки.
- Notification создаётся после `DONE` или `FAILED`.
- Qwen не влияет на `rating`, `category`, `level`.
- При недоступной Ollama используется fallback.
- В UI нет technical labels: `scary`, `violence`, `fallback`.
- Сцена с дракой отображается как `Насилие`.
