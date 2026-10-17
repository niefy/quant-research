"""Structured validation results shared by CLI, API, and reports."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from quant.contracts.factor import ContractModel


class GateStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class GateResult(ContractModel):
    gate: str = Field(min_length=1)
    status: GateStatus
    metrics: dict[str, float | int | str | None] = Field(default_factory=dict)
    failures: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
