import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from llm.tools.evaluation import quality_gate


class QualityGateTest(unittest.TestCase):
    def test_ambiguous_contexts_run_by_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir)
            argv = ["quality_gate", "--report-dir", str(report_dir)]
            stdout = io.StringIO()

            with (
                patch("sys.argv", argv),
                patch("llm.tools.evaluation.quality_gate.evaluate_golden") as golden,
                patch("llm.tools.evaluation.quality_gate.evaluate_ambiguous_contexts") as ambiguous,
                patch("llm.tools.evaluation.quality_gate.evaluate_false_positive_regression") as false_positive,
                redirect_stdout(stdout),
            ):
                golden.return_value = {
                    "failed": 0,
                    "total": 1,
                    "passed": 1,
                    "evidence_accuracy": 1.0,
                    "failures": [],
                    "items": [],
                }
                ambiguous.return_value = {
                    "summary": {
                        "total": 50,
                        "passed": 50,
                        "failed": 0,
                        "pass_rate": 1.0,
                    },
                    "failures": [],
                }
                false_positive.return_value = {
                    "summary": {
                        "total": 16,
                        "passed": 16,
                        "failed": 0,
                        "pass_rate": 1.0,
                        "high_risk_false_positive_count": 0,
                        "false_positive_by_category": {},
                    },
                    "failures": [],
                }
                quality_gate.main()

            summary = json.loads((report_dir / "quality_gate_summary.json").read_text(encoding="utf-8"))

        self.assertTrue(summary["passed"])
        check_names = {item["name"] for item in summary["checks"]}
        self.assertIn("ambiguous_contexts_pass_rate", check_names)
        self.assertIn("false_positive_regression_pass_rate", check_names)
        self.assertIn("false_positive_high_risk_zero", check_names)


if __name__ == "__main__":
    unittest.main()
