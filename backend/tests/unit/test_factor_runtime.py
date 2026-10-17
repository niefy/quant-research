from __future__ import annotations

from datetime import datetime
from pathlib import Path

import polars as pl
import pytest

from quant.data.panel import Panel
from quant.factors.runtime import compute_factor
from tests.helpers import make_factor_document, make_panel


def test_ts_return_values() -> None:
    panel = make_panel(
        {
            "A": [100.0, 110.0, 121.0, 133.1],
            "B": [50.0, 55.0, 60.5, 66.55],
        }
    )
    document = make_factor_document("ts_return(close, 2)")
    result = compute_factor(panel, document)
    start = datetime(2026, 1, 1)
    values = {
        (row["symbol"], row["timestamp"]): row["factor"]
        for row in result.frame.iter_rows(named=True)
    }
    assert values[("A", start)] is None
    assert values[("A", start.replace(hour=2))] == pytest.approx(0.21)
    assert values[("B", start.replace(hour=2))] == pytest.approx(0.21)


def test_nested_cross_sectional_and_time_series_ops() -> None:
    panel = make_panel(
        {
            "A": [100.0, 110.0, 121.0],
            "B": [50.0, 55.0, 66.0],
            "C": [10.0, 9.0, 8.0],
        }
    )
    document = make_factor_document("cs_rank(ts_return(close, 2))")
    result = compute_factor(panel, document)
    last_timestamp = result.frame["timestamp"].max()
    at_last = result.frame.filter(pl.col("timestamp") == last_timestamp).sort("symbol")
    assert at_last["factor"].to_list() == pytest.approx([2.0, 3.0, 1.0])


def test_direction_long_low_negates_signal() -> None:
    panel = make_panel({"A": [1.0, 2.0, 3.0], "B": [3.0, 2.0, 1.0]})
    long_high = compute_factor(panel, make_factor_document("close", direction="long_high"))
    long_low = compute_factor(panel, make_factor_document("close", direction="long_low"))
    assert long_low.frame["factor"].to_list() == pytest.approx(
        [-value for value in long_high.frame["factor"].to_list()]
    )


def test_factor_cache_is_content_addressed(tmp_path: Path) -> None:
    panel = make_panel({"A": [1.0, 2.0, 3.0], "B": [3.0, 2.0, 1.0]})
    document = make_factor_document("cs_rank(close)")
    first = compute_factor(panel, document, cache_dir=tmp_path)
    second = compute_factor(panel, document, cache_dir=tmp_path)
    assert first.cache_path is not None and first.cache_path.exists()
    assert len(list(tmp_path.glob("*.parquet"))) == 1
    assert first.frame.equals(second.frame)


def test_fill_preprocessing_uses_cross_section_median() -> None:
    timestamp = datetime(2026, 1, 1)
    frame = pl.DataFrame(
        {
            "timestamp": [timestamp, timestamp, timestamp],
            "symbol": ["A", "B", "C"],
            "close": [1.0, 2.0, None],
        }
    )
    panel = Panel.from_frame(frame)
    document = make_factor_document(
        "close",
        preprocessing={
            "order": ["fill"],
            "fill": {"method": "cross_section_median", "max_missing_ratio": 0.5},
        },
    )
    result = compute_factor(panel, document)
    values = {row["symbol"]: row["factor"] for row in result.frame.iter_rows(named=True)}
    assert values["C"] == pytest.approx(1.5)
