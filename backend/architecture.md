# 🧱 Архитектура Backend

> **Backend CleanFrame** - NestJS-сервис, который отвечает за пользователей, авторизацию, очередь анализа, хранение результатов, PDF-отчёты, уведомления и связь с LLM-сервисом.

![NestJS](https://img.shields.io/badge/NestJS-11-E0234E?logo=nestjs&logoColor=white)
![Prisma](https://img.shields.io/badge/Prisma-7-2D3748?logo=prisma&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-4169E1?logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)
![BullMQ](https://img.shields.io/badge/BullMQ-Queue-CB3837)

---

## 🌟 Назначение слоя

Backend является центральным прикладным слоем проекта. Он принимает файлы от пользователя, создаёт задачу анализа, отправляет сценарий в LLM-сервис, сохраняет результат и отдаёт frontend-части историю, статусы, отчёты и PDF.

Ключевые обязанности:

- регистрация, вход и JWT-аутентификация;
- роли пользователей и доступ к административным экранам;
- загрузка и временное хранение файлов анализа;
- постановка анализа в очередь;
- фоновая обработка задач worker-процессом;
- retry, dead-letter и мониторинг проблемных задач;
- сохранение результата анализа в PostgreSQL;
- генерация PDF;
- уведомления о завершении или ошибках;
- audit log событий.

---

## 🏗️ Общая схема

```text
Frontend
   |
   v
NestJS API
   |
   +-- AuthModule
   +-- AnalysesModule ---- BullMQ / Redis ---- Worker
   |        |
   |        +---- LlmModule ---- FastAPI LLM service
   |        |
   |        +---- PDF / file storage / retention
   |
   +-- NotificationsModule
   +-- AuditModule
   +-- PrismaModule ---- PostgreSQL
```

---

## 📦 Структура

```text
backend/
├── prisma/                  # Prisma schema и миграции БД
├── scripts/                 # Проверки workflow, seed admin, e2e smoke
├── src/
│   ├── analyses/            # Основная доменная логика анализа сценариев
│   ├── audit/               # Запись audit-событий
│   ├── auth/                # Auth, роли, OAuth, аватары
│   ├── llm/                 # Клиент для LLM-сервиса
│   ├── notifications/       # Уведомления пользователя
│   ├── observability/       # Метрики очередей и наблюдаемость
│   ├── prisma/              # PrismaService и DI-модуль
│   ├── app.module.ts        # Корневой NestJS-модуль
│   ├── health.controller.ts # Health/ready endpoints
│   ├── main.ts              # HTTP API bootstrap
│   └── worker.ts            # Worker bootstrap
├── Dockerfile
├── package.json
└── .env.example
```

---

## 🧩 Основные модули

### 🔐 `auth/`

Отвечает за пользователей и доступ:

- регистрация и вход;
- JWT guard;
- роли `ANALYST`, `ADMIN`, `SUPER_ADMIN`;
- OAuth-провайдеры;
- аватары через S3-compatible storage;
- декораторы и guards для защищённых маршрутов.

### 🎬 `analyses/`

Главный модуль сценарного анализа:

- `analyses.controller.ts` принимает HTTP-запросы;
- `analyses.service.ts` создаёт анализы, отдаёт историю, retry и детали;
- `analysis-queue.service.ts` ставит задачи в BullMQ;
- `analysis-processor.service.ts` выполняет анализ через LLM;
- `analysis-file-storage.service.ts` хранит исходный файл до обработки;
- `analysis-pdf.service.ts` формирует PDF;
- `analysis-retention.service.ts` удаляет старые исходные файлы;
- `analysis-monitor.service.ts` отслеживает долгие задачи.

### 🧠 `llm/`

Тонкий клиент к FastAPI LLM-сервису:

- отправляет файл multipart-запросом;
- передаёт `targetRating`;
- учитывает timeout;
- нормализует имя файла для приватности и логов.

### 🔔 `notifications/`

Хранит и отдаёт уведомления:

- завершение анализа;
- ошибка анализа;
- долгий анализ;
- отмена или проблемный статус.

### 🧾 `audit/`

Пишет события в таблицу `audit_events`:

- создание анализа;
- завершение;
- ошибка;
- удаление исходного файла;
- retry/dead-letter события.

### 🗄️ `prisma/`

Инкапсулирует доступ к PostgreSQL через Prisma Client.

---

## 🔁 Процесс анализа

```text
1. Пользователь выбирает target rating и загружает файл.
2. Backend сохраняет файл во временное хранилище.
3. Создаётся запись Analysis со статусом QUEUED.
4. Задача отправляется в BullMQ.
5. Worker забирает задачу и переводит статус в PROCESSING.
6. LlmService отправляет файл в FastAPI LLM.
7. LLM возвращает результат анализа.
8. Backend сохраняет resultJson, maxRating, riskCount, reviewCount.
9. Пользователь получает уведомление.
10. Исходный файл удаляется по retention/security правилам.
```

---

## ⚙️ Важные конфиги

- `DATABASE_URL` - подключение к PostgreSQL.
- `REDIS_URL` - Redis для BullMQ.
- `LLM_SERVICE_URL` - адрес FastAPI LLM.
- `LLM_ANALYSIS_TIMEOUT_MS` - timeout анализа.
- `ANALYSIS_QUEUE_CONCURRENCY` - параллельность worker.
- `ANALYSIS_QUEUE_ATTEMPTS` - число попыток.
- `PRIVACY_MODE` - скрытие чувствительных данных в ops-экранах.
- `JWT_ACCESS_SECRET` - секрет JWT.

---

## ✅ Проверки

Основные команды backend:

```bash
pnpm typecheck
pnpm test:analysis
pnpm test:security
pnpm build
```

В CI backend также запускает Prisma generate и production build.
