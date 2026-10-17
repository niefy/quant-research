"""Load, dump, hash, and export versioned contracts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from quant.contracts.factor import FactorDocument
from quant.contracts.profile import ValidationProfileDocument


def _read_mapping(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    text = source.read_text(encoding="utf-8")
    if source.suffix.lower() in {".yaml", ".yml"}:
        loaded = yaml.safe_load(text)
    elif source.suffix.lower() == ".json":
        loaded = json.loads(text)
    else:
        raise ValueError(f"unsupported contract file type: {source.suffix}")
    if not isinstance(loaded, dict):
        raise ValueError(f"contract root must be a mapping: {source}")
    return loaded


def load_model[ModelT: BaseModel](path: str | Path, model_type: type[ModelT]) -> ModelT:
    return model_type.model_validate(_read_mapping(path))


def load_factor(path: str | Path) -> FactorDocument:
    return load_model(path, FactorDocument)


def load_profile(path: str | Path) -> ValidationProfileDocument:
    return load_model(path, ValidationProfileDocument)


def canonical_mapping(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json", by_alias=True, exclude_none=True)


def canonical_json(value: BaseModel | dict[str, Any]) -> str:
    mapping = canonical_mapping(value) if isinstance(value, BaseModel) else value
    return json.dumps(mapping, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def contract_hash(model: BaseModel) -> str:
    return sha256_text(canonical_json(model))


def write_json_schema(model_type: type[BaseModel], path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    schema = model_type.model_json_schema(by_alias=True)
    destination.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return destination
