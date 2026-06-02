import json
import tempfile
import unittest
from pathlib import Path

from llm.tools.datasets.build_qwen_sft_dataset import build_dataset, to_sft_example
from llm.tools.evaluation.qwen_recommendation_compare import compare_reports


def row(row_id: str = "rec-1") -> dict:
    return {
        "id": row_id,
        "source_document": "sample.txt",
        "input": {
            "text": "Hero strikes the attacker.",
            "category": "violence",
            "category_label": "Violence",
            "secondary_categories": [],
            "level": 2,
            "level_label": "moderate",
            "rating": "12+",
            "target_rating": "6+",
            "evidence": [{"text": "strikes the attacker"}],
            "legal_context": [{"id": "policy", "policy_version": "v1", "text": "Violence policy"}],
        },
        "expected": {
            "summary": "Violence: soften direct impact.",
            "explanation": "Direct impact raises the age risk.",
            "risk_factors": ["strikes the attacker"],
            "rewrite_suggestions": [
                {
                    "goal": "Soft edit",
                    "before": "strikes the attacker",
                    "after": "blocks the attacker",
                    "rationale": "Less impact.",
                    "expected_effect": "Lower risk.",
                }
            ] * 3,
            "self_check_passed": True,
        },
        "label_source": "human",
        "needs_human_review": False,
    }


class QwenSftDatasetTest(unittest.TestCase):
    def test_to_sft_example_preserves_guardrails(self):
        example = to_sft_example(row())

        self.assertEqual([item["role"] for item in example["messages"]], ["system", "user", "assistant"])
        self.assertIn("Не меняй категорию", example["messages"][0]["content"])
        self.assertIn("Rating engine facts", example["messages"][1]["content"])
        assistant_payload = json.loads(example["messages"][2]["content"])
        self.assertEqual(assistant_payload["summary"], "Violence: soften direct impact.")
        self.assertEqual(example["metadata"]["label_source"], "human")

    def test_build_dataset_writes_splits_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "recommendations.jsonl"
            output_dir = Path(tmp) / "sft"
            source.write_text("\n".join(json.dumps(row(f"rec-{index}")) for index in range(10)) + "\n", encoding="utf-8")

            manifest = build_dataset(source, output_dir, validation_ratio=0.2, test_ratio=0.2)

            self.assertEqual(manifest["splits"], {"train": 6, "validation": 2, "test": 2})
            self.assertTrue((output_dir / "train.jsonl").exists())
            self.assertTrue((output_dir / "manifest.json").exists())

    def test_qwen_report_compare_requires_improvement(self):
        base = {"summary": {"pass_rate": 0.7, "fallback_rate": 0.1}}
        candidate = {"summary": {"pass_rate": 0.75, "fallback_rate": 0.1}}

        report = compare_reports(base, candidate, min_pass_rate_delta=0.01)

        self.assertTrue(report["passed"])


if __name__ == "__main__":
    unittest.main()
