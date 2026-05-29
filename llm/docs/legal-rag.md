# Legal/RAG Notes

Локальный Legal/RAG слой не является юридическим заключением. Он даёт редакторский policy context для рекомендаций и объясняет, какие признаки сцены повлияли на возрастной риск.

## Current Retrieval

- Source: локальная JSONL база `llm/llm/legal_knowledge/policy.jsonl`.
- Retrieval keys: `category`, `level`, `rating`, `evidence_terms`.
- Ranking: сначала совпадение категории, затем попадание в диапазон `min_level/max_level`, совпадение `rating` и пересечение evidence terms.
- Output: найденные policy entries возвращаются в `legal_context` вместе с `retrieval_score`, `retrieval_reason`, `matched_evidence_terms`, `policy_version`.

## Vector Search Decision

Vector search пока не добавляем.

Причина: текущая база маленькая, доменная и структурированная. Для неё keyword/category retrieval проще проверять тестами, он воспроизводимее и не требует отдельного embedding model lifecycle. Vector search имеет смысл рассмотреть позже, если legal knowledge base станет большой и появятся измеримые проблемы качества у keyword retrieval.

Минимальный критерий для возврата к vector search:

- есть отдельный Legal/RAG eval set;
- keyword retrieval показывает недостаточное качество;
- добавлены метрики top-k hit rate и evidence match rate;
- определён lifecycle embedding-модели и версионирование индекса.
