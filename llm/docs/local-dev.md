# Local Development

## Установка

```bash
cd llm
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Ollama

```bash
ollama pull qwen2.5:3b-instruct
```

## Запуск сервиса

```bash
LLM_RECOMMENDATIONS_ENABLED=true \
OLLAMA_BASE_URL=http://127.0.0.1:11434 \
OLLAMA_MODEL=qwen2.5:3b-instruct \
OLLAMA_TIMEOUT_SECONDS=45 \
OLLAMA_RETRY_COUNT=0 \
OLLAMA_NUM_PREDICT=700 \
python -m uvicorn main:app --host 127.0.0.1 --port 8001
```

Для быстрой E2E-проверки можно поставить `OLLAMA_TIMEOUT_SECONDS=15`: если Qwen на CPU не успеет, анализ быстро завершится с шаблонными рекомендациями. Для проверки именно Qwen-рекомендаций ставьте `OLLAMA_TIMEOUT_SECONDS=120`, но на CPU это может быть заметно медленнее.

## Проверки

```bash
python3 -m compileall llm tests
./.venv/bin/python -m unittest tests.test_taxonomy
./.venv/bin/python -m llm.evaluate_golden
curl http://127.0.0.1:8001/api/analysis/health
```

## Частые проблемы

- `No module named 'pkg_resources'`: установите `setuptools` в активное venv.
- `/ready` возвращает 503: проверьте `llm/trained_model`.
- `/api/analysis/health` показывает статус RuBERT и Ollama для диагностики.
- Qwen недоступна: анализ всё равно должен завершиться fallback-рекомендациями.
- Старый анализ в истории не пересчитывается; чтобы увидеть новую классификацию, загрузите файл заново.
