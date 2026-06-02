import tempfile
import unittest
from pathlib import Path

from llm.tools.evaluation.ambiguous_context_report import build_report


class AmbiguousContextReportTest(unittest.TestCase):
    def test_report_collects_remaining_suspicious_terms(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            input_dir = Path(tmpdir)
            (input_dir / "sample.txt").write_text(
                "Училась кровь из носу. После удара видна кровь и рана.",
                encoding="utf-8",
            )

            report = build_report(input_dir, max_samples=2, max_chars=120)

        terms = {(item["category"], item["term"]) for item in report["top_terms"]}
        self.assertIn(("violence", "удар"), terms)
        self.assertIn(("violence", "кровь"), terms)
        self.assertNotIn(("violence", "кровь из носу"), terms)


if __name__ == "__main__":
    unittest.main()
