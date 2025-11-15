# evaluate_rubert.py
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import torch.nn.functional as F
import numpy as np
import json

def classify_text(category, text, model_dir="models/rubert"):
    """
    Возвращает:
      - предсказанный уровень (0–3)
      - вероятность каждого уровня
      - степень уверенности
    """
    model_path = f"{model_dir}/{category}"
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForSequenceClassification.from_pretrained(model_path)
    model.eval()

    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True, max_length=128)
    with torch.no_grad():
        outputs = model(**inputs)
        probs = F.softmax(outputs.logits, dim=-1)[0].numpy()

    pred_level = int(np.argmax(probs))
    confidence = float(np.max(probs))
    return pred_level, probs, confidence

def explain_prediction(category, text):
    level, probs, conf = classify_text(category, text)
    print(f"\n🧠 Категория: {category}")
    print(f"Текст: {text}")
    print(f"➡️ Предсказанный уровень: {level}")
    print(f"📊 Вероятности:")
    for i, p in enumerate(probs):
        bar = "█" * int(p * 40)
        print(f"  Уровень {i}: {p:.3f} {bar}")
    print(f"🎯 Уверенность модели: {conf:.3f}")
    if conf < 0.4:
        print("⚠️ Модель неуверенна — стоит перепроверить этот пример.")
    elif level == 0 and conf < 0.6:
        print("ℹ️ Вероятно, нейтрально, но слабо уверенно.")
    elif level >= 2 and conf > 0.7:
        print("🔥 Модель уверена в высокой степени подозрительности.")

if __name__ == "__main__":
    # 🔧 Примеры для теста
    examples = [
        
        ("Ты как Гитлер", "profanity"),
    ]

    for text, category in examples:
        explain_prediction(category, text)
