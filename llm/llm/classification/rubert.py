import json
from functools import lru_cache
from pathlib import Path
import torch
import numpy as np
from transformers import AutoConfig, AutoTokenizer
import torch.nn as nn
from torch.nn import functional as F
from safetensors.torch import load_file as load_safetensors

from llm.rating import ID_TO_RATING, RATING_ORDER, calculate_rating


MODEL_WEIGHT_FILES = ("model.safetensors", "pytorch_model.bin")
REQUIRED_MODEL_FILES = (
    "category_to_id.json",
    "level_class_weights.npy",
    "level_shift.npy",
    "config.json",
    "tokenizer_config.json",
)

# --- 1. Класс модели (для загрузки) ---

class MultiTaskModel(nn.Module):
    def __init__(self, model_name, num_categories, num_levels, num_ratings=0, level_class_weights=None):
        super().__init__()
        from transformers import AutoModel
        config = AutoConfig.from_pretrained(model_name, local_files_only=True)
        self.bert = AutoModel.from_config(config)
        self.dropout = nn.Dropout(0.3)
        self.category_head = nn.Linear(self.bert.config.hidden_size, num_categories)
        self.level_head = nn.Linear(self.bert.config.hidden_size, num_levels)
        self.rating_head = nn.Linear(self.bert.config.hidden_size, num_ratings) if num_ratings else None

        # Веса не нужны для инференса, но можно сохранить для информации
        if level_class_weights is not None:
            self.level_weights = torch.tensor(level_class_weights, dtype=torch.float32)
        else:
            self.level_weights = None

    def forward(self, input_ids, attention_mask):
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        pooled = outputs.pooler_output
        pooled = self.dropout(pooled)
        cat_logits = self.category_head(pooled)
        lev_logits = self.level_head(pooled)
        rating_logits = self.rating_head(pooled) if self.rating_head is not None else None
        return cat_logits, lev_logits, rating_logits

# --- 2. Загрузка модели и токенизатора ---

def validate_model_dir(model_path: str | Path) -> Path:
    model_path = Path(model_path)
    if not model_path.exists():
        raise FileNotFoundError(f"RuBERT модель не найдена: {model_path}")

    missing = [name for name in REQUIRED_MODEL_FILES if not (model_path / name).exists()]
    if not any((model_path / name).exists() for name in MODEL_WEIGHT_FILES):
        missing.append("model.safetensors или pytorch_model.bin")

    if missing:
        raise FileNotFoundError(
            f"В папке модели {model_path} отсутствуют файлы: {', '.join(missing)}"
        )

    return model_path


def get_model_manifest(model_path: str | Path) -> dict:
    model_path = validate_model_dir(model_path)
    manifest_path = model_path / "model_manifest.json"
    if not manifest_path.exists():
        return {}

    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_state_dict(model_path: Path):
    safetensors_path = model_path / "model.safetensors"
    if safetensors_path.exists():
        return load_safetensors(safetensors_path)

    return torch.load(model_path / "pytorch_model.bin", map_location="cpu", weights_only=True)


@lru_cache(maxsize=1)
def _load_model_and_tokenizer_cached(model_path_str: str):
    model_path = validate_model_dir(model_path_str)

    # Загрузка токенизатора
    tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True)

    # Загрузка маппингов
    with open(model_path / 'category_to_id.json', 'r', encoding='utf-8') as f:
        category_to_id = json.load(f)
    id_to_category = {v: k for k, v in category_to_id.items()}

    rating_to_id = {}
    rating_to_id_path = model_path / "rating_to_id.json"
    if rating_to_id_path.exists():
        with open(rating_to_id_path, "r", encoding="utf-8") as f:
            rating_to_id = json.load(f)

    # Загрузка весов классов (не обязательна, но можно для информации)
    weights_level = np.load(model_path / 'level_class_weights.npy')
    level_shift = np.load(model_path / 'level_shift.npy').item() # 1

    # Инициализация модели
    num_categories = len(category_to_id)  # 5
    num_levels = int(len(weights_level))
    num_ratings = len(rating_to_id)

    model = MultiTaskModel(
        model_name=str(model_path),
        num_categories=num_categories,
        num_levels=num_levels,
        num_ratings=num_ratings,
        level_class_weights=weights_level
    )

    # Загрузка весов
    state_dict = _load_state_dict(model_path)
    model.load_state_dict(state_dict, strict=False)
    model.eval()  # Переводим в режим оценки

    id_to_rating = {v: k for k, v in rating_to_id.items()} if rating_to_id else ID_TO_RATING

    return model, tokenizer, id_to_category, level_shift, id_to_rating


def load_model_and_tokenizer(model_path):
    model_path = validate_model_dir(model_path)
    return _load_model_and_tokenizer_cached(str(model_path.resolve()))


def predict_text(text: str, model_path, max_len: int = 256, device: str | None = None) -> dict:
    text = text.strip()
    if not text:
        raise ValueError("Текст для предсказания пуст")

    model, tokenizer, id_to_category, level_shift, id_to_rating = load_model_and_tokenizer(model_path)
    runtime_device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
    model.to(runtime_device)
    model.eval()

    inputs = tokenizer(
        text,
        truncation=True,
        padding="max_length",
        max_length=max_len,
        return_tensors="pt",
    )
    input_ids = inputs["input_ids"].to(runtime_device)
    attention_mask = inputs["attention_mask"].to(runtime_device)

    with torch.no_grad():
        cat_logits, lev_logits, rating_logits = model(input_ids=input_ids, attention_mask=attention_mask)
        cat_probs = F.softmax(cat_logits, dim=1).cpu().numpy()[0]
        lev_probs = F.softmax(lev_logits, dim=1).cpu().numpy()[0]
        rating_probs = F.softmax(rating_logits, dim=1).cpu().numpy()[0] if rating_logits is not None else None

    cat_pred_id = int(cat_probs.argmax())
    lev_pred_id = int(lev_probs.argmax())
    predicted_category = id_to_category.get(str(cat_pred_id)) or id_to_category.get(cat_pred_id) or "unknown"
    predicted_level = int(lev_pred_id + int(level_shift))
    if predicted_category == "safe":
        predicted_level = 0

    category_scores = {}
    for i, probability in enumerate(cat_probs):
        category = id_to_category.get(str(i)) or id_to_category.get(i) or f"cat_{i}"
        category_scores[category] = float(probability)

    level_scores = {}
    for i, probability in enumerate(lev_probs):
        level_scores[str(int(i + int(level_shift)))] = float(probability)

    rating_scores = {}
    if rating_probs is not None:
        rating_pred_id = int(rating_probs.argmax())
        predicted_rating = id_to_rating.get(str(rating_pred_id)) or id_to_rating.get(rating_pred_id) or RATING_ORDER[rating_pred_id]
        rating_confidence = float(rating_probs[rating_pred_id])
        for i, probability in enumerate(rating_probs):
            rating = id_to_rating.get(str(i)) or id_to_rating.get(i) or RATING_ORDER[i]
            rating_scores[rating] = float(probability)
    else:
        predicted_rating = calculate_rating(predicted_category, predicted_level)
        rating_confidence = min(float(cat_probs[cat_pred_id]), float(lev_probs[lev_pred_id]))

    return {
        "category": predicted_category,
        "level": predicted_level,
        "rating": predicted_rating,
        "category_confidence": float(cat_probs[cat_pred_id]),
        "level_confidence": float(lev_probs[lev_pred_id]),
        "rating_confidence": rating_confidence,
        "category_scores": category_scores,
        "level_scores": level_scores,
        "rating_scores": rating_scores,
    }

# --- 3. Функция предсказания ---

def predict_texts_batch(
    texts: list[str],
    model_path,
    max_len: int = 256,
    device: str | None = None,
    batch_size: int = 16,
) -> list[dict]:
    normalized_texts = [text.strip() for text in texts]
    if any(not text for text in normalized_texts):
        raise ValueError("Text for prediction is empty")
    if not normalized_texts:
        return []

    model, tokenizer, id_to_category, level_shift, id_to_rating = load_model_and_tokenizer(model_path)
    runtime_device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
    model.to(runtime_device)
    model.eval()

    predictions = []
    effective_batch_size = max(1, int(batch_size))
    for start in range(0, len(normalized_texts), effective_batch_size):
        batch_texts = normalized_texts[start:start + effective_batch_size]
        inputs = tokenizer(
            batch_texts,
            truncation=True,
            padding="max_length",
            max_length=max_len,
            return_tensors="pt",
        )
        input_ids = inputs["input_ids"].to(runtime_device)
        attention_mask = inputs["attention_mask"].to(runtime_device)

        with torch.no_grad():
            cat_logits, lev_logits, rating_logits = model(input_ids=input_ids, attention_mask=attention_mask)
            cat_probs_batch = F.softmax(cat_logits, dim=1).cpu().numpy()
            lev_probs_batch = F.softmax(lev_logits, dim=1).cpu().numpy()
            if rating_logits is not None:
                rating_probs_batch = F.softmax(rating_logits, dim=1).cpu().numpy()
            else:
                rating_probs_batch = [None] * len(batch_texts)

        for cat_probs, lev_probs, rating_probs in zip(cat_probs_batch, lev_probs_batch, rating_probs_batch):
            cat_pred_id = int(cat_probs.argmax())
            lev_pred_id = int(lev_probs.argmax())
            predicted_category = id_to_category.get(str(cat_pred_id)) or id_to_category.get(cat_pred_id) or "unknown"
            predicted_level = int(lev_pred_id + int(level_shift))
            if predicted_category == "safe":
                predicted_level = 0

            category_scores = {}
            for i, probability in enumerate(cat_probs):
                category = id_to_category.get(str(i)) or id_to_category.get(i) or f"cat_{i}"
                category_scores[category] = float(probability)

            level_scores = {}
            for i, probability in enumerate(lev_probs):
                level_scores[str(int(i + int(level_shift)))] = float(probability)

            rating_scores = {}
            if rating_probs is not None:
                rating_pred_id = int(rating_probs.argmax())
                predicted_rating = (
                    id_to_rating.get(str(rating_pred_id))
                    or id_to_rating.get(rating_pred_id)
                    or RATING_ORDER[rating_pred_id]
                )
                rating_confidence = float(rating_probs[rating_pred_id])
                for i, probability in enumerate(rating_probs):
                    rating = id_to_rating.get(str(i)) or id_to_rating.get(i) or RATING_ORDER[i]
                    rating_scores[rating] = float(probability)
            else:
                predicted_rating = calculate_rating(predicted_category, predicted_level)
                rating_confidence = min(float(cat_probs[cat_pred_id]), float(lev_probs[lev_pred_id]))

            predictions.append({
                "category": predicted_category,
                "level": predicted_level,
                "rating": predicted_rating,
                "category_confidence": float(cat_probs[cat_pred_id]),
                "level_confidence": float(lev_probs[lev_pred_id]),
                "rating_confidence": rating_confidence,
                "category_scores": category_scores,
                "level_scores": level_scores,
                "rating_scores": rating_scores,
            })

    return predictions


def predict(input_json_path, output_json_path, model_path='trained_model', max_len=128):
    """
    Функция для фильтрации и предсказания category и level для подозрительных элементов сценария.

    Args:
        input_json_path (str): Путь к входному JSON файлу.
        output_json_path (str): Путь, куда сохранить результат.
        model_path (str): Путь к папке с обученной моделью.
        max_len (int): Максимальная длина токенизированного текста.
    """
    # Загружаем модель и токенизатор
    print("Загружаем модель и токенизатор...")
    model, tokenizer, id_to_category, level_shift, id_to_rating = load_model_and_tokenizer(model_path)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model.to(device)
    print("Модель загружена.")

    # Загружаем JSON
    with open(input_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Подготовим список для обработанных элементов
    processed_elements = []

    # Обрабатываем сцены
    for scene in data['scenes']:
        for element in scene['elements']:
            # Проверяем, является ли элемент подозрительным
            natasha_flags = element.get('natasha_flags', {})
            is_suspicious = natasha_flags.get('is_suspicious', False)

            if is_suspicious:
                print(f"Обрабатываю подозрительный элемент: {element.get('text', '')[:50]}...")

                # Собираем текст для анализа
                text_to_analyze = element.get('text', '')
                character_text = element.get('character', '')
                full_text = f"{character_text} {text_to_analyze}".strip()

                if not full_text:
                    print("  - Текст пуст, пропускаем.")
                    continue

                # Токенизация
                inputs = tokenizer(
                    full_text,
                    truncation=True,
                    padding='max_length',
                    max_length=max_len,
                    return_tensors='pt'
                )

                input_ids = inputs['input_ids'].to(device)
                attention_mask = inputs['attention_mask'].to(device)

                # Предсказание
                with torch.no_grad():
                    cat_logits, lev_logits, rating_logits = model(input_ids=input_ids, attention_mask=attention_mask)

                    cat_probs = F.softmax(cat_logits, dim=1)
                    lev_probs = F.softmax(lev_logits, dim=1)

                    cat_pred_id = torch.argmax(cat_probs, dim=1).item()
                    lev_pred_id = torch.argmax(lev_probs, dim=1).item()

                    # Преобразование ID в имя категории
                    predicted_category = id_to_category.get(cat_pred_id, "unknown_category")
                    # Преобразование уровня (0–3) -> (1–4)
                    predicted_level = lev_pred_id + level_shift

                # Создаём новый элемент с минимальной информацией + результатами модели
                processed_element = {
                    "scene_id": scene['scene_id'],
                    "scene_header": scene['header'],
                    "type": element['type'],
                    "character": element.get('character', ''),
                    "text": element.get('text', ''),
                    "model_flags": {
                        "category": predicted_category,
                        "level": predicted_level,
                        "category_confidence": cat_probs[0][cat_pred_id].item(),
                        "level_confidence": lev_probs[0][lev_pred_id].item()
                    }
                }

                processed_elements.append(processed_element)
                print(f"  - Добавлено в результат: category={predicted_category}, level={predicted_level}, conf_cat={cat_probs[0][cat_pred_id].item():.3f}, conf_lev={lev_probs[0][lev_pred_id].item():.3f}")
            

    # Формируем итоговый JSON
    output_data = {
        "processed_elements": processed_elements
    }

    # Сохраняем обновлённый JSON
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"✅ Результат сохранён в {output_json_path}")

# --- 4. Пример запуска ---
if __name__ == "__main__":
    # Укажите пути к вашим файлам
    input_path = "example/Трек 3 - тестовый образец_natasha.json"        # Входной JSON
    output_path = "output_script.json"      # Выходной JSON
    model_dir = "trained_model"             # Папка с моделью

    predict(input_path, output_path, model_dir)
