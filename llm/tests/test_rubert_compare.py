import unittest
from pathlib import Path

from llm.tools.evaluation.rubert_compare import compare_reports, error_breakdown


def report(category_accuracy: float, level_mae: float, rating_accuracy: float, predictions: list[dict]) -> dict:
    return {
        "sample_count": len(predictions),
        "category_metrics": {"accuracy": category_accuracy, "macro_f1": category_accuracy},
        "level_metrics": {"accuracy": 1.0 - level_mae, "macro_f1": 1.0 - level_mae, "mae": level_mae},
        "rating_metrics": {"accuracy": rating_accuracy, "macro_f1": rating_accuracy},
        "predictions": predictions,
    }


class RubertCompareTest(unittest.TestCase):
    def test_compare_blocks_candidate_with_metric_regression(self):
        current = report(
            category_accuracy=0.9,
            level_mae=0.2,
            rating_accuracy=0.8,
            predictions=[],
        )
        candidate = report(
            category_accuracy=0.7,
            level_mae=0.5,
            rating_accuracy=0.6,
            predictions=[],
        )

        comparison = compare_reports(
            dataset_path=Path("dataset.jsonl"),
            current_report=current,
            candidate_report=candidate,
            current_model_dir=Path("trained_model"),
            candidate_model_dir=Path("candidate"),
        )

        self.assertFalse(comparison["promote_recommended"])
        regression_metrics = {item["metric"] for item in comparison["regressions"]}
        self.assertIn("category_accuracy", regression_metrics)
        self.assertIn("level_mae", regression_metrics)
        self.assertIn("rating_accuracy", regression_metrics)

    def test_compare_allows_equal_or_better_candidate(self):
        current = report(
            category_accuracy=0.8,
            level_mae=0.3,
            rating_accuracy=0.7,
            predictions=[],
        )
        candidate = report(
            category_accuracy=0.82,
            level_mae=0.25,
            rating_accuracy=0.72,
            predictions=[],
        )

        comparison = compare_reports(
            dataset_path=Path("dataset.jsonl"),
            current_report=current,
            candidate_report=candidate,
            current_model_dir=Path("trained_model"),
            candidate_model_dir=Path("candidate"),
        )

        self.assertTrue(comparison["promote_recommended"])
        self.assertEqual(comparison["regressions"], [])

    def test_error_breakdown_counts_false_positives_and_rating_errors(self):
        predictions = [
            {
                "id": "safe-1",
                "text": "Hero hits a ball.",
                "category": "safe",
                "level": 0,
                "rating": "0+",
                "predicted_category": "violence",
                "predicted_level": 2,
                "predicted_rating": "12+",
            },
            {
                "id": "risk-1",
                "text": "A fight starts.",
                "category": "violence",
                "level": 2,
                "rating": "12+",
                "predicted_category": "safe",
                "predicted_level": 0,
                "predicted_rating": "0+",
            },
        ]

        breakdown = error_breakdown(predictions)

        self.assertEqual(breakdown["false_positive_count"], 1)
        self.assertEqual(breakdown["false_negative_count"], 1)
        self.assertEqual(breakdown["rating_error_count"], 2)


if __name__ == "__main__":
    unittest.main()
