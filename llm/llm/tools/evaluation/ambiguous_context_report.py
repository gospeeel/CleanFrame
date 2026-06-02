from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from llm.detection.rule_detector import is_suspicious_scene


DEFAULT_INPUT_DIR = Path("/workspace/doc/Real_Text")
DEFAULT_REPORT_PATH = Path(__file__).resolve().parents[3] / "reports" / "ambiguous_context_report.json"


def build_report(input_dir: Path, max_samples: int = 5, max_chars: int = 260) -> dict[str, Any]:
    term_counts: Counter[tuple[str, str]] = Counter()
    samples: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    files = []

    for path in sorted(input_dir.glob("*.txt")):
        files.append(path.name)
        for chunk in chunks(read_text(path), max_chars=max_chars):
            result = is_suspicious_scene(chunk)
            for category, terms in result.get("matched_terms", {}).items():
                for term in terms:
                    key = (category, term)
                    term_counts[key] += 1
                    if len(samples[key]) < max_samples:
                        samples[key].append({"file": path.name, "text": chunk})

    return {
        "input_dir": str(input_dir),
        "files": files,
        "top_terms": [
            {
                "category": category,
                "term": term,
                "count": count,
                "samples": samples[(category, term)],
            }
            for (category, term), count in term_counts.most_common()
        ],
    }


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="cp1251", errors="ignore")


def chunks(text: str, max_chars: int) -> list[str]:
    result = []
    for chunk in re.split(r"(?<=[.!?\u2026])\s+", text):
        normalized = " ".join(chunk.split())
        if normalized and len(normalized) <= max_chars:
            result.append(normalized)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a Real_Text suspicious-term report.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--max-samples", type=int, default=5)
    parser.add_argument("--max-chars", type=int, default=260)
    args = parser.parse_args()

    report = build_report(args.input_dir, args.max_samples, args.max_chars)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} with {len(report['top_terms'])} terms")


if __name__ == "__main__":
    main()
