from __future__ import annotations

from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

from quant.data.panel import Panel, PanelError
from tests.helpers import make_panel


def test_panel_normalizes_epoch_seconds_and_reserved_columns() -> None:
    start = int(datetime(2026, 1, 1, tzinfo=UTC).timestamp())
    frame = pl.DataFrame(
        {
            "datetime": [start, start + 3600, start, start + 3600],
            "symbol": ["A", "A", "B", "B"],
            "close": [1.0, 2.0, 3.0, 4.0],
        }
    )
    panel = Panel.from_frame(frame)
    assert panel.frame["timestamp"].dtype == pl.Datetime("us")
    assert panel.frame["timestamp"][0] == datetime(2026, 1, 1)
    assert panel.field_names == ("close",)
    assert "available_at" in panel.frame.columns
    assert panel.frame["available_at"][0] == panel.frame["timestamp"][0]


def test_panel_rejects_duplicates() -> None:
    timestamp = datetime(2026, 1, 1)
    frame = pl.DataFrame(
        {
            "timestamp": [timestamp, timestamp],
            "symbol": ["A", "A"],
            "close": [1.0, 2.0],
        }
    )
    with pytest.raises(PanelError, match="duplicate"):
        Panel.from_frame(frame)


def test_forward_return_uses_execution_lag_and_horizon() -> None:
    panel = make_panel(
        {
            "A": [100.0, 110.0, 121.0, 133.1],
            "B": [50.0, 55.0, 60.5, 66.55],
        }
    )
    labeled = panel.add_forward_return(horizon_bars=1, execution_lag_bars=1)
    values = {
        (row["symbol"], row["timestamp"]): row["forward_return"]
        for row in labeled.iter_rows(named=True)
    }
    start = datetime(2026, 1, 1)
    assert values[("A", start)] == pytest.approx(0.1)
    assert values[("B", start)] == pytest.approx(0.1)
    assert values[("A", start + timedelta(hours=1))] == pytest.approx(0.1)
    assert values[("A", start + timedelta(hours=2))] is None


def test_as_of_filters_future_rows() -> None:
    start = datetime(2026, 1, 1)
    frame = pl.DataFrame(
        {
            "timestamp": [start, start + timedelta(hours=1)],
            "symbol": ["A", "A"],
            "close": [1.0, 2.0],
            "available_at": [start, start + timedelta(days=1)],
        }
    )
    panel = Panel.from_frame(frame)
    visible = panel.as_of(start + timedelta(hours=2))
    assert visible.frame.height == 1


def test_fingerprint_changes_with_content() -> None:
    first = make_panel({"A": [1.0, 2.0, 3.0]})
    second = make_panel({"A": [1.0, 2.0, 4.0]})
    assert first.fingerprint() != second.fingerprint()
    assert first.fingerprint() == first.fingerprint()
