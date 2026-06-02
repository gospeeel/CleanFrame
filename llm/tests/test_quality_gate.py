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
                quality_gate.main()

            summary = json.loads((report_dir / "quality_gate_summary.json").read_text(encoding="utf-8"))

        self.assertTrue(summary["passed"])
        self.assertIn("ambiguous_contexts_pass_rate", {item["name"] for item in summary["checks"]})


if __name__ == "__main__":
    unittest.main()
