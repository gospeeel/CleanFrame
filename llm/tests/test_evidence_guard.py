import unittest

from llm.pipeline.guards import apply_evidence_guard


class EvidenceGuardTest(unittest.TestCase):
    def risky_prediction(self, category: str, level: int = 4) -> dict:
        rating = {1: "6+", 2: "12+", 3: "16+", 4: "18+"}.get(level, "18+")
        return {
            "category": category,
            "level": level,
            "rating": rating,
            "category_confidence": 0.94,
            "level_confidence": 0.86,
            "rating_confidence": 0.84,
            "category_scores": {category: 0.94, "safe": 0.02},
            "level_scores": {str(level): 0.86},
            "rating_scores": {rating: 0.84},
        }

    def test_suppresses_technical_model_only_sexual_high_risk(self):
        prediction = {
            "category": "sexual",
            "level": 4,
            "rating": "18+",
            "category_confidence": 0.92,
            "level_confidence": 0.88,
            "rating_confidence": 0.86,
            "category_scores": {"sexual": 0.92, "safe": 0.03},
            "level_scores": {"4": 0.88},
            "rating_scores": {"18+": 0.86},
        }
        natasha = {
            "matched_terms": {},
            "category_scores": {"sexual": 0.0},
            "normalized_flags": {"sexual": False},
        }
        text = "ТРУДИ Чувствуешь? Хватает малейшего усилия. Ты едва успеваешь подумать - машина уже реагирует."

        guarded, reasons = apply_evidence_guard(prediction, natasha, text)

        self.assertEqual(guarded["category"], "safe")
        self.assertEqual(guarded["level"], 0)
        self.assertEqual(guarded["rating"], "0+")
        self.assertIn("model_only_sexual_without_evidence", reasons)
        self.assertIn("model_only_high_risk_without_evidence", reasons)

    def test_keeps_explicit_sexual_evidence(self):
        prediction = {
            "category": "sexual",
            "level": 2,
            "rating": "12+",
            "category_confidence": 0.8,
            "level_confidence": 0.75,
            "rating_confidence": 0.7,
            "category_scores": {"sexual": 0.8},
            "level_scores": {"2": 0.75},
            "rating_scores": {"12+": 0.7},
        }
        natasha = {
            "matched_terms": {"sexual": ["секс"]},
            "category_scores": {"sexual": 3.0},
            "normalized_flags": {"sexual": True},
        }

        guarded, reasons = apply_evidence_guard(prediction, natasha, "Персонажи прямо обсуждают секс.")

        self.assertEqual(guarded["category"], "sexual")
        self.assertEqual(guarded["level"], 2)
        self.assertEqual(reasons, [])

    def test_suppresses_blood_idiom_as_violence(self):
        natasha = {
            "matched_terms": {"violence": ["кровь"]},
            "category_scores": {"violence": 1.0},
            "normalized_flags": {"violence": True},
        }

        guarded, reasons = apply_evidence_guard(
            self.risky_prediction("violence"),
            natasha,
            "Ты так старалась. Училась кровь из носу. Но результаты тестов не улучшаются.",
        )

        self.assertEqual(guarded["category"], "safe")
        self.assertEqual(guarded["rating"], "0+")
        self.assertIn("safe_context_idiom", reasons)

    def test_suppresses_medical_blood_context(self):
        natasha = {
            "matched_terms": {"violence": ["кровь"]},
            "category_scores": {"violence": 1.0},
            "normalized_flags": {"violence": True},
        }

        guarded, reasons = apply_evidence_guard(
            self.risky_prediction("violence"),
            natasha,
            "Медсестра берёт анализ крови, врач просит пациента не волноваться.",
        )

        self.assertEqual(guarded["category"], "safe")
        self.assertIn("medical_context", reasons)

    def test_suppresses_sport_fall_context(self):
        natasha = {
            "matched_terms": {"violence": ["падает"]},
            "category_scores": {"violence": 1.0},
            "normalized_flags": {"violence": True},
        }

        guarded, reasons = apply_evidence_guard(
            self.risky_prediction("violence", level=2),
            natasha,
            "Фигурист падает на лёд во время тренировки, смеётся и поднимается сам.",
        )

        self.assertEqual(guarded["category"], "safe")
        self.assertIn("sport_context", reasons)

    def test_suppresses_romantic_non_sexual_context(self):
        natasha = {
            "matched_terms": {"sexual": ["страсть"]},
            "category_scores": {"sexual": 1.0},
            "normalized_flags": {"sexual": True},
        }

        guarded, reasons = apply_evidence_guard(
            self.risky_prediction("sexual", level=2),
            natasha,
            "Они держатся за руки на свидании и обсуждают планы на лето.",
        )

        self.assertEqual(guarded["category"], "safe")
        self.assertIn("romantic_non_sexual_context", reasons)

    def test_keeps_explicit_violence_with_strong_evidence(self):
        natasha = {
            "matched_terms": {"violence": ["кровь", "нож"]},
            "category_scores": {"violence": 3.0},
            "normalized_flags": {"violence": True},
        }

        guarded, reasons = apply_evidence_guard(
            self.risky_prediction("violence"),
            natasha,
            "На полу кровь, рядом нож, герой отступает назад.",
        )

        self.assertEqual(guarded["category"], "violence")
        self.assertEqual(guarded["level"], 4)
        self.assertNotIn("medical_context", reasons)


if __name__ == "__main__":
    unittest.main()
