# Скрипты GitHub CI

В этой папке лежат проектные скрипты, которые запускаются через GitHub Actions. Эти скрипты предназначены только для CI.

- `verify-llm.sh` проверяет LLM-пакет: компиляцию Python-кода, taxonomy-тесты и quality gate.
- `verify-v2-architecture.sh` проверяет связку worker, очереди, Docker Compose, backend и frontend-статусов.
