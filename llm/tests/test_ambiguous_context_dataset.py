import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from llm.detection.rule_detector import is_suspicious_scene
from llm.tools.evaluation.ambiguous_contexts import evaluate_ambiguous_contexts


DATASET = Path(__file__).resolve().parents[1] / "datasets" / "silver" / "ambiguous_contexts.jsonl"


class AmbiguousContextDatasetTest(unittest.TestCase):
    def test_ambiguous_context_dataset_matches_rule_detector(self):
        failures = []
        with DATASET.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                row = json.loads(line)
                result = is_suspicious_scene(row["text"])
                active = {
                    category
                    for category, is_active in result.get("normalized_flags", {}).items()
                    if is_active
                }

                expected_suspicious = bool(row.get("expected_suspicious", False))
                if bool(result.get("is_suspicious")) != expected_suspicious:
                    failures.append(
                        f"{row['id']}:{line_number} expected suspicious={expected_suspicious}, "
                        f"got {bool(result.get('is_suspicious'))}"
                    )

                missing = sorted(set(row.get("required_categories", [])) - active)
                if missing:
                    failures.append(f"{row['id']}:{line_number} missing required {missing}")

                forbidden = sorted(set(row.get("forbidden_categories", [])) & active)
                if forbidden:
                    failures.append(f"{row['id']}:{line_number} forbidden active {forbidden}")

        self.assertEqual(failures, [])

    def test_evaluator_writes_summary_report(self):
        with TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "ambiguous_context_eval.json"
            report = evaluate_ambiguous_contexts(DATASET, output)
            output_exists = output.exists()

        self.assertTrue(output_exists)
        self.assertGreaterEqual(report["summary"]["total"], 50)
        self.assertEqual(report["summary"]["failed"], 0)
        self.assertEqual(report["summary"]["pass_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
