import os
import json
import torch
from typing import Dict, Any
from transformers import BertTokenizer, BertForSequenceClassification
from glob import glob


# -----------------------------
# CONFIG
# -----------------------------
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

CATEGORIES = [
    "violence",
    "obscene_language",
    "sexual_content",
    "drugs_alcohol",
    "fear"
]

MODEL_ROOT = "models/rubert"     # у тебя модели хранятся там
INPUT_FOLDER = "Example"         # где лежат входные JSON
OUTPUT_SUFFIX = "_rubert"        # к имени файла
MAX_LEN = 256


# -----------------------------
# LOAD MODELS
# -----------------------------
def load_all_models() -> Dict[str, Dict[str, Any]]:
    models = {}
    for cat in CATEGORIES:
        model_path = os.path.join(MODEL_ROOT, cat, "final")
        print(f"🔄 Загрузка модели {cat} из {model_path}")

        tokenizer = BertTokenizer.from_pretrained(model_path)
        model = BertForSequenceClassification.from_pretrained(model_path).to(DEVICE)
        model.eval()

        models[cat] = {"tokenizer": tokenizer, "model": model}

    print("✅ Все модели RuBERT загружены.\n")
    return models


# -----------------------------
# PREDICT FOR ONE CATEGORY
# -----------------------------
def predict_category(text: str, tokenizer, model) -> Dict[str, Any]:
    tokens = tokenizer(
        text,
        padding="max_length",
        truncation=True,
        max_length=MAX_LEN,
        return_tensors="pt"
    ).to(DEVICE)

    with torch.no_grad():
        logits = model(**tokens).logits
        probs = torch.softmax(logits, dim=1).cpu().numpy()[0]

    prediction = int(probs.argmax())
    confidence = float(probs[prediction])

    return {
        "prediction": prediction,     # уровень 0–4
        "confidence": confidence      # уверенность
    }


# -----------------------------
# PROCESS ONE SCENE
# -----------------------------
def process_scene_element(text: str, models) -> Dict[str, Any]:
    result = {}

    for cat in CATEGORIES:
        tokenizer = models[cat]["tokenizer"]
        model = models[cat]["model"]

        result[cat] = predict_category(text, tokenizer, model)

    return result


# -----------------------------
# PROCESS FULL SCRIPT JSON
# -----------------------------
def process_script(json_data: Dict[str, Any], models) -> Dict[str, Any]:
    for scene in json_data.get("scenes", []):
        for element in scene.get("elements", []):
            if "text" in element:
                element["rubert_analysis"] = process_scene_element(
                    element["text"],
                    models
                )
    return json_data


# -----------------------------
# MAIN: PROCESS ALL FILES
# -----------------------------
def main():
    if not os.path.isdir(INPUT_FOLDER):
        print(f"❌ Папка '{INPUT_FOLDER}' не найдена.")
        return

    json_files = glob(os.path.join(INPUT_FOLDER, "*.json"))

    if not json_files:
        print(f"❌ Нет JSON-файлов в '{INPUT_FOLDER}'.")
        return

    models = load_all_models()

    print(f"📁 Найдено {len(json_files)} JSON-файлов для обработки.\n")

    for path in json_files:
        print(f"▶ Обработка: {os.path.basename(path)}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # прогон через RuBERT
        processed = process_script(data, models)

        # формирование пути для записи
        base, ext = os.path.splitext(path)
        output_path = f"{base}{OUTPUT_SUFFIX}{ext}"

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(processed, f, ensure_ascii=False, indent=2)

        print(f"✅ Сохранено: {os.path.basename(output_path)}\n")

    print("🎉 Готово! Все файлы обработаны.")


# -----------------------------
# ENTRY POINT
# -----------------------------
if __name__ == "__main__":
    main()
