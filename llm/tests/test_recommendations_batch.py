import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from llm.llm_client import LlmResult
from llm.recommendations import service


def sample_context(item_id: str = "rec-1", category_label: str = "Violence") -> dict:
    return {
        "id": item_id,
        "text": "Hero strikes the attacker.",
        "category": "violence",
        "category_label": category_label,
        "secondary_categories": [],
        "secondary_labels": [],
        "level": 2,
        "level_label": "moderate",
        "rating": "12+",
        "target_rating": "6+",
        "evidence": [{"text": "strikes the attacker", "matched_term": "strikes"}],
        "confidence": {"category": 0.9, "level": 0.8, "rating": 0.7},
        "needs_review": False,
        "element_type": "action",
        "character": "",
        "legal_context": [{"text": "Violence context"}],
        "policy_basis": "Policy basis",
        "fallback_text": "Fallback recommendation",
        "fallback_payload": {
            "summary": "Violence fallback summary",
            "explanation": "Fallback recommendation",
            "risk_factors": ["strikes the attacker"],
            "rewrite_suggestions": [
                {
                    "goal": "Soft edit",
                    "before": "strikes",
                    "after": "pushes away",
                    "rationale": "Less detail",
                    "expected_effect": "Lower risk",
                }
            ],
            "self_check_passed": True,
            "uncertainty_note": None,
        },
    }


def payload_item(item_id: str = "rec-1") -> dict:
    return {
        "id": item_id,
        "summary": "Violence: concise risk summary",
        "explanation": "Violence is present, but can be softened.",
        "risk_factors": ["strikes the attacker"],
        "rewrite_suggestions": [
            {
                "goal": "Soft edit",
                "before": "strikes the attacker",
                "after": "blocks the attacker",
                "rationale": "Keeps conflict with less impact.",
                "expected_effect": "May lower the age risk.",
            },
            {
                "goal": "Strong rating reduction",
                "before": "strikes the attacker",
                "after": "steps back from the attacker",
                "rationale": "Removes physical impact.",
                "expected_effect": "Reduces violence signal.",
            },
            {
                "goal": "Keep drama while removing risk",
                "before": "strikes the attacker",
                "after": "the confrontation freezes in silence",
                "rationale": "Keeps tension without violence.",
                "expected_effect": "Keeps drama lower-risk.",
            },
        ],
        "self_check_passed": True,
        "uncertainty_note": None,
    }


class RecommendationBatchTest(unittest.TestCase):
    def setUp(self):
        self.env_patcher = patch.dict("os.environ", {"LLM_RECOMMENDATION_MODE": "fast"})
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    def test_batch_success_uses_llm_payload(self):
        context = sample_context()
        result = LlmResult(payload={"items": [payload_item()]}, fallback_used=False)

        with patch.object(service, "call_ollama_json", return_value=result):
            packages = service.generate_recommendation_packages_batch([context])

        package = packages["rec-1"]
        self.assertFalse(package["fallback_used"])
        self.assertIn("Violence is present", package["text"])
        self.assertNotIn("Было:", package["text"])
        self.assertNotIn("Стало:", package["text"])
        self.assertIn("Что изменить:", package["text"])
        self.assertEqual(package["recommendation"]["summary"], "Violence: concise risk summary")

    def test_batch_missing_item_falls_back_for_that_item(self):
        context = sample_context()
        result = LlmResult(payload={"items": []}, fallback_used=False)

        with patch.object(service, "call_ollama_json", return_value=result):
            packages = service.generate_recommendation_packages_batch([context])

        package = packages["rec-1"]
        self.assertTrue(package["fallback_used"])
        self.assertIn("missing item", package["fallback_reason"])
        self.assertEqual(package["text"], "Fallback recommendation")

    def test_batch_ollama_error_falls_back_for_all_items(self):
        contexts = [sample_context("rec-1"), sample_context("rec-2")]
        result = LlmResult(payload=None, fallback_used=True, error="ollama unavailable")

        with patch.object(service, "call_ollama_json", return_value=result):
            packages = service.generate_recommendation_packages_batch(contexts)

        self.assertEqual(set(packages), {"rec-1", "rec-2"})
        self.assertTrue(all(package["fallback_used"] for package in packages.values()))
        self.assertTrue(all(package["fallback_reason"] == "ollama unavailable" for package in packages.values()))

    def test_batch_prompt_can_include_pseudo_tuned_examples(self):
        example = {
            "input": {
                "text": "Hero strikes an attacker in a hallway.",
                "category": "violence",
                "category_label": "Violence",
                "level": 2,
                "rating": "12+",
                "target_rating": "6+",
                "evidence": [{"text": "strikes an attacker"}],
            },
            "expected": {
                "summary": "Violence: soften direct physical impact.",
                "explanation": "Reduce explicit contact while preserving tension.",
                "risk_factors": ["direct strike"],
                "rewrite_suggestions": [
                    {
                        "goal": "Soft edit",
                        "before": "strikes an attacker",
                        "after": "blocks an attacker",
                        "rationale": "Less direct impact.",
                        "expected_effect": "Lower violence signal.",
                    }
                ],
                "self_check_passed": True,
            },
        }

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "examples.jsonl"
            path.write_text(json.dumps(example) + "\n", encoding="utf-8")

            service.load_recommendation_examples.cache_clear()
            with patch.dict(
                "os.environ",
                {
                    "LLM_RECOMMENDATION_EXAMPLES_PATH": str(path),
                    "LLM_RECOMMENDATION_EXAMPLES_LIMIT": "1",
                },
            ):
                messages = service.build_batch_messages([sample_context()])

        self.assertIn("Reference examples", messages[1]["content"])
        self.assertIn("soften direct physical impact", messages[1]["content"])

    def test_fast_batch_prompt_is_compact(self):
        messages = service.build_fast_batch_messages([sample_context()])

        self.assertIn('"items"', messages[1]["content"])
        self.assertIn("rec-1", messages[1]["content"])
        self.assertLess(len(messages[1]["content"]), 2500)

    def test_split_llm_contexts_prioritizes_high_rating_with_evidence(self):
        low = sample_context("low")
        low["rating"] = "6+"
        low["evidence"] = []
        high = sample_context("high")
        high["rating"] = "18+"
        high["evidence"] = [{"text": "severe evidence"}]

        selected, skipped = service.split_llm_contexts([low, high], limit=1)

        self.assertEqual([item["id"] for item in selected], ["high"])
        self.assertEqual([item["id"] for item in skipped], ["low"])

    def test_zero_llm_item_limit_means_unlimited(self):
        contexts = [sample_context("rec-1"), sample_context("rec-2")]

        selected, skipped = service.split_llm_contexts(contexts, limit=0)

        self.assertEqual([item["id"] for item in selected], ["rec-1", "rec-2"])
        self.assertEqual(skipped, [])

    def test_grouping_keeps_categories_separate(self):
        violence = sample_context("violence-1", "Violence")
        fear = sample_context("fear-1", "Fear")
        fear["category"] = "fear"
        fear["category_label"] = "Fear"

        groups, skipped = service.build_recommendation_groups([violence, fear], max_representatives=6, max_groups=24)

        self.assertEqual(skipped, [])
        self.assertEqual(len(groups), 2)
        self.assertEqual({group["category"] for group in groups}, {"violence", "fear"})

    def test_grouped_payload_is_applied_to_every_scene_in_group(self):
        contexts = [sample_context("rec-1"), sample_context("rec-2")]
        result = LlmResult(
            payload={
                "groups": [
                    {
                        "group_id": "group-1",
                        "applies_to_ids": ["rec-1", "rec-2"],
                        **{key: value for key, value in payload_item("ignored").items() if key != "id"},
                    }
                ]
            },
            fallback_used=False,
        )

        with patch.object(service, "call_ollama_json", return_value=result):
            packages = service.generate_grouped_recommendation_packages(
                contexts,
                deadline=9999999999.0,
                timeout_seconds=1.0,
            )

        self.assertEqual(set(packages), {"rec-1", "rec-2"})
        self.assertFalse(packages["rec-1"]["fallback_used"])
        self.assertEqual(packages["rec-1"]["grouped_recommendation_id"], "group-1")
        self.assertEqual(packages["rec-2"]["grouped_recommendation_ids"], ["rec-1", "rec-2"])

    def test_grouped_mode_uses_group_num_predict(self):
        context = sample_context("rec-1")
        result = LlmResult(
            payload={
                "groups": [
                    {
                        "group_id": "group-1",
                        "applies_to_ids": ["rec-1"],
                        **{key: value for key, value in payload_item("ignored").items() if key != "id"},
                    }
                ]
            },
            fallback_used=False,
        )

        with patch.dict("os.environ", {
            "LLM_RECOMMENDATION_GROUP_NUM_PREDICT": "333",
            "LLM_RECOMMENDATION_GROUP_SUMMARY_ONLY": "false",
        }):
            with patch.object(service, "call_ollama_json", return_value=result) as call:
                service.generate_grouped_recommendation_packages(
                    [context],
                    deadline=9999999999.0,
                    timeout_seconds=1.0,
                )

        self.assertEqual(call.call_args.kwargs["num_predict"], 333)

    def test_grouped_summary_only_adds_deterministic_rewrites(self):
        context = sample_context("rec-1")
        result = LlmResult(
            payload={
                "groups": [
                    {
                        "group_id": "group-1",
                        "applies_to_ids": ["rec-1"],
                        "summary": "Violence: concise risk summary",
                        "explanation": "Violence can be softened while preserving tension.",
                        "risk_factors": ["direct strike"],
                        "self_check_passed": True,
                        "uncertainty_note": None,
                    }
                ]
            },
            fallback_used=False,
        )

        with patch.dict("os.environ", {
            "LLM_RECOMMENDATION_GROUP_SUMMARY_ONLY": "true",
            "LLM_RECOMMENDATION_GROUP_SUMMARY_NUM_PREDICT": str(service.DEFAULT_GROUP_SUMMARY_NUM_PREDICT),
        }):
            with patch.object(service, "call_ollama_json", return_value=result) as call:
                packages = service.generate_grouped_recommendation_packages(
                    [context],
                    deadline=9999999999.0,
                    timeout_seconds=1.0,
                )

        self.assertFalse(packages["rec-1"]["fallback_used"])
        self.assertEqual(call.call_args.kwargs["num_predict"], service.DEFAULT_GROUP_SUMMARY_NUM_PREDICT)
        self.assertEqual(
            packages["rec-1"]["recommendation"]["rewrite_suggestions"],
            context["fallback_payload"]["rewrite_suggestions"],
        )

    def test_grouped_timeout_falls_back_only_for_failed_group(self):
        violence = sample_context("violence-1", "Violence")
        fear = sample_context("fear-1", "Fear")
        fear["category"] = "fear"
        fear["category_label"] = "Fear"
        success = LlmResult(
            payload={
                "groups": [
                    {
                        "group_id": "group-2",
                        "applies_to_ids": ["fear-1"],
                        "summary": "Fear: concise risk summary",
                        "explanation": "Fear can be softened while preserving tension.",
                        "risk_factors": ["fearful moment"],
                        "rewrite_suggestions": payload_item("ignored")["rewrite_suggestions"],
                        "self_check_passed": True,
                        "uncertainty_note": None,
                    }
                ]
            },
            fallback_used=False,
        )

        with patch.object(service, "call_ollama_json", side_effect=[
            LlmResult(payload=None, fallback_used=True, error="timeout"),
            success,
        ]):
            packages = service.generate_grouped_recommendation_packages(
                [violence, fear],
                deadline=9999999999.0,
                timeout_seconds=1.0,
            )

        self.assertTrue(packages["violence-1"]["fallback_used"])
        self.assertFalse(packages["fear-1"]["fallback_used"])


if __name__ == "__main__":
    unittest.main()
