import os
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SERVICE_ROOT
LLM_DIR = SERVICE_ROOT / "llm"
LEXICONS_DIR = LLM_DIR / "lexicons"
UPLOADS_DIR = SERVICE_ROOT / "uploads"
OUTPUTS_DIR = SERVICE_ROOT / "outputs"
DEFAULT_MODEL_DIR = Path(os.getenv("RUBERT_MODEL_DIR", SERVICE_ROOT / "trained_model"))


def resolve_project_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return PROJECT_ROOT / candidate
