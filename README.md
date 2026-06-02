# CleanFrame

**CleanFrame** - сервис для анализа сценариев на возрастной рейтинг и редакционные риски. Проект помогает сценаристу, редактору или продюсеру понять, какие сцены повышают рейтинг, какие категории риска встречаются в тексте и что можно изменить, чтобы приблизиться к целевому возрастному порогу.

Система объединяет классический backend, frontend-отчёт и отдельный LLM-сервис: сначала сценарий разбирается на сцены и фрагменты, затем проходит rule/RuBERT-классификацию, после чего Qwen формирует редакционные рекомендации.

> Инструкции запуска будут вынесены отдельно в `QUICK_START.md`.

## Что умеет проект

- Анализирует сценарии в текстовых и документных форматах.
- Определяет фактический возрастной рейтинг по найденным риск-сценам.
- Поддерживает целевой режим анализа: `Raw`, `6+`, `12+`, `16+`, `18+`.
- Показывает только сцены, которые мешают выбранной цели, с возможностью раскрыть полный raw-анализ.
- Группирует Qwen-рекомендации, чтобы ускорить анализ больших сценариев.
- Формирует компактный отчёт: сводка, категории, риск-сцены, evidence и варианты редакционной правки.
- Поддерживает историю анализов, retry проблемных задач, worker-очередь и PDF-выгрузку.
- Учитывает safe-context и ambiguous-context правила, чтобы снижать ложные срабатывания.

## Архитектура

```text
Frontend Nuxt
     |
     v
Backend NestJS ---- PostgreSQL
     |                  |
     |                  v
     +------------ Redis / BullMQ Worker
     |
     v
LLM Service FastAPI
     |
     +-- Parser: txt / pdf / docx
     +-- Rule detector + safe-context
     +-- RuBERT classifier
     +-- Qwen recommendations via Ollama
```

## Технологии

**Frontend**

- Nuxt 4
- Vue 3
- Pinia
- TanStack Vue Query
- Tailwind CSS
- Chart.js
- Sentry/GlitchTip integration

**Backend**

- NestJS 11
- Prisma 7
- PostgreSQL
- Redis + BullMQ
- JWT auth
- PDFKit
- S3-compatible avatar/object storage

**LLM-сервис**

- Python 3.12
- FastAPI + Uvicorn
- PyTorch
- Transformers
- RuBERT
- Natasha, Razdel, Pymorphy2
- pdfplumber, python-docx
- Qwen through Ollama

**Инфраструктура**

- Docker Compose
- GitHub Actions
- PostgreSQL 17
- Redis 7

## Основные директории

```text
backend/          NestJS API, Prisma, queue worker, auth, PDF/report logic
frontend/         Nuxt application and report UI
llm/              FastAPI LLM service, parser, RuBERT, Qwen recommendations
.github/          CI workflow and project-level verification scripts
docker-compose.yaml
```

## Ключевая идея

CleanFrame не просто говорит “здесь есть риск”. Он пытается ответить на более практичный вопрос:

**что именно мешает сценарию пройти выбранный возрастной порог и какую правку можно сделать без разрушения драматургии.**

Поэтому анализ строится вокруг трёх уровней:

- фактический рейтинг сценария;
- выбранная пользователем цель;
- сцены, которые превышают эту цель и требуют внимания.

## Текущий статус

Проект находится в стадии production-hardening: уже есть полноценный full-stack pipeline, очередь задач, LLM-рекомендации, отчёт и базовые quality gates. Дальнейшие приоритеты - калибровка рейтинга, расширение human-labeled golden dataset, улучшение evidence quality и ускорение локального inference.
