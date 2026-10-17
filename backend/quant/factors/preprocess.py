"""Apply the fixed, explicit preprocessing pipeline to a factor expression."""

from __future__ import annotations

import polars as pl

from quant.contracts.factor import PreprocessingSpec
from quant.factors.operators.registry import UnsupportedOperatorError


def apply_preprocessing(
    expr: pl.Expr,
    spec: PreprocessingSpec,
    *,
    time_col: str = "timestamp",
) -> pl.Expr:
    result = expr
    for step in spec.order:
        if step == "winsorize":
            if spec.winsorize is None:
                raise ValueError("winsorize step is enabled without configuration")
            lower, upper = spec.winsorize.limits
            lower_expr = result.quantile(lower).over(time_col)
            upper_expr = result.quantile(upper).over(time_col)
            result = pl.min_horizontal(pl.max_horizontal(result, lower_expr), upper_expr)

        elif step == "standardize":
            if spec.standardize is None:
                raise ValueError("standardize step is enabled without configuration")
            if spec.standardize.method == "cross_section_zscore":
                mean = result.mean().over(time_col)
                std = result.std().over(time_col)
                result = (result - mean) / std
            elif spec.standardize.method == "cross_section_rank":
                result = result.rank(method="average").over(time_col)
            else:
                raise ValueError(f"unsupported standardize method: {spec.standardize.method}")

        elif step == "fill":
            if spec.fill is None:
                raise ValueError("fill step is enabled without configuration")
            if spec.fill.method == "cross_section_median":
                result = result.fill_null(result.median().over(time_col))
            elif spec.fill.method == "cross_section_mean":
                result = result.fill_null(result.mean().over(time_col))
            elif spec.fill.method == "zero":
                result = result.fill_null(0.0)
            else:
                raise ValueError(f"unsupported fill method: {spec.fill.method}")

        elif step == "neutralize":
            raise UnsupportedOperatorError(
                "cross-sectional neutralization is not implemented in this slice; "
                "remove it from preprocessing.order or supply pre-neutralized exposures"
            )

        else:
            raise ValueError(f"unknown preprocessing step: {step}")

    return result
