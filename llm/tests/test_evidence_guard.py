import unittest

from llm.pipeline.guards import apply_evidence_guard


class EvidenceGuardTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
