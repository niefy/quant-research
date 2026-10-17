"""Compile and execute a FactorSpec against a Panel."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl

from quant.contracts.factor import FactorDocument, FactorSpec, ParamSpec
from quant.contracts.io import canonical_json, contract_hash, sha256_text
from quant.data.panel import Panel
from quant.factors.dsl.ast import Expression
from quant.factors.dsl.compiler import CompileContext, compile_plan
from quant.factors.dsl.parser import parse_expression
from quant.factors.operators.registry import DSLParseError
from quant.factors.preprocess import apply_preprocessing


class FactorComputeError(ValueError):
    """Raised when a factor cannot be executed or its inputs are invalid."""


@dataclass(frozen=True)
class FactorResult:
    frame: pl.DataFrame
    cache_key: str
    spec_hash: str
    expression: str
    resolved_params: dict[str, Any]
    cache_path: Path | None = None


def resolve_params(
    specs: dict[str, ParamSpec],
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved = {name: spec.default for name, spec in specs.items()}
    for name, value in (overrides or {}).items():
        if name not in specs:
            raise FactorComputeError(f"unknown parameter override: {name}")
        spec = specs[name]
        resolved[name] = _coerce_param(name, spec, value)
    return resolved


def _coerce_param(name: str, spec: ParamSpec, value: Any) -> Any:
    if spec.type == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise FactorComputeError(f"parameter {name} must be int")
        return value
    if spec.type == "float":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise FactorComputeError(f"parameter {name} must be a number")
        return float(value)
    if spec.type == "bool":
        if not isinstance(value, bool):
            raise FactorComputeError(f"parameter {name} must be bool")
        return value
    if spec.type == "str":
        if not isinstance(value, str):
            raise FactorComputeError(f"parameter {name} must be str")
        return value
    raise FactorComputeError(f"unsupported parameter type for {name}: {spec.type}")


def parse_factor_expression(
    document: FactorDocument,
    resolved_params: dict[str, Any],
) -> Expression:
    fields = {field for item in document.spec.inputs for field in item.fields}
    try:
        return parse_expression(
            document.spec.expression,
            fields=fields,
            params=resolved_params,
        )
    except DSLParseError as exc:
        raise FactorComputeError(str(exc)) from exc


def compute_factor(
    panel: Panel,
    document: FactorDocument,
    *,
    params: dict[str, Any] | None = None,
    cache_dir: Path | None = None,
) -> FactorResult:
    spec = document.spec
    fields = {field for item in spec.inputs for field in item.fields}
    panel.require_fields(fields)

    resolved_params = resolve_params(spec.params, params)
    ast = parse_factor_expression(document, resolved_params)
    expression = ast.canonical()

    spec_hash = contract_hash(document)
    expression_hash = sha256_text(expression)
    preprocessing_hash = sha256_text(canonical_json(spec.preprocessing))
    cache_key = sha256_text(
        "|".join(
            [
                spec_hash,
                expression_hash,
                canonical_json(resolved_params),
                panel.fingerprint(),
                preprocessing_hash,
            ]
        )
    )

    cache_path = cache_dir / f"{cache_key}.parquet" if cache_dir is not None else None
    if cache_path is not None and cache_path.exists():
        cached = pl.read_parquet(cache_path)
        return FactorResult(
            frame=cached,
            cache_key=cache_key,
            spec_hash=spec_hash,
            expression=expression,
            resolved_params=resolved_params,
            cache_path=cache_path,
        )

    plan = compile_plan(
        ast,
        CompileContext(
            symbol_col="symbol",
            time_col="timestamp",
            reserved_columns=frozenset(panel.frame.columns),
        ),
    )
    frame = panel.frame
    for step in plan.steps:
        frame = frame.with_columns(step)

    compiled = pl.col(plan.output_column)
    compiled = apply_preprocessing(compiled, spec.preprocessing, time_col="timestamp")
    if spec.direction == "long_low":
        compiled = -compiled

    frame = frame.with_columns(compiled.alias("factor")).select(
        ["timestamp", "symbol", "factor"]
    )
    frame = frame.with_columns(
        pl.when(pl.col("factor").is_finite()).then(pl.col("factor")).otherwise(None).alias("factor")
    )
    frame = _apply_missing_ratio_limit(frame, spec)
    frame = frame.sort(["timestamp", "symbol"])

    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        frame.write_parquet(cache_path)

    return FactorResult(
        frame=frame,
        cache_key=cache_key,
        spec_hash=spec_hash,
        expression=expression,
        resolved_params=resolved_params,
        cache_path=cache_path,
    )


def _apply_missing_ratio_limit(frame: pl.DataFrame, spec: FactorSpec) -> pl.DataFrame:
    fill = spec.preprocessing.fill
    if fill is None or "fill" not in spec.preprocessing.order:
        return frame
    total = pl.len().over("timestamp")
    missing_ratio = pl.col("factor").is_null().sum().over("timestamp") / total
    return frame.with_columns(
        pl.when(missing_ratio <= fill.max_missing_ratio)
        .then(pl.col("factor"))
        .otherwise(None)
        .alias("factor")
    )
