# ML_WINK datasets

Эта папка предназначена для локальных датасетов LLM-сервиса.

Рекомендуемая структура:

```text
llm/datasets/
  golden/
    validation.jsonl
    test.jsonl
  silver/
    train.jsonl
    validation.jsonl
    test.jsonl
  raw/
  annotation_guidelines.md
```

`golden/*.jsonl` - ручная разметка, на которой считаются метрики. Эти файлы могут содержать чувствительные данные сценариев, поэтому по умолчанию они не должны попадать в git без отдельного решения команды.

`silver/*.jsonl` - синтетические или weak-labeled данные. Их можно использовать для bootstrap, регрессионных проверок и первичного дообучения, но не как финальное доказательство качества production-модели.

Минимальный формат одной строки:

```json
{"id":"sample-001","text":"Текст сцены или реплики","category":"violence","level":2,"source":"manual","notes":"optional"}
```

Обязательные поля:

- `id` - стабильный уникальный идентификатор примера.
- `text` - текст, который отправляется в модель.
- `category` - одна из категорий модели: `safe`, `sexual`, `substance`, `fear`, `violence`, `profanity`.
- `level` - уровень риска `0..4`; `0` используется только для `safe`.

Рекомендуемые дополнительные поля:

- `rating` - ожидаемый возрастной рейтинг, если размечаете end-to-end качество.
- `source` - источник примера: `manual`, `script`, `synthetic`, `production_review`.
- `annotator` - кто разметил пример.
- `notes` - почему выбран такой класс или уровень.

Сгенерировать большой silver dataset:

```bash
cd llm
python3 -m llm.tools.datasets.bootstrap_dataset --samples-per-bucket 30 --output-dir datasets/silver
```

При `--samples-per-bucket 30` получится 630 примеров: `safe` level 0 + 5 риск-категорий * 4 уровня * 30 вариантов.

Если генерация выполняется в Docker с bind mount, используйте `--user "$(id -u):$(id -g)"`, чтобы файлы не создавались от `root`.
