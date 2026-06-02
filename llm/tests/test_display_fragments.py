import unittest

from llm.pipeline.full_pipeline import display_risk_text


class DisplayFragmentsTest(unittest.TestCase):
    def test_display_risk_text_limits_to_three_sentences_around_evidence(self):
        text = (
            "First safe sentence. "
            "Second safe sentence. "
            "The conflict starts near the door. "
            "A удар is heard in the hallway. "
            "Someone calls for help. "
            "The family later talks at the table."
        )
        evidence = [{"matched_term": "удар", "text": "A удар is heard in the hallway."}]

        fragment = display_risk_text(text, evidence)

        self.assertIn("удар", fragment)
        self.assertLessEqual(fragment.count(". "), 2)
        self.assertNotIn("First safe sentence", fragment)
        self.assertNotIn("The family later talks", fragment)


if __name__ == "__main__":
    unittest.main()
