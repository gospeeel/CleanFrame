# 🎨 Архитектура Frontend

> **Frontend CleanFrame** - Nuxt/Vue-приложение, которое даёт пользователю загрузку сценария, выбор целевого рейтинга, историю анализов, отчёт, сравнение результатов и административные ops-экраны.

![Nuxt](https://img.shields.io/badge/Nuxt-4-00DC82?logo=nuxt&logoColor=white)
![Vue](https://img.shields.io/badge/Vue-3-4FC08D?logo=vuedotjs&logoColor=white)
![Pinia](https://img.shields.io/badge/Pinia-State-F7C545)
![TanStack Query](https://img.shields.io/badge/TanStack_Query-5-FF4154)
![Tailwind](https://img.shields.io/badge/Tailwind_CSS-3-38B2AC?logo=tailwindcss&logoColor=white)

---

## 🌟 Назначение слоя

Frontend отвечает за пользовательский опыт: загрузку сценария, выбор цели анализа, отображение статуса, чтение отчёта, фильтрацию категорий, работу с историей и административными задачами.

Основные задачи:

- авторизация и хранение пользовательской сессии;
- отправка файла на анализ;
- выбор `Raw / 6+ / 12+ / 16+ / 18+`;
- отображение compact report;
- навигация по категориям и риск-сценам;
- PDF download;
- история анализов;
- ops-панель проблемных задач;
- privacy mode для админских экранов.

---

## 🏗️ Общая схема

```text
Nuxt Pages
   |
   +-- Features ---- Shared API ---- Backend API
   |
   +-- Widgets
   |
   +-- Entities / Stores
   |
   +-- Shared UI / lib / css
```

Проект близок к feature-sliced подходу: бизнес-сущности лежат в `entities`, сценарии использования - в `features`, крупные UI-блоки - в `widgets`, общие API/helpers/UI - в `shared`.

---

## 📦 Структура

```text
frontend/
├── app/
│   ├── entities/            # Типы, stores и presentation helpers доменных сущностей
│   ├── features/            # Пользовательские сценарии: auth, upload, ops, profile
│   ├── middleware/          # Route middleware
│   ├── pages/               # Nuxt pages
│   ├── plugins/             # Client plugins
│   ├── shared/              # Общие API, lib, UI и CSS
│   ├── widgets/             # Крупные виджеты интерфейса
│   └── app.vue              # Корневой layout приложения
├── nuxt.config.ts
├── tailwind.config.ts
├── sentry.client.config.ts
├── sentry.server.config.ts
├── Dockerfile
└── .env.example
```

---

## 🧩 Основные зоны

### 🧬 `entities/`

Содержит доменные модели:

- `analysis` - типы анализа, presentation helpers, UI-store раскрытых сцен;
- `user` - типы пользователя и auth store;
- `notification` - типы уведомлений.

### ⚙️ `features/`

Содержит пользовательские сценарии:

- `auth` - login/register panels;
- `script-analysis` - upload panel, drag & drop, target rating, polling анализа;
- `ops` - очередь активных и проблемных задач;
- `profile` - профиль пользователя;
- `compare` - сравнение анализов;
- `notifications` - запросы уведомлений.

### 🧱 `widgets/`

Крупные композиционные блоки:

- `analysis-result` - основной отчёт анализа;
- `app-header` - верхняя навигация и notifications;
- `ambient-background` - визуальный фон приложения.

### 🔌 `shared/`

Общие переиспользуемые части:

- `api` - HTTP-клиенты к backend;
- `lib` - motion/privacy helpers;
- `ui` - небольшие общие компоненты;
- `assets/css` - глобальные стили.

---

## 🔁 Процесс пользовательского анализа

```text
1. Пользователь открывает главную страницу.
2. UploadPanel предлагает выбрать target rating.
3. Пользователь загружает файл или перетаскивает его drag & drop.
4. useScriptAnalysis / useAnalysisQueries создаёт анализ через API.
5. Frontend polling-ом получает статус задачи.
6. После DONE открывается report page.
7. AnalysisResult группирует сцены по категориям.
8. Пользователь фильтрует категории, раскрывает детали и скачивает PDF.
```

---

## 📊 Отчёт анализа

`AnalysisResult.vue` отвечает за:

- сводку результата;
- target/raw режим;
- фильтр категорий;
- быстрый переход к категории;
- карточки риск-сцен;
- compact evidence;
- tabs вариантов правки;
- fallback/needs-review пояснения;
- график распределения рисков.

`RiskTimelineChart.vue` отвечает за визуализацию риск-точек и удержание точек внутри области графика.

---

## ⚙️ Важные конфиги

- `NUXT_PUBLIC_API_BASE` - адрес backend API.
- `NUXT_PUBLIC_PRIVACY_MODE` - скрытие чувствительных данных в UI.
- `NUXT_PUBLIC_APP_ENV` - окружение.
- `NUXT_PUBLIC_APP_VERSION` - версия приложения.
- `NUXT_PUBLIC_SENTRY_DSN` / `NUXT_PUBLIC_GLITCHTIP_DSN` - observability.

---

## ✅ Проверки

Основные команды frontend:

```bash
pnpm typecheck
pnpm build
```

В CI используется Node.js 22.
