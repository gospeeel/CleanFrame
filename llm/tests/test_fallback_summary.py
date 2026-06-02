import unittest

from llm.pipeline.full_pipeline import summarize_fallback_reasons


class FallbackSummaryTest(unittest.TestCase):
    def test_network_timeout_is_grouped_without_raw_http_noise(self):
        summary = summarize_fallback_reasons([
            {
                "fallback_used": True,
                "fallback_reason": "HTTPConnectionPool(host='host.docker.internal', port=11434): Read timed out.",
            },
            {
                "fallback_used": True,
                "fallback_reason": "LLM recommendation skipped by production budget",
            },
        ])

        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["reasons"]["LLM recommendation timed out"], 1)
        self.assertEqual(summary["reasons"]["LLM recommendation time budget exceeded"], 1)
        self.assertNotIn("host.docker.internal", str(summary))


if __name__ == "__main__":
    unittest.main()
