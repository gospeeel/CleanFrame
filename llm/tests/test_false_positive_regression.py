import json
import tempfile
import unittest
from pathlib import Path

from llm.tools.evaluation.false_positive_regression import evaluate_false_positive_regression


class FalsePositiveRegressionTest(unittest.TestCase):
    def test_false_positive_report_has_required_metrics(self):
        rows = [
            {
                "id": "safe-1",
                "text": "Ане страшно опоздать на поезд, поэтому она ускоряет шаг.",
                "category": "safe",
                "level": 0,
                "rating": "0+",
                "risk_detected": False,
                "expected_evidence": [],
                "notes": "Бытовая тревога.",
                "label_source": "manual_false_positive_regression",
            },
            {
                "id": "risk-1",
                "text": "Герой бьёт противника кулаком, тот падает.",
                "category": "violence",
                "level": 2,
                "rating": "12+",
                "risk_detected": True,
                "expected_evidence": ["бьёт", "падает"],
                "notes": "Явное насилие.",
                "label_source": "manual_false_positive_regression",
            },
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset = Path(tmpdir) / "fp.jsonl"
            output = Path(tmpdir) / "report.json"
            dataset.write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
                encoding="utf-8",
            )

            report = evaluate_false_positive_regression(dataset, output)
            output_exists = output.exists()

        self.assertIn("false_positive_rate", report["summary"])
        self.assertIn("high_risk_false_positive_count", report["summary"])
        self.assertTrue(output_exists)


if __name__ == "__main__":
    unittest.main()
