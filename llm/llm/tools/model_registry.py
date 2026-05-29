from __future__ import annotations

import argparse
import json
from pathlib import Path

from llm.core.model_registry import (
    active_model_metadata,
    load_model_registry,
    register_model,
    rollback_model,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage ML_WINK model registry.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("show")

    active_parser = subparsers.add_parser("active")
    active_parser.add_argument("role", choices=["rubert", "qwen"])

    register_parser = subparsers.add_parser("register")
    register_parser.add_argument("role", choices=["rubert", "qwen"])
    register_parser.add_argument("--model-name", required=True)
    register_parser.add_argument("--model-dir", type=Path)
    register_parser.add_argument("--model-version")
    register_parser.add_argument("--weights-hash")
    register_parser.add_argument("--base-model")

    rollback_parser = subparsers.add_parser("rollback")
    rollback_parser.add_argument("role", choices=["rubert", "qwen"])

    args = parser.parse_args()
    if args.command == "show":
        payload = load_model_registry()
    elif args.command == "active":
        payload = active_model_metadata(args.role)
    elif args.command == "register":
        metadata = {
            "model_name": args.model_name,
            "model_version": args.model_version,
            "weights_hash": args.weights_hash,
            "base_model": args.base_model,
        }
        if args.model_dir is not None:
            metadata["model_dir"] = str(args.model_dir)
        payload = register_model(
            args.role,
            {key: value for key, value in metadata.items() if value is not None},
        )
    else:
        payload = rollback_model(args.role)

    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
