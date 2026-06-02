# 🎬 CleanFrame

> **Full-stack платформа для анализа сценариев на возрастной рейтинг, поиска риск-сцен и формирования редакционных рекомендаций с помощью RuBERT и Qwen.**

![Nuxt](https://img.shields.io/badge/Nuxt-4-00DC82?logo=nuxt&logoColor=white)
![Vue](https://img.shields.io/badge/Vue-3-4FC08D?logo=vuedotjs&logoColor=white)
![NestJS](https://img.shields.io/badge/NestJS-11-E0234E?logo=nestjs&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.121+-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-4169E1?logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Qwen](https://img.shields.io/badge/Qwen-Ollama-111111)
![RuBERT](https://img.shields.io/badge/RuBERT-HuggingFace-FFD21E?logo=huggingface&logoColor=black)

---

## 🌟 О проекте

**CleanFrame** помогает сценаристу, редактору или продюсеру понять, какие сцены повышают возрастной рейтинг сценария и какие правки могут приблизить текст к выбранной цели: `6+`, `12+`, `16+`, `18+` или raw-анализу без целевого порога.

Система объединяет:

- **frontend-отчёт** с навигацией по категориям, риск-сценам и рекомендациям;
- **backend API** с очередью анализа, историей, retry и PDF-выгрузкой;
- **LLM-сервис** для парсинга сценариев, классификации рисков и генерации редакционных советов;
- **RuBERT-классификатор** для категорий, уровня риска и рейтинговых сигналов;
- **Qwen через Ollama** для практических рекомендаций по снижению рейтинга;
- **safe-context правила**, снижающие ложные срабатывания на бытовых, метафорических и нейтральных фразах.

> 🚀 Подробный запуск проекта описан в [`QUICK_START.md`](QUICK_START.md).

---

## 🧩 Ключевые функции

### 🎯 Анализ под целевой рейтинг

- Выбор цели перед загрузкой сценария: `Raw`, `6+`, `12+`, `16+`, `18+`.
- Фактический рейтинг всё равно считается честно по всему сценарию.
- В целевом режиме отчёт фокусируется на сценах, которые мешают выбранному порогу.
- Raw-сигналы можно раскрыть отдельно, если нужен полный диагностический анализ.

### 🔎 Поиск риск-сцен

- Парсинг `.txt`, `.pdf`, `.docx`.
- Разбиение сценария на компактные фрагменты, чтобы пользователь не перечитывал весь текст заново.
- Категории риска: насилие, пугающие сцены, вещества, сексуализированный контент, грубая лексика и другие сигналы.
- Evidence-блоки с короткими основаниями и matched terms.

### 🧠 LLM-рекомендации

- Qwen формирует редакционные рекомендации для риск-сцен.
- Grouped-рекомендации уменьшают число LLM-запросов и ускоряют анализ больших сценариев.
- Для каждой сцены сохраняются собственные evidence, rating, target rating и policy basis.
- При недоступности LLM система возвращает понятный fallback, а не ломает анализ.

### 📊 Отчёт и UX

- Сводка: фактический рейтинг, цель, количество блокирующих сцен и время анализа.
- Карточки категорий с быстрым переходом.
- Фильтрация и навигация по категориям.
- Компактные tabs-рекомендации: мягкая правка, сильная правка, сохранение драматургии.
- PDF-выгрузка результата.

### 🛡️ Очередь, история и администрирование

- История анализов для пользователя.
- Очередь задач на BullMQ.
- Worker-процесс для фонового анализа.
- Retry проблемных задач.
- Dead-letter статусы для неуспешных анализов.
- Privacy mode для скрытия чувствительных данных в админских экранах.

---

## 🏗️ Архитектура

```text
Frontend Nuxt 4
      |
      v
Backend NestJS 11  ---- PostgreSQL 17
      |                     |
      |                     v
      +--------------- Redis 7 / BullMQ Worker
      |
      v
LLM Service FastAPI
      |
      +-- Parser: txt / pdf / docx
      +-- Rule detector + safe-context
      +-- RuBERT classifier
      +-- Qwen recommendations via Ollama
```

При первом Docker-запуске проект автоматически подтягивает:

- **RuBERT** из Hugging Face: `gospeeel/ruBERT-cleanframe`;
- **Qwen** через Ollama: `qwen3:1.7b`.

---

## 🛠️ Технологии

### Frontend

- Nuxt 4
- Vue 3
- Pinia
- TanStack Vue Query
- Tailwind CSS
- Chart.js
- Sentry / GlitchTip

### Backend

- NestJS 11
- Prisma 7
- PostgreSQL 17
- Redis 7
- BullMQ
- JWT auth
- PDFKit
- S3-compatible storage

### LLM-сервис

- Python 3.12
- FastAPI + Uvicorn
- PyTorch
- Transformers
- RuBERT
- Natasha, Razdel, Pymorphy2
- pdfplumber, python-docx
- Qwen через Ollama
- Hugging Face Hub для доставки модели

### Инфраструктура

- Docker Compose
- GitHub Actions
- Ollama
- Hugging Face model repository
- PostgreSQL volume
- Redis queue

---

## 📦 Структура проекта

```text
CleanFrame/
├── backend/              # NestJS API, Prisma, auth, queue, PDF/report logic
├── frontend/             # Nuxt-приложение и UI отчёта
├── llm/                  # FastAPI LLM service, parser, RuBERT, Qwen recommendations
├── doc/                  # Тестовые документы и локальные материалы
├── .github/              # GitHub Actions и CI scripts
├── docker-compose.yaml   # Production-like orchestration
├── QUICK_START.md        # Инструкция запуска
└── README.md
```

---

## ✅ Проверки качества

В проекте есть CI-проверки для основных частей:

- frontend typecheck и build;
- backend typecheck, build и workflow tests;
- LLM compile/test/quality gate;
- статическая проверка worker/queue/docker wiring.

Основные CI-скрипты лежат в:

```text
.github/scripts/
```

---

## 📌 Текущий статус

Проект находится в стадии **production-hardening**: уже есть полноценный full-stack pipeline, фоновые задачи, LLM-рекомендации, отчёт, PDF-экспорт, базовые quality gates и переносимый Docker-запуск.

Ближайшие направления развития:

- расширение human-labeled golden dataset;
- дальнейшая калибровка RuBERT/rating policy;
- улучшение evidence quality evaluation;
- ускорение локального inference;
- расширение regression-наборов для false positives.
