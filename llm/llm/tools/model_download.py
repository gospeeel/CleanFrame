import argparse
import os
from pathlib import Path

from huggingface_hub import snapshot_download

from llm.classification.rubert import validate_model_dir


DEFAULT_REPO_ID = "gospeeel/ruBERT-cleanframe"
DEFAULT_REVISION = "main"
DEFAULT_OUTPUT_DIR = "/models/trained_model"


def download_rubert_model(repo_id: str, revision: str, output_dir: Path, token: str | None = None) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=repo_id,
        repo_type="model",
        revision=revision,
        local_dir=output_dir,
        local_dir_use_symlinks=False,
        token=token or None,
        allow_patterns=[
            "category_to_id.json",
            "config.json",
            "id_to_category.json",
            "level_class_weights.npy",
            "level_shift.npy",
            "model.safetensors",
            "model_manifest.json",
            "special_tokens_map.json",
            "tokenizer.json",
            "tokenizer_config.json",
            "vocab.txt",
        ],
    )
    return validate_model_dir(output_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download the CleanFrame RuBERT model from Hugging Face.")
    parser.add_argument("--repo-id", default=os.getenv("HF_RUBERT_REPO_ID", DEFAULT_REPO_ID))
    parser.add_argument("--revision", default=os.getenv("HF_RUBERT_REVISION", DEFAULT_REVISION))
    parser.add_argument("--output-dir", type=Path, default=Path(os.getenv("RUBERT_MODEL_DIR", DEFAULT_OUTPUT_DIR)))
    parser.add_argument("--token", default=os.getenv("HF_TOKEN", ""))
    args = parser.parse_args()

    model_dir = download_rubert_model(
        repo_id=args.repo_id,
        revision=args.revision,
        output_dir=args.output_dir,
        token=args.token.strip() or None,
    )
    print(f"RuBERT model is ready at {model_dir}")


if __name__ == "__main__":
    main()
