# ML_WINK

Система анализа русскоязычных сценариев на потенциальные возрастные ограничения.

## Структура

- `frontend/` - Nuxt 4 приложение.
- `backend/` - NestJS API gateway: авторизация, загрузка файлов, CORS и проксирование LLM-сервиса.
- `llm/` - Python FastAPI LLM/NLP сервис: парсинг документов, словарная фильтрация, RuBERT-инференс и рекомендации.
- `llm/trained_model/` - локальный артефакт RuBERT-модели для LLM-сервиса. Папка не хранится в git и не запекается в Docker image.
- `doc/` - локальные документы и примеры.

## Docker Compose

```bash
docker compose up --build
```

Сервисы:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- LLM service: `http://localhost:8001`
- Postgres: `localhost:5432`
- Redis: `localhost:6379`

Для полноценного анализа нужна локальная папка `llm/trained_model/`.
В compose она монтируется в LLM-контейнер как `/models/trained_model` в read-only режиме.

Минимальный состав модели:

```text
llm/trained_model/
  config.json
  tokenizer.json
  tokenizer_config.json
  vocab.txt
  special_tokens_map.json
  category_to_id.json
  id_to_category.json
  level_class_weights.npy
  level_shift.npy
  model.safetensors
  model_manifest.json
```

## Backend

Backend использует Redis/BullMQ для очереди анализов. Для локального запуска перед `pnpm start:dev` поднимите Redis:

```bash
docker compose up -d redis
```

```bash
cd backend
pnpm install
cp .env.example .env
pnpm prisma:generate
pnpm prisma:migrate
pnpm start:dev
```

Если `pnpm prisma:migrate` падает с `P3014 permission denied to create database`, значит пользователь Postgres не может создать shadow database. Для локального dev есть два варианта:

```bash
sudo -u postgres psql -c "ALTER USER ml_wink CREATEDB;"
```

или создать отдельную shadow DB и указать её в `backend/.env`:

```bash
sudo -u postgres createdb -O ml_wink ml_wink_shadow
```

```env
SHADOW_DATABASE_URL=postgresql://ml_wink:ml_wink_password@localhost:5432/ml_wink_shadow?schema=public
```

Для простого применения уже готовых миграций без shadow database можно использовать:

```bash
pnpm prisma:deploy
```

API:

```text
GET  /api/health
GET  /api/ready

POST /api/analyses
GET  /api/analyses
GET  /api/analyses/:id
POST /api/analyses/:id/retry
POST /api/analyses/:id/cancel
authenticated async analysis jobs with persisted history
supported upload formats: .docx, .pdf, .txt

GET   /api/notifications
GET   /api/notifications/stream
PATCH /api/notifications/:id/read
PATCH /api/notifications/read-all

POST /api/auth/register
POST /api/auth/login
POST /api/auth/refresh
POST /api/auth/logout
GET  /api/auth/me

PATCH  /api/auth/profile/password
POST   /api/auth/profile/avatar
DELETE /api/auth/profile/avatar

POST  /api/auth/admin/invites
PATCH /api/auth/admin/users/:id/role

GET /api/auth/oauth/google
GET /api/auth/oauth/yandex
GET /api/auth/oauth/vk
GET /api/auth/oauth/:provider/callback
```

Backend проксирует анализ в LLM-сервис через `LLM_SERVICE_URL` и внутренний endpoint `POST /api/analysis/run`.
Основной пользовательский поток создаёт async job в `/api/analyses`, сохраняет результат в Postgres и показывает историю запросов. Файл временно хранится в `ANALYSIS_UPLOAD_DIR` до завершения задачи; после `DONE` или `CANCELLED` он удаляется. После `FAILED` файл сохраняется для ручного retry.

В production/runtime backend API и analysis worker запускаются отдельными процессами:

```bash
# API process
ANALYSIS_WORKER_ENABLED=false pnpm start:prod

# Worker process
ANALYSIS_WORKER_ENABLED=true pnpm start:worker
```

В `docker-compose.yaml` это уже разделено на сервисы `backend` и `backend-worker`. Worker отвечает за BullMQ processing, retries, dead-letter handling, long-running notifications и cleanup старых retained upload-файлов.
Realtime-уведомления идут через SSE endpoint `GET /api/notifications/stream`; polling остаётся fallback на frontend.

GlitchTip/Sentry-compatible observability включается при заполненном `GLITCHTIP_DSN` или `SENTRY_DSN`. Frontend использует `NUXT_PUBLIC_GLITCHTIP_DSN` или `NUXT_PUBLIC_SENTRY_DSN`.
В локальных `.env` можно указывать GlitchTip DSN; SDK остаётся Sentry-compatible, поэтому пакеты `@sentry/*` и `sentry-sdk` продолжают использоваться.

### Auth and database

Backend использует Prisma 7 + Postgres. Логическая схема БД и Mermaid ER-диаграмма лежат в [`backend/docs/auth-database.md`](backend/docs/auth-database.md).

Связей many-to-many в auth-схеме нет:

- `users` 1:N `auth_accounts`
- `users` 1:N `refresh_tokens`
- `users` 1:N `email_verification_codes`
- `users` 1:N `admin_invites` как creator
- `users` 1:N `admin_invites` как used user

Создать главного администратора:

```bash
cd backend
SEED_ADMIN_LOGIN=admin \
SEED_ADMIN_EMAIL=admin@example.com \
SEED_ADMIN_PASSWORD='change-this-password' \
pnpm seed:admin
```

Seed-пользователь получает роль `SUPER_ADMIN`. Администраторы, созданные через invite-link, получают роль `ADMIN` и могут модерировать только обычных пользователей.

OAuth Google/Yandex/VK работает через backend endpoints. Для локальной проверки укажите в OAuth-приложениях redirect URI:

```text
http://localhost:8000/api/auth/oauth/google/callback
http://localhost:8000/api/auth/oauth/yandex/callback
http://localhost:8000/api/auth/oauth/vk/callback
```

И заполните `backend/.env`:

```env
BACKEND_PUBLIC_URL=http://localhost:8000
FRONTEND_URL=http://localhost:3000

GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
YANDEX_CLIENT_ID=
YANDEX_CLIENT_SECRET=
VK_CLIENT_ID=
VK_CLIENT_SECRET=
```

OAuth callback backend возвращает пользователя на `/oauth/callback`, где frontend сохраняет полученную сессию в Pinia store.

Смена email временно отключена: SMTP/Brevo не требуется для локального запуска проекта.

Аватары профиля загружаются в S3-compatible storage. Для бесплатного старта можно использовать Cloudflare R2, в `users.avatar_url` хранится публичный URL:

```env
S3_ENDPOINT=https://your-cloudflare-account-id.r2.cloudflarestorage.com
S3_REGION=auto
S3_BUCKET=ml-wink
S3_ACCESS_KEY_ID=your-r2-access-key-id
S3_SECRET_ACCESS_KEY=your-r2-secret-access-key
S3_PUBLIC_BASE_URL=https://your-public-r2-domain
```

После обновления схемы авторизации примените миграции:

```bash
cd backend
pnpm install
pnpm prisma:generate
pnpm prisma:migrate
```

## LLM Service

```bash
cd llm
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8001
```

Для локальных LLM-рекомендаций установите Ollama и скачайте лёгкую instruct-модель:

```bash
ollama pull qwen2.5:3b-instruct
```

LLM не меняет итоговый рейтинг: рейтинг считает RuBERT/rules engine, а локальная LLM генерирует объяснение и редакторские рекомендации. Если Ollama выключена или вернула невалидный JSON, сервис использует deterministic fallback-рекомендации.
Поддерживаемые форматы анализа: `.docx`, `.pdf`, `.txt`.

Настройки:

```env
LLM_RECOMMENDATIONS_ENABLED=true
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:3b-instruct
OLLAMA_TIMEOUT_SECONDS=45
OLLAMA_RETRY_COUNT=0
OLLAMA_NUM_PREDICT=700
```

### V1.1 E2E

V1.1 поддерживает `.pdf`, `.docx` и `.txt`. Пользовательский frontend-поток работает через `/api/analyses`; backend вызывает внутренний Python endpoint `POST /api/analysis/run`.
Для очереди нужен Redis. По умолчанию локальная concurrency равна `1`, чтобы не перегружать Ollama/RuBERT на CPU.

Перед ручной проверкой:

```bash
cd llm
python3 -m compileall llm tests
./.venv/bin/python -m unittest tests.test_taxonomy
./.venv/bin/python -m llm.evaluate_golden
```

```bash
cd backend && pnpm build
cd ../frontend && pnpm typecheck && pnpm build
```

Подробный сценарий проверки: `llm/docs/v1-e2e.md`. Backlog следующих этапов: `llm/docs/backlog.md`.

Подробный checklist: [`llm/docs/v1-e2e.md`](llm/docs/v1-e2e.md).

Health endpoints:

```text
GET /health - процесс LLM-сервиса запущен
GET /ready  - модель найдена, валидна и загружается
```

Для локального запуска модель по умолчанию читается из `llm/trained_model/`.
Путь можно переопределить:

```bash
RUBERT_MODEL_DIR=/absolute/path/to/trained_model uvicorn main:app --host 127.0.0.1 --port 8001
```

### Model Evaluation

Фундамент для улучшения качества модели:

- `llm/datasets/README.md` - формат датасетов.
- `llm/datasets/annotation_guidelines.md` - правила ручной разметки.
- `llm/datasets/golden/example.jsonl` - минимальный пример JSONL.
- `llm/llm/tools/datasets/bootstrap_dataset.py` - генератор большого synthetic/weak-labeled silver dataset.
- `llm/llm/evaluate.py` - CLI для расчёта метрик.

Сгенерировать bootstrap dataset:

```bash
cd llm
python3 -m llm.tools.datasets.bootstrap_dataset --samples-per-bucket 30 --output-dir datasets/silver
```

Если генерируете датасеты из Docker с bind mount, запускайте контейнер от своего пользователя, иначе файлы на хосте могут стать `root:root`:

```bash
docker run --rm \
  --user "$(id -u):$(id -g)" \
  -v "$PWD/llm/datasets:/service/datasets" \
  ml-wink-llm-check \
  python -m llm.tools.datasets.bootstrap_dataset --samples-per-bucket 30 --output-dir datasets/silver
```

Запуск оценки:

```bash
cd llm
python3 -m llm.evaluate \
  --dataset datasets/silver/validation.jsonl \
  --model-dir trained_model \
  --output reports/evaluation_report.json \
  --device cpu
```

Основные метрики:

- `category_metrics.macro_f1` - главный сигнал качества по категориям.
- `category_metrics.observed_macro_f1` - macro-F1 только по классам, которые есть в датасете.
- `category_metrics.confusion_matrix` - какие категории модель путает.
- `level_metrics.mae` - средняя ошибка уровня риска.
- `level_metrics.quadratic_weighted_kappa` - насколько хорошо модель ранжирует тяжесть.
- `rating_metrics.accuracy` - точность итогового возрастного рейтинга, если в датасете есть поле `rating`.
- `errors.category_examples`, `errors.level_examples`, `errors.low_confidence_examples` - примеры для ручного анализа.

Обучить кандидата модели на JSONL:

```bash
cd llm
python3 -m llm.tools.training.train_jsonl \
  --train datasets/silver/train.jsonl \
  --validation datasets/silver/validation.jsonl \
  --output-dir trained_model_candidate \
  --epochs 3 \
  --batch-size 8 \
  --device cpu
```

Сравнить несколько базовых моделей:

```bash
python3 -m llm.tools.training.compare_models \
  --train datasets/silver/train.jsonl \
  --validation datasets/silver/validation.jsonl \
  --test datasets/silver/test.jsonl \
  --epochs 3 \
  --batch-size 8
```

Собрать очередь ручной проверки из ошибок отчёта:

```bash
python3 -m llm.tools.datasets.build_annotation_queue \
  --report reports/silver_validation_report.json \
  --output datasets/golden/annotation_queue.jsonl
```

Реальные `golden/*.jsonl`, `raw/` и `reports/` игнорируются git, потому что могут содержать чувствительные тексты сценариев.
Синтетический `silver` помогает стартовать, но финальную production-уверенность даёт только экспертно размеченный `golden`/`test` набор.

## Frontend

```bash
cd frontend
pnpm install
NUXT_PUBLIC_API_BASE=http://127.0.0.1:8000 pnpm dev
```

Useful frontend checks:

```bash
pnpm typecheck
pnpm build
```

По умолчанию frontend обращается к `http://127.0.0.1:8000`. URL backend можно переопределить через:

```bash
NUXT_PUBLIC_API_BASE=http://127.0.0.1:8000
```

Auth-состояние хранится в Pinia: login/register/logout, refresh token rotation, восстановление сессии после перезагрузки и OAuth callback. TanStack/Vue Query подключён в проекте и лучше подходит для серверных списков и аналитических данных, но не должен заменять Pinia как источник текущей пользовательской сессии.
