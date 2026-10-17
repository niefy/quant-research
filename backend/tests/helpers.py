from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl

from quant.contracts.factor import FactorDocument
from quant.data.panel import Panel

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def make_factor_document(
    expression: str,
    *,
    direction: str = "long_high",
    preprocessing: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    frequency: str = "1h",
    horizon: str = "1h",
) -> FactorDocument:
    return FactorDocument.model_validate(
        {
            "apiVersion": "quant/v1",
            "kind": "Factor",
            "metadata": {
                "id": "fac_test",
                "name": "test_factor",
                "version": 1,
                "status": "candidate",
                "created_at": "2026-10-17T10:00:00Z",
                "created_by": "test",
            },
            "spec": {
                "market": "crypto_perp",
                "scope": "cross_sectional",
                "frequency": frequency,
                "horizon": horizon,
                "universe": {"type": "test", "n": 3, "as_of": "rebalance"},
                "inputs": [
                    {"name": "close", "source": "test", "fields": ["close"]},
                ],
                "params": params or {},
                "expression": expression,
                "preprocessing": preprocessing or {"order": []},
                "direction": direction,
                "economic_rationale": "test factor",
                "provenance": {
                    "hypothesis_id": "hyp_test",
                    "source_ids": ["src_test"],
                    "generated_by": "test",
                },
            },
        }
    )


def make_panel(prices: dict[str, list[float]]) -> Panel:
    timestamps: list[datetime] = []
    symbols: list[str] = []
    closes: list[float] = []
    start = datetime(2026, 1, 1)
    for symbol, series in prices.items():
        for index, close in enumerate(series):
            timestamps.append(start + timedelta(hours=index))
            symbols.append(symbol)
            closes.append(close)
    frame = pl.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": symbols,
            "close": closes,
        }
    )
    return Panel.from_frame(frame)
