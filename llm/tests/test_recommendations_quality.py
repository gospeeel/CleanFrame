import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from llm.tools.evaluation.recommendations_quality import evaluate_dataset, evaluate_suggestion


def recommendation_row() -> dict:
    return {
        "id": "rec-1",
        "source_document": "sample.txt",
        "input": {
            "text": "Hero strikes the attacker in the hallway.",
            "category": "violence",
            "category_label": "Violence",
            "level": 2,
            "rating": "12+",
            "target_rating": "6+",
            "evidence": [{"text": "strikes the attacker", "matched_term": "strikes"}],
        },
        "expected": {
            "summary": "Violence: direct strike should be softened.",
            "explanation": "Violence is present through direct physical contact.",
            "risk_factors": ["strikes the attacker"],
            "rewrite_suggestions": [
                {
                    "goal": "Soft edit",
                    "before": "strikes the attacker",
                    "after": "blocks the attacker",
                    "rationale": "Keeps conflict with less impact.",
                    "expected_effect": "Lowers the violence signal.",
                },
                {
                    "goal": "Strong rating reduction",
                    "before": "strikes the attacker",
                    "after": "steps away from the attacker",
                    "rationale": "Removes physical impact.",
                    "expected_effect": "Reduces age risk.",
                },
                {
                    "goal": "Keep drama while removing risk",
                    "before": "strikes the attacker",
                    "after": "freezes as the attacker approaches",
                    "rationale": "Keeps tension without violence.",
                    "expected_effect": "Keeps drama lower-risk.",
                },
            ],
            "self_check_passed": True,
        },
    }


class RecommendationsQualityTest(unittest.TestCase):
    def test_expected_payload_passes_quality_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "recommendations.jsonl"
            output = Path(tmp) / "report.json"
            dataset.write_text(json.dumps(recommendation_row()) + "\n", encoding="utf-8")

            report = evaluate_dataset(dataset, output, use_expected=True)
            output_exists = output.exists()

        self.assertEqual(report["sample_count"], 1)
        self.assertEqual(report["summary"]["pass_rate"], 1.0)
        self.assertTrue(report["items"][0]["checks"]["before_after_quality_ok"])
        self.assertTrue(output_exists)

    def test_live_payload_reports_fallback_failure(self):
        row = recommendation_row()
        package = {
            "fallback_used": True,
            "fallback_reason": "ollama unavailable",
            "llm_recommendation": row["expected"],
            "recommendation": row["expected"],
        }

        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "recommendations.jsonl"
            output = Path(tmp) / "report.json"
            dataset.write_text(json.dumps(row) + "\n", encoding="utf-8")

            with patch(
                "llm.tools.evaluation.recommendations_quality.generate_recommendation_packages_batch",
                return_value={"rec-1": package},
            ):
                report = evaluate_dataset(dataset, output)

        self.assertEqual(report["summary"]["pass_rate"], 0.0)
        self.assertEqual(report["summary"]["fallback_rate"], 1.0)

    def test_suggestion_quality_requires_changed_after(self):
        context = {
            "text": "Hero strikes the attacker in the hallway.",
            "evidence": [{"text": "strikes the attacker"}],
        }
        item = {
            "goal": "Soft edit",
            "before": "strikes the attacker",
            "after": "strikes the attacker",
            "rationale": "No change.",
            "expected_effect": "No change.",
        }

        result = evaluate_suggestion(item, context)

        self.assertTrue(result["before_grounded"])
        self.assertFalse(result["changed"])
        self.assertFalse(result["quality_ok"])


if __name__ == "__main__":
    unittest.main()
