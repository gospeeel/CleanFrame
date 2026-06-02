from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Iterable

from docx import Document
import pdfplumber


logger = logging.getLogger(__name__)

DEFAULT_MAX_ELEMENT_CHARS = 1400
MAX_ELEMENT_CHARS = int(os.getenv("SCRIPT_PARSER_MAX_ELEMENT_CHARS", str(DEFAULT_MAX_ELEMENT_CHARS)))
MAX_HEADER_CHARS = 180


def _mojibake(value: str) -> str:
    """Return the common UTF-8-as-CP1251 mojibake variant used by older fixtures."""
    try:
        return value.encode("utf-8").decode("cp1251")
    except UnicodeError:
        return value


def _repair_mojibake(value: str) -> str:
    """Repair the common CP1251 rendering of UTF-8 Russian text when possible."""
    try:
        return value.encode("cp1251").decode("utf-8")
    except UnicodeError:
        return value


def _text_quality_penalty(value: str) -> int:
    replacements = value.count("\ufffd")
    mojibake_markers = sum(value.count(marker) for marker in ("Р", "С", "в„", "Рџ", "Рђ", "СЊ"))
    cyrillic = len(re.findall(r"[А-Яа-яЁё]", value))
    latin = len(re.findall(r"[A-Za-z]", value))
    return replacements * 1000 + mojibake_markers * 10 - cyrillic - latin // 4


def _variants(*values: str) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        for candidate in (value, _mojibake(value)):
            if candidate and candidate not in result:
                result.append(candidate)
    return tuple(result)


def _regex_alt(values: Iterable[str]) -> str:
    return "|".join(re.escape(value) for value in sorted(set(values), key=len, reverse=True))


SCENE_MARKERS = _variants(
    "\u0418\u041d\u0422",  # INT in Russian
    "\u041d\u0410\u0422",  # NAT/exterior legacy marker
    "\u042d\u041a\u0421\u0422",  # EXT in Russian
    "\u0418\u041d\u0422\u0415\u0420\u042c\u0415\u0420",
    "\u042d\u041a\u0421\u0422\u0415\u0420\u042c\u0415\u0420",
) + ("INT", "EXT", "INTERIOR", "EXTERIOR")

TIME_MARKERS = _variants(
    "\u0414\u0415\u041d\u042c",
    "\u041d\u041e\u0427\u042c",
    "\u0423\u0422\u0420\u041e",
    "\u0412\u0415\u0427\u0415\u0420",
    "\u0417\u0410\u041a\u0410\u0422",
    "\u0420\u0410\u0421\u0421\u0412\u0415\u0422",
    "\u041f\u041e\u0417\u0416\u0415",
    "\u0421\u0423\u041c\u0415\u0420\u041a\u0418",
    "\u041f\u041e\u041b\u0414\u0415\u041d\u042c",
    "\u041f\u0420\u041e\u0414\u041e\u041b\u0416\u0415\u041d\u0418\u0415",
    "\u0421\u0415\u041a\u0423\u041d\u0414\u042b \u0421\u041f\u0423\u0421\u0422\u042f",
    "\u041c\u0418\u041d\u0423\u0422\u042b \u0421\u041f\u0423\u0421\u0422\u042f",
    "\u0421\u0415\u041a\u0423\u041d\u0414\u041e\u0419 \u041f\u041e\u0417\u0416\u0415",
    "\u0412 \u0422\u041e \u0416\u0415 \u0412\u0420\u0415\u041c\u042f",
    "\u0427\u0415\u0420\u0415\u0417 \u041f\u0410\u0420\u0423 \u041c\u0418\u041d\u0423\u0422",
    "\u0427\u0415\u0420\u0415\u0417 \u041d\u0415\u0421\u041a\u041e\u041b\u042c\u041a\u041e \u041c\u0418\u041d\u0423\u0422",
    "\u041c\u0413\u041d\u041e\u0412\u0415\u041d\u0418\u0415 \u0421\u041f\u0423\u0421\u0422\u042f",
    "\u041c\u0415\u0421\u042f\u0426\u042b \u0421\u041f\u0423\u0421\u0422\u042f",
    "\u0413\u041e\u0414\u042b \u0421\u041f\u0423\u0421\u0422\u042f",
) + (
    "DAY",
    "NIGHT",
    "MORNING",
    "EVENING",
    "LATER",
    "CONTINUOUS",
    "SAME TIME",
)

ACTION_CUE_WORDS = _variants(
    "\u0421\u041c\u0415\u0425",
    "\u041f\u0410\u0423\u0417\u0410",
    "\u041c\u041e\u041b\u0427\u0410\u041d\u0418\u0415",
    "\u0417\u0412\u0423\u041a",
    "\u0422\u0418\u0422\u0420",
    "\u0421\u041a\u041b\u0415\u0419\u041a\u0410",
    "\u041f\u0415\u0420\u0415\u0425\u041e\u0414",
    "\u0413\u0420\u0410\u0424\u0418\u041a\u0410",
    "\u041e\u0411\u0429\u0418\u0419",
    "\u041a\u0420\u0423\u041f\u041d\u041e",
    "\u041a\u0410\u041c\u0415\u0420\u0410",
    "\u041a\u041e\u041d\u0415\u0426",
)

ACTION_VERBS = _variants(
    "\u0432\u044b\u0445\u043e\u0434\u0438\u0442",
    "\u0432\u0445\u043e\u0434\u0438\u0442",
    "\u0438\u0434\u0435\u0442",
    "\u0438\u0434\u0451\u0442",
    "\u0441\u043b\u044b\u0448\u0438\u0442",
    "\u0432\u0438\u0434\u0438\u0442",
    "\u0431\u0435\u0440\u0435\u0442",
    "\u0431\u0435\u0440\u0451\u0442",
    "\u0445\u0432\u0430\u0442\u0430\u0435\u0442",
    "\u043f\u0430\u0434\u0430\u0435\u0442",
    "\u0443\u0434\u0430\u0440\u044f\u0435\u0442",
    "\u0431\u044c\u0435\u0442",
    "\u0431\u044c\u0451\u0442",
    "\u043e\u0442\u043a\u0440\u044b\u0432\u0430\u0435\u0442",
    "\u0437\u0430\u043a\u0440\u044b\u0432\u0430\u0435\u0442",
    "\u0441\u043c\u043e\u0442\u0440\u0438\u0442",
    "\u043c\u043e\u043b\u0447\u0438\u0442",
    "\u043a\u0440\u0438\u0447\u0438\u0442",
    "\u043a\u0430\u043c\u0435\u0440\u0430",
    "\u0441\u0432\u0435\u0442",
    "\u0434\u0432\u0435\u0440\u044c",
)

SCENE_MARKER_ALT = _regex_alt(SCENE_MARKERS)
TIME_MARKER_ALT = _regex_alt(TIME_MARKERS)

DASH_VARIANTS = _variants("\u2013", "\u2014", "\u2212") + ("--",)
NBSP_VARIANTS = ("\u00a0", "\u202f")

SCENE_HEADER_RE = re.compile(
    rf"^(?:\d{{1,4}}(?:[-/]\d{{1,4}})?[.)]?\s*)?"
    rf"(?:{SCENE_MARKER_ALT})(?:[./])?(?:\s|$|[-:])",
    re.IGNORECASE,
)
NUMBERED_HEADER_RE = re.compile(r"^\d{1,4}(?:[-/]\d{1,4})?\.\s+\S")
NUMBERED_HEADER_SPLIT_RE = re.compile(r"^(\d{1,4}(?:[-/]\d{1,4})?\.)\s*(.*)$")
SCENE_BREAK_RE = re.compile(
    rf"\s+(?=(?:\d{{1,4}}(?:[-/]\d{{1,4}})?[.)]\s*)?"
    rf"(?:{SCENE_MARKER_ALT})(?:[./])?(?:\s|[-:]))",
    re.IGNORECASE,
)
NUMBERED_BREAK_RE = re.compile(
    rf"\s+(?=\d{{1,4}}(?:[-/]\d{{1,4}})?\.\s+(?:{SCENE_MARKER_ALT}|\S))",
    re.IGNORECASE,
)
TIME_MARKER_RE = re.compile(rf"\b(?:{TIME_MARKER_ALT})\b", re.IGNORECASE)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?\u2026])\s+")


def normalize_spacing(text: str) -> str:
    text = text.replace("\ufeff", " ")
    for nbsp in NBSP_VARIANTS:
        text = text.replace(nbsp, " ")
    for dash in DASH_VARIANTS:
        text = text.replace(dash, " - ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"\n\s+", "\n", text)
    return text.strip()


def expand_compacted_line(line: str) -> list[str]:
    text = normalize_spacing(line)
    if not text:
        return []

    text = SCENE_BREAK_RE.sub("\n", text)
    text = NUMBERED_BREAK_RE.sub("\n", text)
    return [part.strip(" -") for part in text.splitlines() if part.strip(" -")]


def normalize_script_lines(lines_with_page: list) -> list[tuple[str, int | None]]:
    if lines_with_page and isinstance(lines_with_page[0], str):
        rows = [(line, None) for line in lines_with_page]
    else:
        rows = [(line, page) for line, page in lines_with_page]

    normalized: list[tuple[str, int | None]] = []
    for raw_line, page in rows:
        for line in expand_compacted_line(str(raw_line)):
            normalized.append((line, page))

    return ensure_scene_header(normalized)


def is_scene_header(line: str) -> bool:
    stripped = normalize_spacing(line)
    if not stripped:
        return False
    return bool(SCENE_HEADER_RE.match(stripped) or NUMBERED_HEADER_RE.match(stripped))


def split_scene_header(line: str) -> tuple[str, str] | None:
    stripped = normalize_spacing(line)
    if not is_scene_header(stripped):
        return None

    marker_match = SCENE_HEADER_RE.match(stripped)
    if not marker_match:
        numbered_match = NUMBERED_HEADER_SPLIT_RE.match(stripped)
        if numbered_match:
            return numbered_match.group(1).strip(), numbered_match.group(2).strip()
        return stripped, ""

    time_match = None
    for candidate in TIME_MARKER_RE.finditer(stripped):
        if candidate.end() <= MAX_HEADER_CHARS:
            time_match = candidate
            break

    if time_match and time_match.end() < len(stripped):
        return stripped[: time_match.end()].strip(), stripped[time_match.end() :].strip(" -:")

    if len(stripped) <= MAX_HEADER_CHARS:
        return stripped, ""

    boundary = _find_header_boundary(stripped, marker_match.end())
    if boundary:
        return stripped[:boundary].strip(), stripped[boundary:].strip(" -:")

    return stripped[:MAX_HEADER_CHARS].strip(" -:"), stripped[MAX_HEADER_CHARS:].strip(" -:")


def _find_header_boundary(text: str, start: int) -> int | None:
    lower_bound = max(start + 24, 40)
    upper_bound = min(len(text), MAX_HEADER_CHARS)
    for pattern in (r":\s+", r"\s+-\s+", r"\.\s+"):
        for match in re.finditer(pattern, text):
            if lower_bound <= match.end() <= upper_bound:
                return match.end()
    return None


def _word_count(text: str) -> int:
    return len([word for word in text.split() if word.strip()])


def is_character_line(line: str) -> bool:
    stripped = normalize_spacing(line).strip(" -")
    if not stripped or len(stripped) > 64 or is_scene_header(stripped):
        return False

    if _word_count(stripped) > 6:
        return False

    if re.search(r"[.!?:;]", stripped):
        return False

    if not re.match(r"^[^\W\d_]", stripped, flags=re.UNICODE):
        return False

    upper = stripped.upper()
    if any(cue in upper for cue in ACTION_CUE_WORDS):
        return False

    letters = [char for char in stripped if char.isalpha()]
    if not letters:
        return False

    uppercase_letters = [char for char in letters if char.upper() == char]
    return len(uppercase_letters) / max(len(letters), 1) >= 0.65


def looks_like_action_after_dialogue(line: str) -> bool:
    stripped = normalize_spacing(line)
    if not stripped:
        return False

    lowered = stripped.lower()
    if any(marker in lowered for marker in ACTION_VERBS):
        return True

    if len(stripped) > 90 and not stripped.endswith(("?", "!")):
        return True

    return False


def extract_text_from_docx(path: str) -> list[str]:
    doc = Document(path)
    return [para.text for para in doc.paragraphs if para.text.strip()]


def extract_text_from_pdf(path: str) -> list[tuple[str, int]]:
    lines_with_page: list[tuple[str, int]] = []
    with pdfplumber.open(path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(x_tolerance=1, y_tolerance=1)
            if text:
                for line in text.splitlines():
                    if line.strip():
                        lines_with_page.append((line, page_num))
    return lines_with_page


def extract_text_from_txt(path: str) -> list[str]:
    raw = Path(path).read_bytes()
    candidates: list[tuple[int, str]] = []
    last_error: Exception | None = None

    for encoding in ("utf-8-sig", "utf-8", "cp1251", "windows-1251"):
        try:
            text = raw.decode(encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
            continue

        repaired = _repair_mojibake(text)
        for candidate in (text, repaired):
            candidates.append((_text_quality_penalty(candidate), candidate))

    if not candidates:
        raise ValueError(f"Unable to read .txt file: {last_error}")

    text = min(candidates, key=lambda item: item[0])[1]
    return [line for line in text.splitlines() if line.strip()]


def ensure_scene_header(lines: list[tuple[str, int | None]]) -> list[tuple[str, int | None]]:
    if not lines:
        return lines

    if any(is_scene_header(line) for line, _page in lines):
        return lines

    first_page = lines[0][1]
    return [("1. TEXT SCRIPT", first_page), *lines]


def split_text_chunks(text: str, max_chars: int = MAX_ELEMENT_CHARS) -> list[str]:
    text = normalize_spacing(text)
    if not text:
        return []

    chunks: list[str] = []
    current = ""
    for sentence in _split_sentences(text):
        if not sentence:
            continue
        if len(sentence) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(_split_long_sentence(sentence, max_chars))
            continue
        if current and len(current) + 1 + len(sentence) > max_chars:
            chunks.append(current.strip())
            current = sentence
        else:
            current = f"{current} {sentence}".strip()

    if current:
        chunks.append(current.strip())
    return chunks


def _split_sentences(text: str) -> list[str]:
    parts = SENTENCE_SPLIT_RE.split(text)
    if len(parts) > 1:
        return [part.strip() for part in parts if part.strip()]
    return [text]


def _split_long_sentence(text: str, max_chars: int) -> list[str]:
    words = text.split()
    chunks: list[str] = []
    current = ""
    for word in words:
        if len(word) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(word[i : i + max_chars] for i in range(0, len(word), max_chars))
            continue
        if current and len(current) + 1 + len(word) > max_chars:
            chunks.append(current.strip())
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        chunks.append(current.strip())
    return chunks


def append_element(scene: dict, element_type: str, text: str, character: str | None = None) -> None:
    for chunk in split_text_chunks(text):
        element = {"type": element_type, "text": chunk}
        if character:
            element["character"] = character
        scene["elements"].append(element)


def compact_scenes(scenes: list[dict]) -> list[dict]:
    compacted: list[dict] = []
    for scene in scenes:
        if not scene.get("elements"):
            continue
        scene["scene_id"] = len(compacted) + 1
        compacted.append(scene)
    return compacted


def parse_script_lines(lines_with_page: list) -> dict:
    scenes: list[dict] = []
    current_scene: dict | None = None
    last_character: str | None = None
    current_action_lines: list[str] = []
    current_dialogue_lines: list[str] = []

    rows = normalize_script_lines(lines_with_page)
    logger.debug("script_parser.normalized_lines", extra={"line_count": len(rows)})

    def flush_action() -> None:
        nonlocal current_action_lines
        if current_scene is not None and current_action_lines:
            append_element(current_scene, "action", " ".join(current_action_lines))
        current_action_lines = []

    def flush_dialogue() -> None:
        nonlocal current_dialogue_lines, last_character
        if current_scene is not None and current_dialogue_lines and last_character:
            append_element(current_scene, "dialogue", " ".join(current_dialogue_lines), character=last_character)
        current_dialogue_lines = []
        last_character = None

    def process_content_line(line: str) -> None:
        nonlocal last_character
        if current_scene is None:
            return

        if is_character_line(line):
            flush_action()
            flush_dialogue()
            last_character = line
            return

        if last_character is not None:
            if current_dialogue_lines and looks_like_action_after_dialogue(line):
                flush_dialogue()
                current_action_lines.append(line)
            else:
                current_dialogue_lines.append(line)
            return

        current_action_lines.append(line)

    for raw_line, page in rows:
        line = normalize_spacing(raw_line)
        if not line:
            continue

        header_parts = split_scene_header(line)
        if header_parts is not None:
            flush_action()
            flush_dialogue()
            if current_scene is not None:
                scenes.append(current_scene)

            header, remainder = header_parts
            current_scene = {
                "scene_id": len(scenes) + 1,
                "header": header,
                "page": page,
                "elements": [],
            }
            last_character = None

            if remainder:
                for content_line in expand_compacted_line(remainder):
                    process_content_line(content_line)
            continue

        process_content_line(line)

    if current_scene is not None:
        flush_action()
        flush_dialogue()
        scenes.append(current_scene)

    scenes = compact_scenes(scenes)
    logger.debug("script_parser.parsed", extra={"scene_count": len(scenes)})
    return {"scenes": scenes}


def parse_script(file_path: str) -> dict:
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    suffix = file_path.suffix.lower()
    if suffix == ".docx":
        return parse_script_lines(extract_text_from_docx(str(file_path)))
    if suffix == ".pdf":
        return parse_script_lines(extract_text_from_pdf(str(file_path)))
    if suffix == ".txt":
        return parse_script_lines(extract_text_from_txt(str(file_path)))

    raise ValueError("Only .docx, .pdf and .txt files are supported")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = input("Path to screenplay file (.docx, .pdf or .txt): ").strip('"').strip("'")

    if not input_file or not os.path.exists(input_file):
        print("File was not found or path is empty")
        sys.exit(1)

    try:
        result = parse_script(input_file)
        output_file = Path(input_file).with_suffix(".json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"Parsed {len(result['scenes'])} scenes -> {output_file}")
    except Exception as exc:
        print(f"Error: {exc}")
        sys.exit(1)
