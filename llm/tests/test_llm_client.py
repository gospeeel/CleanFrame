import unittest
from unittest.mock import patch

from llm.llm_client import ollama_options


class LlmClientOptionsTest(unittest.TestCase):
    def test_ollama_options_include_runtime_tuning_env(self):
        with patch.dict(
            "os.environ",
            {
                "OLLAMA_TEMPERATURE": "0.1",
                "OLLAMA_NUM_CTX": "2048",
                "OLLAMA_NUM_THREAD": "6",
                "OLLAMA_NUM_BATCH": "128",
                "OLLAMA_NUM_GPU": "999",
                "OLLAMA_TOP_P": "0.8",
            },
            clear=True,
        ):
            options = ollama_options(520)

        self.assertEqual(options["temperature"], 0.1)
        self.assertEqual(options["num_predict"], 520)
        self.assertEqual(options["num_ctx"], 2048)
        self.assertEqual(options["num_thread"], 6)
        self.assertEqual(options["num_batch"], 128)
        self.assertEqual(options["num_gpu"], 999)
        self.assertEqual(options["top_p"], 0.8)

    def test_ollama_options_json_can_override_defaults(self):
        with patch.dict(
            "os.environ",
            {
                "OLLAMA_OPTIONS_JSON": '{"temperature":0.05,"repeat_penalty":1.05}',
            },
            clear=True,
        ):
            options = ollama_options(300)

        self.assertEqual(options["num_predict"], 300)
        self.assertEqual(options["temperature"], 0.05)
        self.assertEqual(options["repeat_penalty"], 1.05)


if __name__ == "__main__":
    unittest.main()
