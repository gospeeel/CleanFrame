# Updated Backlog: Backend/Frontend, Queue И Notifications

## Summary
Да, очередь нужна. Текущий backend запускает анализ in-process сразу после `POST /api/analyses`, поэтому несколько параллельных анализов зависят от жизни одного backend-процесса и могут потеряться при restart. Для production нужно перейти на durable queue: пользователь может отправить несколько файлов, backend поставит их в очередь, worker обработает по порядку/параллельно, а UI уведомит пользователя о завершении.

Уведомления добавляем отдельным слоем: сначала in-app notifications + polling/SSE, затем browser push как v2 backlog. Email/Brevo отложены до появления VPS и доменного имени.

## Key Changes

### P0: Queue Architecture
- Ввести durable queue для analysis jobs:
  - Redis + BullMQ как основной вариант для NestJS backend.
  - Backend API создаёт `Analysis` в БД со статусом `QUEUED`.
  - Backend кладёт job `{ analysisId, userId }` в очередь.
  - Отдельный worker забирает job и вызывает Python LLM service `POST /api/analysis/run`.
- Исходный файл нельзя хранить только в памяти:
  - для v1.1 хранить временный файл в локальном `uploads/analysis/{analysisId}` до завершения job;
  - после `DONE/FAILED/CANCELLED` файл удалять;
  - для v2 заменить на S3/R2 private object storage с retention.
- Расширить `AnalysisStatus`:
  - `QUEUED`;
  - `PROCESSING`;
  - `DONE`;
  - `FAILED`;
  - `CANCELLED`.
- Добавить metadata:
  - `queuedAt`;
  - `startedAt`;
  - `completedAt`;
  - `attempts`;
  - `errorCode`;
  - `workerId`.
- Queue policy:
  - concurrency: `1` по умолчанию для локального CPU/Ollama;
  - на GPU/server можно поднять до `2-4`;
  - retry только для transient errors: network, 503, timeout;
  - no retry для unsupported file/validation errors.
- Dead-letter behavior:
  - после max attempts job становится `FAILED`;
  - ошибка сохраняется в `errorMessage/errorCode`;
  - Sentry получает event с `analysisId`.

### P0: User Notifications
- Добавить in-app notification center:
  - иконка/кнопка в header;
  - unread count;
  - список событий;
  - click ведёт на `/report?id=<analysisId>`.
- Типы уведомлений:
  - `analysis_done`;
  - `analysis_failed`;
  - `analysis_long_running`;
  - `analysis_cancelled`.
- Минимальная DB-модель:
  - `Notification`: `id`, `userId`, `type`, `title`, `message`, `analysisId`, `readAt`, `createdAt`.
- Backend создаёт notification при переходе analysis в terminal status:
  - `DONE`;
  - `FAILED`;
  - `CANCELLED`.
- Frontend:
  - показывает toast при новом событии;
  - хранит список в notification center;
  - history/report остаются источником правды.
- Delivery v1.1:
  - polling `GET /api/notifications?unreadOnly=true` раз в 15-30 секунд;
  - mark read endpoint.
- Delivery v2:
  - SSE или WebSocket для realtime;
  - browser push как optional настройка;
  - email/Brevo не подключать до появления VPS и доменного имени.

### P0: IMDb‑Style Report
- Переработать `/report` под UX IMDb Parents Guide:
  - summary;
  - category severity cards;
  - раскрываемые категории;
  - список сцен по категориям;
  - evidence;
  - варианты `было/стало`.
- Chart.js оставить и использовать для “Пиков возрастного риска”.
- Добавить timeline points:
  - `scene_id`;
  - `scene_header`;
  - `page`;
  - `element_index`;
  - `timeline_position`;
  - `level`;
  - `rating`;
  - `primary_category`.
- График:
  - X-axis: позиция/сцена/страница;
  - Y-axis: риск `0-4`;
  - цвет: категория;
  - tooltip: категория, рейтинг, evidence preview;
  - click раскрывает сцену.
- Chart.js lazy-load только на странице отчёта.

### P1: Observability
- Sentry:
  - frontend `@sentry/nuxt`;
  - backend `@sentry/nestjs`.
- Trace chain:
  - upload request;
  - queue enqueue;
  - worker processing;
  - Python LLM request;
  - notification creation.
- Sentry tags:
  - `analysisId`;
  - `queueJobId`;
  - `workerId`;
  - `status`;
  - `fallbackUsed`;
  - `errorCode`.
- Data scrubbing:
  - не отправлять полный текст сценария;
  - не отправлять tokens/email codes;
  - не отправлять raw uploaded file names, если включён privacy mode.

### P1: Frontend Performance
- Оптимизировать визуальные слои:
  - adaptive `AmbientBackground`;
  - reduced blur на слабых устройствах;
  - остановка анимаций при hidden tab;
  - IntersectionObserver для entrance animations.
- Fonts:
  - убрать CSS `@import`;
  - preload/preconnect;
  - `font-display: swap`.
- Nuxt:
  - devtools только local/dev;
  - report widgets lazy-load;
  - Chart.js lazy-load.
- Performance targets:
  - initial JS gzip: 180-220 KB;
  - LCP: до 2.5s;
  - CLS: < 0.1;
  - INP: < 200ms.

### P1: Backend API Additions
- Analysis:
  - `POST /api/analyses`;
  - `GET /api/analyses`;
  - `GET /api/analyses/:id`;
  - `POST /api/analyses/:id/retry`;
  - `POST /api/analyses/:id/cancel`.
- Notifications:
  - `GET /api/notifications`;
  - `PATCH /api/notifications/:id/read`;
  - `PATCH /api/notifications/read-all`.
- Health:
  - `/api/health`: basic liveness;
  - `/api/ready`: DB + Redis + LLM service readiness.

## Test Plan
- Backend:
  - queue enqueue creates DB record `QUEUED`;
  - worker moves status `QUEUED -> PROCESSING -> DONE`;
  - failed LLM request creates `FAILED` + notification;
  - retry creates new queue job only for owned analysis;
  - cancel stops queued job and marks `CANCELLED`;
  - user A cannot see user B notifications.
- Frontend:
  - multiple uploads appear independently in history;
  - notification appears when job completes;
  - click notification opens report;
  - unread count updates;
  - Chart.js is not loaded before visiting report.
- E2E:
  - submit 3 files quickly;
  - see all jobs in history;
  - receive 3 completion/failure notifications;
  - open each result from notification center;
  - restart backend during queued job: job should not disappear after Redis/worker recovery.
- Observability:
  - Sentry receives worker failure with `analysisId`;
  - no raw script text in Sentry payload;
  - queue latency and processing time are visible.

## Assumptions
- Queue implementation: Redis + BullMQ.
- Local default concurrency: `1`, because Ollama/Qwen on CPU/GPU can be the bottleneck.
- Notifications v1.1 use DB + polling; SSE/WebSocket is v2.
- Uploaded source files may be stored temporarily only until job terminal status, then deleted.
- Chart.js remains in dependencies and is used for report timeline.

## Current State Review TODO

Ревизия по текущему коду проекта. Проверялись `backend/src`, `backend/prisma/schema.prisma`, `frontend/app`, Sentry configs и package dependencies.

### Что Уже Сделано

- [x] Backend analysis API:
  - [x] `POST /api/analyses`;
  - [x] `GET /api/analyses`;
  - [x] `GET /api/analyses/:id`;
  - [x] `POST /api/analyses/:id/retry`;
  - [x] `POST /api/analyses/:id/cancel`.
- [x] Durable queue на Redis/BullMQ:
  - [x] `AnalysisQueueService` создаёт BullMQ queue;
  - [x] job содержит `analysisId`, `userId`;
  - [x] concurrency настраивается через `ANALYSIS_QUEUE_CONCURRENCY`;
  - [x] attempts/backoff настраиваются через `ANALYSIS_QUEUE_ATTEMPTS`;
  - [x] есть отдельный runtime entrypoint `backend/src/worker.ts` и script `pnpm start:worker`.
- [x] Analysis statuses и metadata:
  - [x] `QUEUED`;
  - [x] `PROCESSING`;
  - [x] `DONE`;
  - [x] `FAILED`;
  - [x] `DEAD_LETTER`;
  - [x] `CANCELLED`;
  - [x] `queuedAt`, `startedAt`, `completedAt`, `attempts`, `errorCode`, `workerId`, `queueJobId`.
- [x] Временное хранение upload-файлов:
  - [x] файл сохраняется в `ANALYSIS_UPLOAD_DIR`;
  - [x] после `DONE` файл удаляется;
  - [x] после `CANCELLED` файл удаляется;
  - [x] после `FAILED/DEAD_LETTER` файл остаётся для retry.
- [x] Notifications backend:
  - [x] Prisma-модель `Notification`;
  - [x] `GET /api/notifications`;
  - [x] `PATCH /api/notifications/:id/read`;
  - [x] `PATCH /api/notifications/read-all`;
  - [x] notification создаётся для `DONE`, `FAILED/DEAD_LETTER`, `CANCELLED`.
- [x] Notifications frontend:
  - [x] notification center в header;
  - [x] unread count;
  - [x] polling раз в 20 секунд;
  - [x] toast для нового unread notification;
  - [x] click ведёт на `/report?id=<analysisId>`.
- [x] Report UX:
  - [x] summary максимального рейтинга;
  - [x] category severity cards;
  - [x] раскрываемые сцены по категориям;
  - [x] evidence;
  - [x] варианты `было/стало`;
  - [x] Chart.js timeline lazy-load внутри `RiskTimelineChart.vue`;
  - [x] click по точке графика раскрывает сцену.
- [x] Health/readiness:
  - [x] `/api/health`;
  - [x] `/api/ready` проверяет DB, Redis, LLM service.
- [x] Базовый Sentry:
  - [x] frontend `@sentry/nuxt`;
  - [x] backend `@sentry/nestjs`;
  - [x] базовый scrubbing `authorization` и `cookie` headers.
- [x] Frontend performance basics:
  - [x] Nuxt devtools включаются только через `NUXT_DEVTOOLS=true`;
  - [x] Chart.js загружается динамическим import только на странице отчёта;
  - [x] fonts подключены через `preconnect` и stylesheet с `display=swap`, без CSS `@import`.

### Что Не Доделано

- [x] Разделение backend API и worker на уровне deploy/runtime закреплено в Docker/compose/deploy config:
  - [x] API process запускается с `ANALYSIS_WORKER_ENABLED=false`;
  - [x] worker process запускается отдельной командой `pnpm start:worker`;
  - [x] documented runbook есть в README + `docker-compose.yaml`.
- [x] Retry policy разделяет transient и validation errors:
  - [x] validation/unsupported file errors помечаются как unrecoverable и не ретраятся;
  - [x] transient retry оставлен для timeout/network/503/5xx.
- [x] Dead-letter observability:
  - [x] явно отправляется `Sentry.captureException` при terminal failure/dead-letter;
  - [x] добавляются Sentry tags `analysisId`, `queueJobId`, `workerId`, `status`, `errorCode`;
  - [x] добавляются breadcrumbs для `queued`, `processing`, `retry`, `dead-letter`, `done`.
- [x] Trace chain:
  - [x] связан прикладной `frontend -> backend API -> Redis/BullMQ job -> backend worker -> Python LLM` через `x-request-id`;
  - [x] request context прокидывается в BullMQ job data и Sentry breadcrumbs/tags.
- [x] Data scrubbing:
  - [x] Sentry удаляет `authorization`, `cookie`, request body/data и cookies;
  - [x] Sentry не получает request body с текстом сценария;
  - [x] raw uploaded file names фильтруются в custom context при `PRIVACY_MODE=true`;
  - [x] tokens/email codes/password-like поля фильтруются в custom contexts.
- [x] `ANALYSIS_LONG_RUNNING` notification:
  - [x] добавлен threshold для долгих job;
  - [x] создаётся notification `ANALYSIS_LONG_RUNNING`;
  - [x] повторные уведомления по одной job не создаются.
- [ ] Frontend notification realtime:
  - [x] SSE stream добавлен через `GET /api/notifications/stream`;
  - [x] polling оставлен как fallback;
  - [ ] browser push как opt-in настройка;
  - [ ] email/Brevo отложены до VPS и доменного имени.
- [x] Timeline metadata нормализуется на уровне backend:
  - [x] валидируются/нормализуются `scene_id`, `scene_header`, `page`, `element_index`, `timeline_position`;
  - [x] добавлен fallback timeline position при неполных данных.
- [x] Upload lifecycle и retention:
  - [x] после `DONE` файл удаляется;
  - [x] после `CANCELLED` файл удаляется;
  - [x] после `FAILED/DEAD_LETTER` файл оставлен для retry осознанно;
  - [x] добавлена retention cleanup job для старых failed/dead-letter/cancelled файлов.
- [ ] S3/R2 private object storage для v2 не сделан:
  - [ ] заменить локальный `ANALYSIS_UPLOAD_DIR` на private object storage;
  - [ ] добавить retention policy;
  - [ ] добавить cleanup job.

### Что Не Сделано

- [ ] Automated backend tests из Test Plan:
  - [x] queue enqueue создаёт DB record `QUEUED`;
  - [ ] worker переводит `QUEUED -> PROCESSING -> DONE`;
  - [ ] failed LLM request создаёт `FAILED/DEAD_LETTER` + notification;
  - [x] retry доступен только владельцу анализа;
  - [x] cancel удаляет queued job и ставит `CANCELLED`;
  - [ ] user A не видит notifications user B.
- [ ] Automated frontend tests:
  - [ ] несколько загрузок появляются независимо в history;
  - [ ] notification появляется после завершения job;
  - [ ] click notification открывает report;
  - [ ] unread count обновляется;
  - [ ] Chart.js не загружается до посещения report.
- [ ] E2E сценарии:
  - [ ] отправить 3 файла подряд;
  - [ ] увидеть все jobs в history;
  - [ ] получить 3 completion/failure notifications;
  - [ ] открыть каждый result из notification center;
  - [ ] рестарт worker/backend во время queued/processing job не теряет analysis.
- [ ] Performance verification:
  - [ ] измерить initial JS gzip;
  - [ ] измерить LCP;
  - [ ] измерить CLS;
  - [ ] измерить INP;
  - [ ] проверить слабые устройства/reduced motion/hidden tab.
- [ ] Queue metrics:
  - [ ] queue latency;
  - [ ] processing time;
  - [ ] attempts count;
  - [ ] dead-letter count;
  - [ ] worker concurrency utilization.

### Что Нужно Доделать В Первую Очередь

- [x] P0: добавить backend verification tests для queue/retry/cancel/notifications ownership.
- [x] P0: исправить retry policy, чтобы validation errors не ретраились.
- [x] P0: добавить Sentry scope/tags/breadcrumbs/captureException для worker и dead-letter.
- [x] P0: добавить retention cleanup для старых source files после `FAILED/DEAD_LETTER`.
- [x] P1: добавить `ANALYSIS_LONG_RUNNING` notification.
- [x] P1: закрепить deploy-схему API и worker отдельными процессами в Docker/compose.
- [ ] P1: добавить E2E smoke на 3 параллельных анализа и restart worker.
- [ ] P2: измерить frontend performance targets и зафиксировать baseline.

### Что Можно Сделать Позже

- [x] SSE вместо polling как основной realtime-канал, polling оставлен fallback.
- [ ] Browser push notifications как пользовательская настройка.
- [ ] Email/Brevo notifications после появления VPS и доменного имени.
- [ ] S3/R2 private object storage для upload-файлов.
- [ ] Admin/ops экран для queue status, failed/dead-letter jobs и ручного retry.
- [ ] Privacy mode для скрытия raw file names в UI/logs/Sentry.
- [ ] Report export в PDF/HTML.
- [ ] Отдельная страница сравнения нескольких анализов одного сценария.
