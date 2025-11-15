# evaluate_all_models.py
import torch
import torch.nn.functional as F
import numpy as np
from transformers import AutoTokenizer, AutoModelForSequenceClassification

# Путь к папке с моделями
MODEL_DIR = "models/rubert"

# Возрастная шкала по ФЗ-436
RATING_MAP = {0: "0+", 1: "6+", 2: "12+", 3: "16+", 4: "18+"}

# Список категорий
CATEGORIES = ["profanity", "violence", "erotic", "drugs_alcohol", "fear"]

# Кэширование моделей и токенизаторов
MODELS = {}
TOKENIZERS = {}

def load_models():
    """Загрузка всех 5 моделей в память один раз"""
    print("🔍 Загружаем модели...")
    for cat in CATEGORIES:
        try:
            model_path = f"{MODEL_DIR}/{cat}/final"
            tokenizer = AutoTokenizer.from_pretrained(model_path)
            model = AutoModelForSequenceClassification.from_pretrained(model_path)
            model.eval()
            TOKENIZERS[cat] = tokenizer
            MODELS[cat] = model
            print(f"✅ Загружена модель: {cat}")
        except Exception as e:
            print(f"❌ Ошибка при загрузке {cat}: {e}")
            raise

def classify_text(category, text):
    """Предсказать уровень для одной категории"""
    tokenizer = TOKENIZERS[category]
    model = MODELS[category]

    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        padding=True,
        max_length=256
    )
    with torch.no_grad():
        outputs = model(**inputs)
        probs = F.softmax(outputs.logits, dim=-1)[0].numpy()

    pred_level = int(np.argmax(probs))
    confidence = float(np.max(probs))
    return pred_level, probs, confidence

def classify_scene(text):
    """Агрегация предсказаний всех моделей → итоговый рейтинг по ФЗ-436"""
    results = {}
    max_level = 0

    print(f"\n📄 Анализируем сцену:\n{text}\n{'─' * 50}")

    for cat in CATEGORIES:
        level, probs, conf = classify_text(cat, text)
        results[cat] = {
            "level": level,
            "confidence": conf,
            "probabilities": probs.tolist()
        }
        max_level = max(max_level, level)

        # Визуализация вероятностей
        print(f"🧠 {cat.capitalize()}: уровень {level} ({RATING_MAP[level]}) | Уверенность: {conf:.3f}")
        for i, p in enumerate(probs):
            bar = "█" * int(p * 30)
            print(f"   Ур.{i} ({RATING_MAP[i]}): {p:.3f} {bar}")
        print()

    final_rating = RATING_MAP[max_level]
    print(f"🎯 ИТОГОВЫЙ ВОЗРАСТНОЙ РЕЙТИНГ: {final_rating}")

    # Обоснование по ФЗ-436
    if max_level == 4:
        print("🚨 Причина: обнаружена информация, запрещённая для детей (ст. 5 ч.2 ФЗ-436):")
        print("   - нецензурная брань / сексуальное насилие / порнография и т.п.")
    elif max_level == 3:
        print("⚠️ Причина: информация, допустимая только с 16+ (ст. 10 ФЗ-436):")
        print("   - бранные слова (не мат), жестокость, алкоголь и т.п.")
    elif max_level == 2:
        print("⚠️ Причина: информация, допустимая с 12+ (ст. 9 ФЗ-436):")
        print("   - оскорбления, лёгкое насилие и т.п.")
    elif max_level == 1:
        print("ℹ️ Причина: лёгкое раздражение, допустимо с 6+ (ст. 8 ФЗ-436).")
    else:
        print("✅ Безопасно для всех возрастов (0+).")

    return final_rating, results

def main():
    # Загружаем модели
    load_models()

    # Примеры для теста (замените на свои)
    test_cases = [
        "Ты пошёл нахуй, мразь!",
        "Чёрт, забыл ключи дома.",
        "Я убью тебя, если ты ещё раз так сделаешь.",
        "Давай займёмся сексом прямо здесь.",
        "Выпьем вина за ужином?",
        "Я боюсь темноты в подвале.",
        "Сегодня отличная погода!",
        "Ты как Гитлер, просто ужас.",
        "Пошёл к чёрту со своими проблемами!",
    ]

    print("🧪 Начинаем тестирование моделей...\n")

    for i, text in enumerate(test_cases, 1):
        print(f"\n{'='*60}")
        print(f"ТЕСТ {i}:")
        print(f"{'='*60}")
        classify_scene(text)

    print("\n✅ Всё готово! Модели работают.")

if __name__ == "__main__":
    main()