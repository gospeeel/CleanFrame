# Быстрый Запуск CleanFrame

## Что понадобится

- Git
- Docker Desktop или Docker Engine с Docker Compose
- Стабильный интернет для первого запуска
- Свободное место на диске: желательно от 5 GB

Python, Node.js, PostgreSQL, Redis и модели вручную ставить не нужно: основной запуск идёт через Docker Compose.

## 1. Клонировать проект

```bash
git clone <URL_РЕПОЗИТОРИЯ>
cd CleanFrame
```

## 2. Проверить env-файлы

Для обычного Docker-запуска копировать `.env.example` не обязательно: `docker-compose.yaml` уже задаёт рабочие значения по умолчанию.

Но если нужно переопределить настройки, создай локальные `.env`:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
cp llm/.env.example llm/.env
```

На Windows PowerShell:

```powershell
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.example frontend/.env
Copy-Item llm/.env.example llm/.env
```

Локальные `.env` не попадают в Git.

## 3. Первый запуск

```bash
docker compose up --build
```

Первый запуск будет долгим, потому что Compose автоматически:

- собирает backend, frontend и LLM-сервис;
- поднимает PostgreSQL и Redis;
- скачивает RuBERT-модель из Hugging Face repo `gospeeel/ruBERT-cleanframe`;
- применяет Prisma migrations;
- создаёт super admin пользователя.

После первого запуска модели сохраняются в Docker volumes, поэтому следующие запуски будут быстрее.

## 4. Адреса сервисов

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- LLM service: http://localhost:8001

## 5. Доступ администратора

По умолчанию создаётся super admin:

```text
login: admin
email: admin@example.com
password: admin123
```

Если хочешь поменять данные, задай в `backend/.env`:

```env
SEED_ADMIN_LOGIN=admin
SEED_ADMIN_EMAIL=admin@example.com
SEED_ADMIN_PASSWORD=admin12345
```

Пароль должен быть не короче 8 символов.

## 6. Проверка готовности

Когда контейнеры поднялись, проверь:

```bash
docker compose ps
```

Backend health:

```bash
curl http://localhost:8000/api/ready
```

LLM health:

```bash
curl http://localhost:8001/ready
```

На Windows PowerShell можно использовать:

```powershell
Invoke-RestMethod http://localhost:8000/api/ready
Invoke-RestMethod http://localhost:8001/ready
```

## 7. Как выполнить первый анализ

1. Открой http://localhost:3000
2. Войди под admin-аккаунтом.
3. Выбери цель анализа: `Raw`, `6+`, `12+`, `16+` или `18+`.
4. Загрузи файл сценария.
5. Дождись отчёта.

Для быстрой проверки можно использовать тестовые файлы из папки `doc/`, например:

```text
doc/test_script_safe.txt
doc/test_script_mixed.pdf
doc/test_script_mixed.docx
```

## 8. Что скачивается автоматически

### RuBERT

Сервис `rubert-model-pull` скачивает модель:

```text
gospeeel/ruBERT-cleanframe
```

Модель сохраняется в Docker volume:

```text
rubert_model
```

## 9. Повторный запуск

После первого успешного запуска достаточно:

```bash
docker compose up
```

Остановить сервисы:

```bash
docker compose down
```

Остановить сервисы и удалить volumes с моделями и базой:

```bash
docker compose down -v
```

После `down -v` следующий запуск снова скачает RuBERT.

## 10. Частые проблемы

### Первый запуск очень долгий

Это нормально. Скачиваются Docker images и RuBERT.

### LLM service не становится healthy

Проверь логи:

```bash
docker compose logs llm
docker compose logs rubert-model-pull
```

Частые причины:

- не скачалась RuBERT-модель;
- нет доступа к Hugging Face;
- не хватает места на диске.

### Backend не стартует после изменения схемы БД

Применение migrations выполняет service `backend-migrate`.

Проверь:

```bash
docker compose logs backend-migrate
```

Если база сломана в локальной разработке и данные не нужны:

```bash
docker compose down -v
docker compose up --build
```

### Порт уже занят

По умолчанию используются:

```text
3000 frontend
8000 backend
8001 llm
5432 postgres
6379 redis
```

Освободи порт или измени mapping в `docker-compose.yaml`.

## 11. Локальная разработка

Для production-like запуска используй Docker Compose.

Для разработки отдельных сервисов можно использовать `.env.example` внутри:

- `backend/.env.example`
- `frontend/.env.example`
- `llm/.env.example`
