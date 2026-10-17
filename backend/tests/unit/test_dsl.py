from __future__ import annotations

from datetime import datetime, timedelta

import polars as pl
import pytest

from quant.factors.dsl.compiler import CompileContext, compile_plan
from quant.factors.dsl.parser import parse_expression
from quant.factors.operators.registry import DSLParseError


def test_parse_resolves_params_and_canonicalizes() -> None:
    ast = parse_expression(
        'cs_rank(ts_return(close, window), method="average")',
        fields={"close"},
        params={"window": 20},
    )
    assert ast.canonical() == "cs_rank(ts_return(close, 20), method='average')"


def test_parse_allows_where_and_comparisons() -> None:
    ast = parse_expression(
        "where(close > 10, cs_rank(close), 0)",
        fields={"close"},
    )
    assert "where" in ast.canonical()


def test_unknown_field_is_rejected() -> None:
    with pytest.raises(DSLParseError, match="unknown field"):
        parse_expression("ts_mean(volume, 5)", fields={"close"})


def test_unknown_operator_is_rejected() -> None:
    with pytest.raises(DSLParseError, match="not whitelisted"):
        parse_expression("__import__('os')", fields={"close"})


def test_attribute_access_is_rejected() -> None:
    with pytest.raises(DSLParseError, match="direct calls"):
        parse_expression("close.rolling_mean(5)", fields={"close"})


def test_negative_shift_is_rejected() -> None:
    with pytest.raises(DSLParseError, match=">= 0"):
        parse_expression("ts_shift(close, -1)", fields={"close"})


def test_min_periods_larger_than_window_is_rejected() -> None:
    with pytest.raises(DSLParseError, match="min_periods"):
        parse_expression("ts_mean(close, 5, min_periods=10)", fields={"close"})


def test_compile_plan_materializes_mixed_grouping() -> None:
    start = datetime(2026, 1, 1)
    frame = pl.DataFrame(
        {
            "timestamp": [start + timedelta(hours=i) for i in range(10)] * 3,
            "symbol": ["A"] * 10 + ["B"] * 10 + ["C"] * 10,
            "close": (
                [100 + i for i in range(10)]
                + [50 + 2 * i for i in range(10)]
                + [200 - i for i in range(10)]
            ),
        }
    )
    ast = parse_expression("cs_rank(ts_return(close, 2))", fields={"close"})
    plan = compile_plan(
        ast,
        CompileContext(reserved_columns=frozenset(frame.columns)),
    )
    result = frame
    for step in plan.steps:
        result = result.with_columns(step)

    expected = frame.with_columns(
        (pl.col("close") / pl.col("close").shift(2) - 1.0).over("symbol").alias("r")
    ).with_columns(pl.col("r").rank().over("timestamp").alias("expected"))

    actual = result.select(["timestamp", "symbol", plan.output_column]).rename(
        {plan.output_column: "actual"}
    )
    joined = actual.join(
        expected.select(["timestamp", "symbol", "expected"]),
        on=["timestamp", "symbol"],
        how="left",
    )
    assert joined.filter(pl.col("expected").is_not_null()).select(
        (pl.col("actual") - pl.col("expected")).abs().max()
    ).item() < 1e-12
    assert joined["actual"].null_count() == 6


def test_compile_plan_ts_mean_matches_polars() -> None:
    start = datetime(2026, 1, 1)
    frame = pl.DataFrame(
        {
            "timestamp": [start + timedelta(hours=i) for i in range(20)],
            "symbol": ["A"] * 20,
            "close": [float(i) for i in range(20)],
        }
    )
    ast = parse_expression("ts_mean(close, 3, min_periods=2)", fields={"close"})
    plan = compile_plan(ast, CompileContext(reserved_columns=frozenset(frame.columns)))
    result = frame
    for step in plan.steps:
        result = result.with_columns(step)
    expected = frame.with_columns(
        pl.col("close").rolling_mean(3, min_samples=2).alias("expected")
    )
    actual = result[plan.output_column]
    expected_values = expected["expected"]
    assert actual.is_null().to_list() == expected_values.is_null().to_list()
    mask = expected_values.is_not_null()
    assert (actual.filter(mask) - expected_values.filter(mask)).abs().max() < 1e-12
