"""G1: cross-sectional IC / Rank IC predictive-power gate."""

from __future__ import annotations

from math import isfinite
from typing import Any

import polars as pl

from quant.contracts.profile import ValidationProfileDocument
from quant.contracts.results import GateResult, GateStatus
from quant.data.panel import Panel
from quant.validation.metrics import rank_ic_series, summarize_ic


def run_g1_ic(
    factor_frame: pl.DataFrame,
    panel: Panel,
    profile: ValidationProfileDocument,
    *,
    horizon_bars: int = 1,
    execution_lag_bars: int = 1,
    min_symbols: int = 5,
    n_subperiods: int = 4,
) -> GateResult:
    if profile.metadata.scope != "cross_sectional":
        return GateResult(
            gate="G1",
            status=GateStatus.SKIPPED,
            failures=[],
            details={
                "reason": "G1 Rank IC is only defined for cross_sectional factors; "
                "time_series strategies use a different gate implementation"
            },
        )

    labels = panel.add_forward_return(
        horizon_bars=horizon_bars,
        execution_lag_bars=execution_lag_bars,
    ).select(["timestamp", "symbol", "forward_return"])
    ic_series = rank_ic_series(
        factor_frame,
        labels,
        min_symbols=min_symbols,
    )
    summary = summarize_ic(ic_series, n_subperiods=n_subperiods)
    thresholds = profile.thresholds.g1_ic

    failures: list[str] = []
    if summary.n_periods < thresholds.min_periods:
        failures.append(
            f"n_periods={summary.n_periods} < min_periods={thresholds.min_periods}"
        )
    if not _at_least(summary.rank_ic_mean, thresholds.rank_ic_mean_min):
        failures.append(
            f"rank_ic_mean={_fmt(summary.rank_ic_mean)} < {thresholds.rank_ic_mean_min}"
        )
    if not _at_least(summary.icir, thresholds.icir_min):
        failures.append(f"icir={_fmt(summary.icir)} < {thresholds.icir_min}")
    if not _at_least(summary.ic_win_rate, thresholds.ic_win_rate_min):
        failures.append(
            f"ic_win_rate={_fmt(summary.ic_win_rate)} < {thresholds.ic_win_rate_min}"
        )
    if not _at_least(summary.t_stat, thresholds.t_stat_min):
        failures.append(f"t_stat={_fmt(summary.t_stat)} < {thresholds.t_stat_min}")
    if not _at_least(
        summary.subperiod_positive_ratio,
        thresholds.subperiod_positive_ratio_min,
    ):
        failures.append(
            "subperiod_positive_ratio="
            f"{_fmt(summary.subperiod_positive_ratio)} < "
            f"{thresholds.subperiod_positive_ratio_min}"
        )

    metrics: dict[str, float | int | str | None] = {
        "rank_ic_mean": _finite_or_none(summary.rank_ic_mean),
        "ic_std": _finite_or_none(summary.ic_std),
        "icir": _finite_or_none(summary.icir),
        "ic_win_rate": _finite_or_none(summary.ic_win_rate),
        "t_stat": _finite_or_none(summary.t_stat),
        "n_periods": summary.n_periods,
        "subperiod_positive_ratio": _finite_or_none(summary.subperiod_positive_ratio),
    }
    details: dict[str, Any] = {
        "thresholds": thresholds.model_dump(mode="json"),
        "horizon_bars": horizon_bars,
        "execution_lag_bars": execution_lag_bars,
        "min_symbols": min_symbols,
        "ic_series": [
            {
                "timestamp": str(row["timestamp"]),
                "ic": row["ic"],
                "n_symbols": row["n_symbols"],
            }
            for row in ic_series.iter_rows(named=True)
        ],
    }

    return GateResult(
        gate="G1",
        status=GateStatus.FAILED if failures else GateStatus.PASSED,
        metrics=metrics,
        failures=failures,
        details=details,
    )


def _finite_or_none(value: float) -> float | None:
    return value if isfinite(value) else None


def _at_least(value: float, threshold: float) -> bool:
    return isfinite(value) and value >= threshold


def _fmt(value: float) -> str:
    return f"{value:.4f}" if isfinite(value) else "nan"
