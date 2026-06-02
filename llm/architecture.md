# 🧠 Архитектура LLM-сервиса

> **LLM-сервис CleanFrame** - FastAPI-приложение, которое парсит сценарии, ищет риск-сигналы, классифицирует их через RuBERT и формирует редакционные рекомендации через Qwen/Ollama.

![FastAPI](https://img.shields.io/badge/FastAPI-0.121+-009688?logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-2.6-EE4C2C?logo=pytorch&logoColor=white)
![Transformers](https://img.shields.io/badge/Transformers-4.46+-FFD21E?logo=huggingface&logoColor=black)
![Ollama](https://img.shields.io/badge/Ollama-Qwen-111111)

---

## 🌟 Назначение слоя

LLM-сервис выполняет всю интеллектуальную часть анализа. Backend передаёт файл и целевой рейтинг, а LLM-сервис возвращает структурированный результат: найденные риск-сцены, rating metadata, evidence, рекомендации и статистику.

Ключевые обязанности:

- загрузка и проверка RuBERT-модели;
- парсинг `.txt`, `.pdf`, `.docx`;
- выделение сцен и компактных текстовых элементов;
- rule-based поиск первичных сигналов;
- safe-context подавление ложных срабатываний;
- RuBERT batch inference;
- rating aggregation;
- grouped Qwen recommendations;
- evidence quality и regression tooling;
- health/ready endpoints.

---

## 🏗️ Общая схема

```text
FastAPI /api/analysis/run
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
      +-- recommendations/service.py ---- llm_client.py ---- Ollama/Qwen
      |
      v
structured JSON result
```

---

## 📦 Структура

```text
llm/
├── llm/
│   ├── classification/       # RuBERT model loading и inference
│   ├── core/                 # Runtime status, metrics, model registry, logging
│   ├── detection/            # Rule detector
│   ├── legal/                # Policy basis и legal retrieval
│   ├── legal_knowledge/      # JSONL policy knowledge base
│   ├── lexicons/             # Базовые и расширенные словари
│   ├── parsing/              # Script parser для txt/pdf/docx
│   ├── pipeline/             # Full analysis pipeline и guards
│   ├── recommendations/      # Qwen recommendation service
│   ├── tools/                # Eval, training, datasets, model download
│   ├── llm_client.py         # Клиент Ollama/Qwen
│   ├── rating.py             # Rating policy и aggregation
│   ├── router.py             # FastAPI routes
│   ├── service.py            # Upload validation и запуск pipeline
│   └── taxonomy.py           # Категории, labels, safe-context, evidence
├── datasets/                 # Golden/silver datasets
├── tests/                    # Unit/eval regression tests
├── main.py                   # FastAPI app bootstrap
├── requirements.txt
├── Dockerfile
└── .env.example
```

---

## 🔁 Процесс анализа

```text
1. Backend отправляет файл на /api/analysis/run.
2. service.py валидирует расширение и сохраняет временный файл.
3. Проверяется доступность RuBERT через model_status().
4. full_pipeline запускает parser.
5. rule_detector ищет первичные подозрительные элементы.
6. taxonomy применяет safe-context и ambiguous-context правила.
7. RuBERT классифицирует кандидатов батчами.
8. rating.py рассчитывает rating и агрегирует итог.
9. recommendations/service.py выбирает сцены для Qwen.
10. Qwen генерирует grouped-рекомендации или fallback.
11. Pipeline возвращает JSON с metadata, scenes, evidence и stats.
12. Временный файл удаляется.
```

---

## 🧩 Основные компоненты

### 📄 `parsing/`

Отвечает за разбор сценария:

- чтение `.txt`, `.pdf`, `.docx`;
- нормализацию строк;
- определение сцен;
- ограничение длины фрагментов;
- подготовку элементов для detection.

### 🧭 `detection/` и `taxonomy.py`

Первичный риск-слой:

- словари категорий;
- matched terms;
- category scores;
- safe-context patterns;
- ambiguous adjustments;
- evidence reasons;
- labels категорий и уровней.

### 🤖 `classification/rubert.py`

RuBERT inference:

- проверка файлов модели;
- загрузка tokenizer/config/weights;
- multitask heads для category/level/rating;
- batch prediction;
- confidence metadata.

### 🎚️ `rating.py`

Политика рейтинга:

- mapping rating order;
- category-specific rating rules;
- aggregation итогового max rating;
- confidence/evidence guards;
- снижение unreliable high-risk signals.

### ✍️ `recommendations/`

Редакционные рекомендации:

- режимы `fast`, `full`, `grouped`;
- grouping сцен по category/level/rating/evidence;
- Qwen prompts;
- fallback summary;
- few-shot examples из `datasets/silver/real_text_pseudo`.

### 🧪 `tools/evaluation/`

Качество и regression:

- `quality_gate.py`;
- evidence quality;
- recommendations quality;
- RuBERT compare;
- ambiguous context report;
- Qwen recommendation compare.

---

## 📥 Модели и датасеты

RuBERT скачивается автоматически через:

```text
llm.tools.model_download
```

Источник:

```text
gospeeel/ruBERT-cleanframe
```

Qwen скачивается через Ollama service в Docker Compose:

```text
qwen3:1.7b
```

Few-shot dataset для рекомендаций:

```text
llm/datasets/silver/real_text_pseudo/
```

---

## ⚙️ Важные конфиги

- `RUBERT_MODEL_DIR` - путь к RuBERT.
- `HF_RUBERT_REPO_ID` - Hugging Face repo модели.
- `LLM_PRELOAD_MODEL` - прогрев модели при старте.
- `OLLAMA_BASE_URL` - адрес Ollama.
- `OLLAMA_MODEL` - Qwen model tag.
- `LLM_RECOMMENDATION_MODE` - `fast`, `full`, `grouped`.
- `LLM_RECOMMENDATION_TIME_BUDGET_SECONDS` - бюджет рекомендаций.
- `SCRIPT_PARSER_MAX_ELEMENT_CHARS` - ограничение длины фрагмента.

---

## ✅ Проверки

Основные команды LLM:

```bash
python -m unittest discover tests
python -m llm.tools.evaluation.quality_gate --run-evidence-quality
```

CI дополнительно компилирует Python-код и проверяет taxonomy/regression наборы.
