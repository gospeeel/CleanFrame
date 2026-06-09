from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm.paths import DEFAULT_MODEL_DIR, SERVICE_ROOT


DEFAULT_REGISTRY_PATH = Path(os.getenv("MODEL_REGISTRY_PATH", SERVICE_ROOT / "model_registry.json"))
DEFAULT_MODEL_AUDIT_PATH = Path(os.getenv("MODEL_REGISTRY_AUDIT_PATH", SERVICE_ROOT / "reports" / "model_registry_audit.jsonl"))


def default_registry(default_rubert_dir: Path = DEFAULT_MODEL_DIR) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "active": {
            "rubert": {
                "model_name": "ml-wink-rubert-multitask",
                "model_dir": str(default_rubert_dir),
                "created_at": None,
            },
        },
        "previous": {},
        "updated_at": None,
    }


def load_model_registry(path: Path = DEFAULT_REGISTRY_PATH) -> dict[str, Any]:
    if not path.exists():
        return default_registry()
    with path.open("r", encoding="utf-8") as f:
        registry = json.load(f)
    if not isinstance(registry, dict):
        raise ValueError(f"Model registry must be an object: {path}")
    registry.setdefault("active", {})
    registry.setdefault("previous", {})
    return registry


def save_model_registry(registry: dict[str, Any], path: Path = DEFAULT_REGISTRY_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    registry["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resolve_model_dir(role: str, fallback: str | Path) -> Path:
    if role == "rubert" and os.getenv("RUBERT_MODEL_DIR"):
        return Path(os.environ["RUBERT_MODEL_DIR"])

    registry = load_model_registry()
    model_dir = registry.get("active", {}).get(role, {}).get("model_dir")
    return Path(model_dir) if model_dir else Path(fallback)


def active_model_metadata(role: str) -> dict[str, Any]:
    registry = load_model_registry()
    active = registry.get("active", {}).get(role, {})
    return active if isinstance(active, dict) else {}


def register_model(role: str, metadata: dict[str, Any], path: Path = DEFAULT_REGISTRY_PATH) -> dict[str, Any]:
    registry = load_model_registry(path)
    active = registry.setdefault("active", {})
    previous = registry.setdefault("previous", {})
    previous_active = active.get(role)
    if role in active:
        previous[role] = active[role]
    metadata.setdefault("created_at", datetime.now(timezone.utc).isoformat())
    active[role] = metadata
    save_model_registry(registry, path)
    append_model_audit_event(
        action="model.switched",
        role=role,
        previous=previous_active,
        current=metadata,
    )
    return registry


def rollback_model(role: str, path: Path = DEFAULT_REGISTRY_PATH) -> dict[str, Any]:
    registry = load_model_registry(path)
    active = registry.setdefault("active", {})
    previous = registry.setdefault("previous", {})
    if role not in previous:
        raise ValueError(f"No previous model registered for role: {role}")
    previous_active = active.get(role)
    active[role], previous[role] = previous[role], active.get(role)
    save_model_registry(registry, path)
    append_model_audit_event(
        action="model.rolled_back",
        role=role,
        previous=previous_active,
        current=active.get(role),
    )
    return registry


def append_model_audit_event(
    action: str,
    role: str,
    previous: Any,
    current: Any,
    path: Path = DEFAULT_MODEL_AUDIT_PATH,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "role": role,
        "previous": previous if isinstance(previous, dict) else None,
        "current": current if isinstance(current, dict) else None,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
