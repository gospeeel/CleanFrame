import json
import tempfile
import unittest
from pathlib import Path

from llm.core.model_registry import append_model_audit_event, register_model, rollback_model


class ModelRegistryAuditTest(unittest.TestCase):
    def test_append_model_audit_event_writes_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            append_model_audit_event(
                action="model.switched",
                role="rubert",
                previous={"model_name": "old"},
                current={"model_name": "new"},
                path=path,
            )

            events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(events[0]["action"], "model.switched")
        self.assertEqual(events[0]["role"], "rubert")
        self.assertEqual(events[0]["previous"]["model_name"], "old")
        self.assertEqual(events[0]["current"]["model_name"], "new")

    def test_register_and_rollback_update_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry_path = Path(tmp) / "registry.json"
            registry = register_model("qwen", {"model_name": "qwen-new"}, path=registry_path)
            rolled_back = rollback_model("qwen", path=registry_path)

        self.assertEqual(registry["active"]["qwen"]["model_name"], "qwen-new")
        self.assertNotEqual(rolled_back["active"]["qwen"]["model_name"], "qwen-new")


if __name__ == "__main__":
    unittest.main()
