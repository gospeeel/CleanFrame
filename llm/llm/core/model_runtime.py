from pathlib import Path

from llm.classification.rubert import get_model_manifest, load_model_and_tokenizer, validate_model_dir
from llm.core.model_registry import active_model_metadata, resolve_model_dir
from llm.paths import DEFAULT_MODEL_DIR


def model_status(model_dir: str | Path | None = None, warm: bool = False) -> dict:
    model_dir = Path(model_dir) if model_dir is not None else resolve_model_dir("rubert", DEFAULT_MODEL_DIR)

    try:
        validate_model_dir(model_dir)
        manifest = get_model_manifest(model_dir)
        if warm:
            load_model_and_tokenizer(model_dir)
    except Exception as exc:
        return {
            "ready": False,
            "model_dir": str(model_dir),
            "error": str(exc),
        }

    return {
        "ready": True,
        "model_dir": str(model_dir),
        "manifest": manifest,
        "registry": active_model_metadata("rubert"),
    }


def warm_model(model_dir: str | Path | None = None) -> None:
    model_dir = Path(model_dir) if model_dir is not None else resolve_model_dir("rubert", DEFAULT_MODEL_DIR)
    load_model_and_tokenizer(model_dir)
