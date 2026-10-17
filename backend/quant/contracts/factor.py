"""FactorSpec v1 contracts.

The document is intentionally strict: unknown fields are rejected so that a
typo in a generated spec fails before any expensive computation starts.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        frozen=True,
        str_strip_whitespace=True,
    )


class FactorStatus(StrEnum):
    DRAFT = "draft"
    CANDIDATE = "candidate"
    VALIDATED = "validated"
    PROMOTED = "promoted"
    REJECTED = "rejected"
    QUARANTINED = "quarantined"


class FactorMetadata(ContractModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    version: int = Field(default=1, ge=1)
    status: FactorStatus = FactorStatus.DRAFT
    created_at: datetime
    created_by: str = Field(min_length=1)


class UniverseSpec(ContractModel):
    type: str = Field(min_length=1)
    n: int | None = Field(default=None, ge=1)
    as_of: Literal["rebalance", "decision"] = "rebalance"


class InputSpec(ContractModel):
    name: str = Field(min_length=1)
    source: str = Field(min_length=1)
    fields: list[str] = Field(min_length=1)
    availability_lag: str = "0s"


class ParamSpec(ContractModel):
    type: Literal["int", "float", "bool", "str"]
    default: Any
    grid: list[Any] | None = None


class WinsorizeSpec(ContractModel):
    method: Literal["quantile"] = "quantile"
    limits: tuple[float, float] = (0.01, 0.99)
    scope: Literal["cross_section", "time_series"] = "cross_section"

    @model_validator(mode="after")
    def _validate_limits(self) -> WinsorizeSpec:
        lower, upper = self.limits
        if not 0.0 <= lower < upper <= 1.0:
            raise ValueError("winsorize limits must satisfy 0 <= lower < upper <= 1")
        return self


class NeutralizeSpec(ContractModel):
    exposures: list[str] = Field(min_length=1)
    method: Literal["ols"] = "ols"


class StandardizeSpec(ContractModel):
    method: Literal["cross_section_zscore", "cross_section_rank"] = "cross_section_zscore"


class FillSpec(ContractModel):
    method: Literal["cross_section_median", "cross_section_mean", "zero"] = (
        "cross_section_median"
    )
    max_missing_ratio: float = Field(default=0.3, ge=0.0, le=1.0)


class PreprocessingSpec(ContractModel):
    order: list[Literal["winsorize", "neutralize", "standardize", "fill"]] = Field(
        default_factory=list
    )
    winsorize: WinsorizeSpec | None = None
    neutralize: NeutralizeSpec | None = None
    standardize: StandardizeSpec | None = None
    fill: FillSpec | None = None

    @model_validator(mode="after")
    def _validate_order(self) -> PreprocessingSpec:
        if len(set(self.order)) != len(self.order):
            raise ValueError("preprocessing order must not contain duplicates")
        allowed = {"winsorize", "neutralize", "standardize", "fill"}
        unknown = set(self.order) - allowed
        if unknown:
            raise ValueError(f"unknown preprocessing steps: {sorted(unknown)}")
        for step in self.order:
            if getattr(self, step) is None:
                raise ValueError(f"preprocessing step '{step}' is enabled but not configured")
        return self


class ProvenanceSpec(ContractModel):
    hypothesis_id: str = Field(min_length=1)
    source_ids: list[str] = Field(min_length=1)
    quotes: list[str] = Field(default_factory=list)
    generated_by: str = Field(min_length=1)
    review_status: Literal["pending", "approved", "rejected"] = "pending"


class FactorSpec(ContractModel):
    market: str = Field(min_length=1)
    scope: Literal["cross_sectional", "time_series"]
    frequency: str = Field(min_length=1)
    horizon: str = Field(min_length=1)
    universe: UniverseSpec
    inputs: list[InputSpec] = Field(min_length=1)
    params: dict[str, ParamSpec] = Field(default_factory=dict)
    expression: str = Field(min_length=1)
    preprocessing: PreprocessingSpec = Field(default_factory=PreprocessingSpec)
    direction: Literal["long_high", "long_low"] = "long_high"
    economic_rationale: str = Field(min_length=1)
    provenance: ProvenanceSpec

    @model_validator(mode="after")
    def _validate_input_names(self) -> FactorSpec:
        names = [item.name for item in self.inputs]
        if len(set(names)) != len(names):
            raise ValueError("input names must be unique")
        return self


class FactorDocument(ContractModel):
    api_version: Literal["quant/v1"] = Field(alias="apiVersion")
    kind: Literal["Factor"]
    metadata: FactorMetadata
    spec: FactorSpec
