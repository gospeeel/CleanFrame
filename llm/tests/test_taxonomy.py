import unittest

from llm.detection.rule_detector import is_suspicious_scene
from llm.legal.retrieval import retrieve_legal_context
from llm.taxonomy import (
    category_label,
    normalize_category,
    primary_category_from_evidence,
    score_curated_terms,
)


class TaxonomyTest(unittest.TestCase):
    def test_category_aliases_have_russian_labels(self):
        self.assertEqual(normalize_category("scary"), "fear")
        self.assertEqual(normalize_category("drugs_alcohol"), "substance")
        self.assertEqual(normalize_category("erotic"), "sexual")
        self.assertEqual(category_label("scary"), "Пугающие сцены")

    def test_fight_scene_prefers_violence_over_fear_prediction(self):
        natasha = is_suspicious_scene(
            "Олег выходит из тени и резко хватает незнакомца за рукав. "
            "Завязывается короткая драка, слышен удар, незнакомец падает на пол."
        )

        primary, secondary = primary_category_from_evidence("fear", natasha)

        self.assertEqual(primary, "violence")
        self.assertIn("fear", secondary)

    def test_fear_scene_without_violence_stays_fear(self):
        natasha = is_suspicious_scene(
            "В темном коридоре слышится странный звук. Марине страшно, она видит тень."
        )

        primary, secondary = primary_category_from_evidence("fear", natasha)

        self.assertEqual(primary, "fear")
        self.assertNotIn("violence", secondary)

    def test_neutral_sentence_does_not_match_profanity(self):
        scores, matches = score_curated_terms("Марина спокойно читает письмо и закрывает окно.")

        self.assertEqual(scores["profanity"], 0)
        self.assertEqual(matches["profanity"], [])

    def test_safe_contexts_do_not_raise_risk(self):
        examples = [
            ("Олег ударил по мячу, и игра продолжилась.", "violence"),
            ("Ане страшно опоздать на поезд.", "fear"),
            ("Марина режет торт ножом для торта.", "violence"),
        ]

        for text, category in examples:
            with self.subTest(text=text):
                natasha = is_suspicious_scene(text)
                self.assertFalse(natasha["normalized_flags"].get(category, False))

    def test_legal_retrieval_uses_evidence_terms(self):
        context = retrieve_legal_context(
            category="violence",
            level=4,
            rating="18+",
            text="После удара видна кровь и рана.",
            evidence=[
                {"matched_term": "кровь", "text": "видна кровь"},
                {"matched_term": "рана", "text": "рана"},
            ],
        )

        self.assertGreaterEqual(len(context), 1)
        self.assertEqual(context[0]["category"], "violence")
        self.assertIn("кровь", context[0]["matched_evidence_terms"])
        self.assertEqual(context[0]["id"], "policy-violence-severe")
        self.assertIn("level", context[0]["retrieval_reason"])
        self.assertIn("evidence", context[0]["retrieval_reason"])

    def test_legal_retrieval_prefers_level_specific_context(self):
        mild = retrieve_legal_context(
            category="violence",
            level=1,
            rating="6+",
            text="Герой толкает соседа, конфликт сразу прекращается.",
            evidence=[{"matched_term": "толкает", "text": "Герой толкает соседа"}],
            limit=1,
        )
        severe = retrieve_legal_context(
            category="violence",
            level=4,
            rating="18+",
            text="После нападения видны кровь, рана и тяжелые травмы.",
            evidence=[
                {"matched_term": "кровь", "text": "видны кровь и рана"},
                {"matched_term": "рана", "text": "рана"},
            ],
            limit=1,
        )

        self.assertEqual(mild[0]["id"], "policy-violence-mild")
        self.assertEqual(severe[0]["id"], "policy-violence-severe")
        self.assertGreater(severe[0]["retrieval_score"], mild[0]["retrieval_score"])

    def test_legal_retrieval_has_safe_context(self):
        context = retrieve_legal_context(
            category="safe",
            level=0,
            rating="0+",
            text="Друзья спокойно обсуждают учебу и планы на выходные.",
            evidence=[],
            limit=1,
        )

        self.assertEqual(context[0]["id"], "policy-safe-general")
        self.assertEqual(context[0]["policy_version"], "2026-05-28")


if __name__ == "__main__":
    unittest.main()
