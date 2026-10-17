from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import polars as pl

from quant.contracts.profile import ValidationProfileDocument
from quant.contracts.results import GateStatus
from quant.data.panel import Panel
from quant.validation.gates.g1_ic import run_g1_ic


def _profile() -> ValidationProfileDocument:
    return ValidationProfileDocument.model_validate(
        {
            "apiVersion": "quant/v1",
            "kind": "ValidationProfile",
            "metadata": {
                "id": "test_profile",
                "market": "crypto_perp",
                "frequency": "1h",
                "scope": "cross_sectional",
                "version": 1,
            },
            "thresholds": {
                "g1_ic": {
                    "rank_ic_mean_min": 0.05,
                    "icir_min": 0.2,
                    "ic_win_rate_min": 0.55,
                    "t_stat_min": 2.0,
                    "min_periods": 100,
                    "subperiod_positive_ratio_min": 0.6,
                }
            },
        }
    )


def _synthetic_panel_and_factor(
    *,
    n_symbols: int = 10,
    n_bars: int = 300,
    seed: int = 7,
) -> tuple[Panel, pl.DataFrame]:
    rng = np.random.default_rng(seed)
    latent = rng.normal(size=(n_bars, n_symbols))
    noise = rng.normal(size=(n_bars, n_symbols))
    returns = np.zeros((n_bars, n_symbols))
    returns[2:] = 0.02 * latent[:-2] + 0.005 * noise[2:]
    prices = 100.0 * np.cumprod(1.0 + returns, axis=0)

    start = datetime(2026, 1, 1)
    timestamps = [start + timedelta(hours=i) for i in range(n_bars)]
    symbols = [f"S{i:02d}" for i in range(n_symbols)]

    panel_frame = pl.DataFrame(
        {
            "timestamp": [timestamps[t] for t in range(n_bars) for _ in range(n_symbols)],
            "symbol": symbols * n_bars,
            "close": prices.reshape(-1).tolist(),
        }
    )
    panel = Panel.from_frame(panel_frame)

    factor_frame = pl.DataFrame(
        {
            "timestamp": [timestamps[t] for t in range(n_bars - 2) for _ in range(n_symbols)],
            "symbol": symbols * (n_bars - 2),
            "factor": latent[:-2].reshape(-1).tolist(),
        }
    )
    return panel, factor_frame


def test_g1_passes_a_known_signal() -> None:
    panel, factor_frame = _synthetic_panel_and_factor()
    result = run_g1_ic(
        factor_frame,
        panel,
        _profile(),
        horizon_bars=1,
        execution_lag_bars=1,
        min_symbols=5,
    )
    assert result.status is GateStatus.PASSED
    assert result.metrics["rank_ic_mean"] is not None
    assert result.metrics["rank_ic_mean"] > 0.5
    assert result.metrics["n_periods"] >= 100


def test_g1_fails_a_noise_factor() -> None:
    panel, factor_frame = _synthetic_panel_and_factor(seed=11)
    rng = np.random.default_rng(99)
    noise_factor = factor_frame.with_columns(
        pl.Series("factor", rng.normal(size=factor_frame.height))
    )
    result = run_g1_ic(
        noise_factor,
        panel,
        _profile(),
        horizon_bars=1,
        execution_lag_bars=1,
        min_symbols=5,
    )
    assert result.status is GateStatus.FAILED
    assert any("rank_ic_mean" in failure for failure in result.failures)
