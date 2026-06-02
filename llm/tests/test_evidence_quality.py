import json
import tempfile
import unittest
from pathlib import Path

from llm.tools.evaluation.evidence_quality import evaluate_evidence_quality


class EvidenceQualityTest(unittest.TestCase):
    def test_expected_evidence_terms_are_reported(self):
        rows = [
            {
                "id": "risk-hit",
                "text": "Герой держит нож для торта на кухне.",
                "expected_primary_category": "safe",
                "expected_secondary_categories": [],
                "expected_level": 0,
                "expected_rating": "0+",
                "expected_risk_detected": False,
                "expected_evidence": [],
            },
            {
                "id": "violence-hit",
                "text": "Завязывается драка, слышен удар.",
                "expected_primary_category": "violence",
                "expected_secondary_categories": [],
                "expected_level": 2,
                "expected_rating": "12+",
                "expected_risk_detected": True,
                "expected_evidence": ["драка", "удар"],
            },
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            dataset = Path(tmpdir) / "golden.jsonl"
            output = Path(tmpdir) / "evidence.json"
            dataset.write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
                encoding="utf-8",
            )

            report = evaluate_evidence_quality(dataset, output, mode="rules")
            output_exists = output.exists()

        self.assertIn("evidence_accuracy", report["summary"])
        self.assertIn("evidence_term_recall", report["summary"])
        self.assertEqual(report["summary"]["false_positive_count"], 0)
        self.assertTrue(output_exists)


if __name__ == "__main__":
    unittest.main()
