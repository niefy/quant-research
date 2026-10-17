from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import polars as pl
import pytest

from quant.validation.metrics import (
    newey_west_t,
    rank_ic_series,
    subperiod_positive_ratio,
    summarize_ic,
)


def test_rank_ic_is_one_for_perfect_rank_relation() -> None:
    timestamp = datetime(2026, 1, 1)
    factor = pl.DataFrame(
        {
            "timestamp": [timestamp] * 5,
            "symbol": list("ABCDE"),
            "factor": [1.0, 2.0, 3.0, 4.0, 5.0],
        }
    )
    labels = pl.DataFrame(
        {
            "timestamp": [timestamp] * 5,
            "symbol": list("ABCDE"),
            "forward_return": [0.1, 0.2, 0.3, 0.4, 0.5],
        }
    )
    series = rank_ic_series(factor, labels, min_symbols=5)
    assert series.height == 1
    assert series["ic"][0] == pytest.approx(1.0)


def test_rank_ic_skips_sparse_timestamps() -> None:
    timestamp = datetime(2026, 1, 1)
    factor = pl.DataFrame(
        {
            "timestamp": [timestamp] * 4,
            "symbol": list("ABCD"),
            "factor": [1.0, 2.0, 3.0, 4.0],
        }
    )
    labels = pl.DataFrame(
        {
            "timestamp": [timestamp] * 4,
            "symbol": list("ABCD"),
            "forward_return": [0.1, 0.2, 0.3, 0.4],
        }
    )
    series = rank_ic_series(factor, labels, min_symbols=5)
    assert series.is_empty()


def test_newey_west_t_detects_positive_mean() -> None:
    rng = np.random.default_rng(42)
    values = 0.05 + rng.normal(0.0, 0.1, 500)
    t_stat = newey_west_t(values)
    assert np.isfinite(t_stat)
    assert t_stat > 5.0


def test_subperiod_positive_ratio() -> None:
    assert subperiod_positive_ratio(np.ones(100) * 0.1) == 1.0
    mixed = np.concatenate([np.ones(50) * 0.1, -np.ones(50) * 0.1])
    assert subperiod_positive_ratio(mixed, n_subperiods=4) == pytest.approx(0.5)


def test_summarize_ic_empty() -> None:
    empty = pl.DataFrame(
        schema={"timestamp": pl.Datetime("us"), "ic": pl.Float64, "n_symbols": pl.UInt32}
    )
    summary = summarize_ic(empty)
    assert summary.n_periods == 0
    assert np.isnan(summary.rank_ic_mean)


def test_summarize_ic_known_series() -> None:
    start = datetime(2026, 1, 1)
    series = pl.DataFrame(
        {
            "timestamp": [start + timedelta(days=i) for i in range(100)],
            "ic": [0.05] * 100,
            "n_symbols": [20] * 100,
        }
    )
    summary = summarize_ic(series)
    assert summary.rank_ic_mean == pytest.approx(0.05)
    assert summary.ic_win_rate == pytest.approx(1.0)
    assert summary.subperiod_positive_ratio == pytest.approx(1.0)
