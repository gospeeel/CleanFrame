import unittest
import tempfile
from pathlib import Path

from llm.parsing.script_parser import (
    _mojibake,
    extract_text_from_txt,
    parse_script_lines,
    split_text_chunks,
)


class ScriptParserTests(unittest.TestCase):
    def test_compacted_text_is_split_into_scenes_and_elements(self):
        text = (
            "1. INT. HUMVEE - DAY Tony holds a glass. "
            "EXT. DESERT - DAY A blast throws dust over the road. "
            "3. INT. CAVE - NIGHT Tony wakes up."
        )

        result = parse_script_lines([text])

        self.assertGreaterEqual(len(result["scenes"]), 3)
        self.assertTrue(all(scene["elements"] for scene in result["scenes"]))
        self.assertIn("HUMVEE", result["scenes"][0]["header"])
        self.assertIn("DESERT", result["scenes"][1]["header"])

    def test_mojibake_scene_markers_are_supported(self):
        text = _mojibake(
            "1. \u042d\u041a\u0421\u0422. \u0414\u0412\u041e\u0420 - \u0414\u0415\u041d\u042c "
            "\u0413\u0435\u0440\u043e\u0439 \u0431\u0435\u0436\u0438\u0442. "
            "\u0418\u041d\u0422. \u0414\u041e\u041c - \u041d\u041e\u0427\u042c "
            "\u0413\u0435\u0440\u043e\u0439 \u043f\u0440\u044f\u0447\u0435\u0442\u0441\u044f."
        )

        result = parse_script_lines([text])

        self.assertEqual(len(result["scenes"]), 2)
        self.assertTrue(all(scene["elements"] for scene in result["scenes"]))

    def test_long_action_is_chunked(self):
        long_action = " ".join(["Sentence with action."] * 180)

        result = parse_script_lines([f"1. INT. ROOM - DAY {long_action}"])

        elements = result["scenes"][0]["elements"]
        self.assertGreater(len(elements), 1)
        self.assertTrue(all(len(element["text"]) <= 1400 for element in elements))

    def test_split_text_chunks_handles_single_long_token(self):
        chunks = split_text_chunks("x" * 3000, max_chars=1000)

        self.assertEqual([len(chunk) for chunk in chunks], [1000, 1000, 1000])

    def test_parenthesized_aircraft_number_is_not_a_scene(self):
        text = "INT. F-22 (VIPER 1) FLIGHT - DAY Pilot keeps formation."

        result = parse_script_lines([text])

        self.assertEqual(len(result["scenes"]), 1)
        self.assertIn("VIPER 1", result["scenes"][0]["header"])
        self.assertEqual(len(result["scenes"][0]["elements"]), 1)

    def test_empty_scene_headers_are_dropped(self):
        text = "EXT. EMPTY PLACE - DAY INT. ROOM - DAY Someone enters."

        result = parse_script_lines([text])

        self.assertEqual(len(result["scenes"]), 1)
        self.assertEqual(result["scenes"][0]["scene_id"], 1)
        self.assertIn("ROOM", result["scenes"][0]["header"])

    def test_txt_extraction_repairs_common_mojibake(self):
        text = _mojibake("ИНТ. КОМНАТА - ДЕНЬ\nГерой входит.")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "script.txt"
            path.write_text(text, encoding="utf-8")

            lines = extract_text_from_txt(str(path))

        self.assertEqual(lines[0], "ИНТ. КОМНАТА - ДЕНЬ")
        self.assertEqual(lines[1], "Герой входит.")


if __name__ == "__main__":
    unittest.main()
