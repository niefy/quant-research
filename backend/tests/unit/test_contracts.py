from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from quant.contracts.factor import FactorDocument
from quant.contracts.io import (
    canonical_json,
    contract_hash,
    load_factor,
    load_profile,
    write_json_schema,
)
from quant.contracts.profile import ValidationProfileDocument
from tests.helpers import EXAMPLES


def test_load_example_factor_contract() -> None:
    document = load_factor(EXAMPLES / "factor_momentum.yaml")
    assert document.api_version == "quant/v1"
    assert document.kind == "Factor"
    assert document.spec.scope == "cross_sectional"
    assert document.spec.frequency == "30m"
    assert document.spec.params["window"].default == 20
    assert document.spec.preprocessing.order == ["winsorize", "standardize", "fill"]


def test_load_example_profile_contract() -> None:
    profile = load_profile(EXAMPLES / "profile_crypto_perp_30m_v1.yaml")
    assert profile.metadata.id == "crypto_perp_30m_v1"
    assert profile.metadata.scope == "cross_sectional"
    assert profile.thresholds.g1_ic.min_periods == 2000


def test_contract_hash_is_stable() -> None:
    document = load_factor(EXAMPLES / "factor_momentum.yaml")
    first = contract_hash(document)
    second = contract_hash(load_factor(EXAMPLES / "factor_momentum.yaml"))
    assert first == second
    assert len(first) == 64


def test_unknown_field_is_rejected() -> None:
    document = load_factor(EXAMPLES / "factor_momentum.yaml")
    payload = json.loads(canonical_json(document))
    payload["spec"]["typo_field"] = 1
    with pytest.raises(ValidationError):
        FactorDocument.model_validate(payload)


def test_preprocessing_step_requires_configuration() -> None:
    payload = yaml.safe_load((EXAMPLES / "factor_momentum.yaml").read_text(encoding="utf-8"))
    payload["spec"]["preprocessing"] = {"order": ["winsorize"]}
    with pytest.raises(ValidationError):
        FactorDocument.model_validate(payload)


def test_json_schema_export(tmp_path: Path) -> None:
    factor_path = write_json_schema(FactorDocument, tmp_path / "factor.json")
    profile_path = write_json_schema(ValidationProfileDocument, tmp_path / "profile.json")
    factor_schema = json.loads(factor_path.read_text(encoding="utf-8"))
    profile_schema = json.loads(profile_path.read_text(encoding="utf-8"))
    assert factor_schema["title"] == "FactorDocument"
    assert profile_schema["title"] == "ValidationProfileDocument"
    assert "apiVersion" in factor_schema["properties"]
