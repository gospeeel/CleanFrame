# 🧠 Архитектура LLM-сервиса

> **LLM-сервис CleanFrame** отвечает за интеллектуальную часть анализа сценария: парсинг, поиск риск-сигналов, классификацию RuBERT, расчёт возрастного рейтинга и быстрые локальные редакционные рекомендации.

![FastAPI](https://img.shields.io/badge/FastAPI-0.121+-009688?logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-2.6-EE4C2C?logo=pytorch&logoColor=white)
![Transformers](https://img.shields.io/badge/Transformers-4.46+-FFD21E?logo=huggingface&logoColor=black)

---

## Назначение

Сервис принимает файл сценария от backend, разбирает его на компактные элементы, находит потенциально рискованный контент и возвращает структурированный JSON для отчёта.

Ключевой принцип текущей архитектуры: **никаких внешних генеративных моделей в runtime**. Рекомендации формируются локально на основе правил, категории, уровня риска, evidence и выбранного целевого рейтинга.

---

## Поток Анализа

```text
POST /api/analysis/run
      |
      v
service.py
      |
      v
pipeline/full_pipeline.py
      |
      +-- parsing/script_parser.py
      +-- detection/rule_detector.py
      +-- taxonomy.py / safe-context
      +-- classification/rubert.py
      +-- rating.py
      +-- recommendations/service.py
      |
      v
structured JSON result
```

1. Backend отправляет файл и, при наличии, целевой рейтинг.
2. `service.py` валидирует файл и запускает pipeline.
3. `script_parser.py` читает `.txt`, `.pdf`, `.docx` и выделяет сцены/элементы.
4. `rule_detector.py` и `taxonomy.py` находят первичные риск-сигналы и применяют safe-context.
5. `rubert.py` батчами классифицирует кандидаты.
6. `rating.py` рассчитывает рейтинг и агрегирует итог.
7. `recommendations/service.py` формирует локальные policy-рекомендации.
8. Pipeline возвращает сцены, evidence, рейтинг, metadata и статистику.

---

## Структура

```text
llm/
├── llm/
│   ├── classification/       # Загрузка RuBERT и batch inference
│   ├── core/                 # Runtime status, metrics, model registry, logging
│   ├── detection/            # Rule detector и первичные сигналы
│   ├── legal/                # Policy basis и retrieval контекста
│   ├── legal_knowledge/      # JSONL-база правового/редакторского контекста
│   ├── lexicons/             # Базовые и расширенные словари
│   ├── parsing/              # Парсер txt/pdf/docx
│   ├── pipeline/             # Главный анализ и evidence guards
│   ├── recommendations/      # Локальные редакционные рекомендации
│   ├── tools/                # Eval, datasets, model download
│   ├── rating.py             # Rating policy и aggregation
│   ├── router.py             # FastAPI routes
│   ├── service.py            # Upload validation и запуск pipeline
│   └── taxonomy.py           # Категории, labels, safe-context, evidence
├── datasets/                 # Golden/silver datasets
├── tests/                    # Unit/eval regression tests
├── main.py                   # FastAPI bootstrap
├── requirements.txt
├── Dockerfile
└── .env.example
```

---

## Основные Компоненты

### `parsing/`

Разбирает входной сценарий:

- читает `.txt`, `.pdf`, `.docx`;
- нормализует строки;
- выделяет сцены и элементы сценария;
- ограничивает слишком длинные фрагменты;
- готовит текст для rule detection и RuBERT.

### `detection/` и `taxonomy.py`

Первичный риск-слой:

- словари категорий;
- matched terms;
- category scores;
- safe-context и ambiguous-context правила;
- evidence reasons;
- labels категорий и уровней риска.

### `classification/rubert.py`

RuBERT inference:

- проверка файлов модели;
- загрузка tokenizer/config/weights;
- multitask heads для category/level/rating;
- batch prediction;
- confidence metadata.

### `rating.py`

Политика возрастного рейтинга:

- порядок рейтингов;
- category-specific rules;
- aggregation итогового рейтинга;
- confidence/evidence guards;
- осторожное снижение unreliable high-risk signals.

### `recommendations/`

Редакционные рекомендации без генеративной модели:

- быстрые policy-based советы по category/level/rating/target rating;
- ровно три варианта правки для UI;
- единый JSON-формат для frontend;
- отсутствие сетевых таймаутов и внешних runtime-зависимостей.

### `tools/evaluation/`

Инструменты качества:

- `quality_gate.py`;
- evidence quality;
- recommendations quality;
- RuBERT compare;
- ambiguous context reports;
- regression-проверки.

---

## Модели И Датасеты

RuBERT скачивается автоматически через:

```text
llm.tools.model_download
```

Источник модели:

```text
gospeeel/ruBERT-cleanframe
```

Silver dataset для оценки и экспериментов:

```text
llm/datasets/silver/real_text_pseudo/
```

---

## Важные Конфиги

- `RUBERT_MODEL_DIR` - путь к RuBERT.
- `HF_RUBERT_REPO_ID` - Hugging Face repo модели.
- `HF_RUBERT_REVISION` - revision модели на Hugging Face.
- `HF_TOKEN` - токен Hugging Face, если модель или лимиты требуют авторизации.
- `LLM_PRELOAD_MODEL` - прогрев модели при старте сервиса.
- `SCRIPT_PARSER_MAX_ELEMENT_CHARS` - ограничение длины фрагмента.

---

## Проверки

```bash
python -m unittest discover tests
python -m llm.tools.evaluation.quality_gate --run-evidence-quality
```

CI дополнительно компилирует Python-код и проверяет regression-наборы.
