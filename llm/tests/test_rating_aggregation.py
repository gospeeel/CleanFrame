import unittest

from llm.rating import aggregate_project_rating, calculate_rating, calibrate_level_from_evidence


class RatingAggregationTest(unittest.TestCase):
    def test_evidence_terms_raise_minimum_level(self):
        level = calibrate_level_from_evidence("violence", 1, {"violence": ["нож"]})

        self.assertEqual(level, 3)
        self.assertEqual(calculate_rating("violence", level), "16+")

    def test_mild_profanity_can_stay_mild(self):
        level = calibrate_level_from_evidence("profanity", 1, {"profanity": ["нахрен"]})

        self.assertEqual(level, 1)
        self.assertEqual(calculate_rating("profanity", level), "6+")

    def test_single_low_confidence_18_does_not_raise_project_rating(self):
        items = [
            {
                "rating": "12+",
                "confidence": {"rating": 0.55, "level": 0.55},
                "evidence": [{"text": "moderate"}],
            }
            for _ in range(56)
        ]
        items.extend([
            {
                "rating": "6+",
                "confidence": {"rating": 0.55, "level": 0.55},
                "evidence": [{"text": "mild"}],
            }
            for _ in range(23)
        ])
        items.extend([
            {
                "rating": "16+",
                "confidence": {"rating": 0.37, "level": 0.37},
                "evidence": [{"text": "weak high"}],
            }
            for _ in range(2)
        ])
        items.append({
            "rating": "18+",
            "confidence": {"rating": 0.29, "level": 0.29},
            "evidence": [{"text": "weak max"}],
        })

        result = aggregate_project_rating(items)

        self.assertEqual(result["rating"], "12+")
        self.assertEqual(result["technical_max_rating"], "18+")
        self.assertEqual(result["reason"], "dominant_moderate_risk")

    def test_repeated_reliable_18_raises_project_rating(self):
        items = [
            {
                "rating": "18+",
                "category": "substance",
                "confidence": {"rating": 0.8, "level": 0.78},
                "evidence": [{"text": "severe"}],
            },
            {
                "rating": "18+",
                "category": "substance",
                "confidence": {"rating": 0.75, "level": 0.72},
                "evidence": [{"text": "severe"}],
            },
            {
                "rating": "12+",
                "category": "substance",
                "confidence": {"rating": 0.55, "level": 0.55},
                "evidence": [{"text": "adult context"}],
            },
            {
                "rating": "12+",
                "category": "substance",
                "confidence": {"rating": 0.55, "level": 0.55},
                "evidence": [{"text": "adult context"}],
            },
            {
                "rating": "12+",
                "category": "substance",
                "confidence": {"rating": 0.55, "level": 0.55},
                "evidence": [{"text": "adult context"}],
            },
        ]

        result = aggregate_project_rating(items)

        self.assertEqual(result["rating"], "18+")
        self.assertEqual(result["reason"], "repeated_reliable_18_plus")

    def test_repeated_action_only_18_is_capped_at_16(self):
        items = [
            {
                "rating": "18+",
                "category": "violence",
                "confidence": {"rating": 0.8, "level": 0.78},
                "evidence": [{"text": "action violence"}],
            },
            {
                "rating": "18+",
                "category": "violence",
                "confidence": {"rating": 0.75, "level": 0.72},
                "evidence": [{"text": "action violence"}],
            },
        ]

        result = aggregate_project_rating(items)

        self.assertEqual(result["rating"], "16+")
        self.assertEqual(result["reason"], "repeated_reliable_18_plus_action_context")

    def test_action_violence_without_adult_signals_is_moderated_to_12(self):
        items = [
            {
                "rating": "16+",
                "category": "violence",
                "confidence": {"rating": 0.7, "level": 0.7},
                "evidence": [{"text": "action violence"}],
            }
            for _ in range(12)
        ]

        result = aggregate_project_rating(items)

        self.assertEqual(result["rating"], "12+")
        self.assertEqual(result["reason"], "action_violence_moderated_to_12_plus")

    def test_document_level_adult_pattern_raises_project_rating(self):
        items = [
            {
                "rating": "12+",
                "category": "profanity",
                "confidence": {"rating": 0.45, "level": 0.45},
                "evidence": [{"text": "language"}],
            }
            for _ in range(25)
        ]

        result = aggregate_project_rating(items)

        self.assertEqual(result["rating"], "18+")
        self.assertEqual(result["reason"], "document_level_adult_pattern")


if __name__ == "__main__":
    unittest.main()
