"""Cross-sectional IC metrics and Newey-West inference."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import polars as pl
from scipy import stats


@dataclass(frozen=True)
class ICSummary:
    rank_ic_mean: float
    ic_std: float
    icir: float
    ic_win_rate: float
    t_stat: float
    n_periods: int
    subperiod_positive_ratio: float


def rank_ic_series(
    factor_frame: pl.DataFrame,
    labels: pl.DataFrame,
    *,
    factor_col: str = "factor",
    label_col: str = "forward_return",
    min_symbols: int = 5,
) -> pl.DataFrame:
    """Compute one Spearman rank IC per timestamp.

    Both inputs must contain ``timestamp`` and ``symbol``. Rows with a null
    factor or label are ignored; timestamps with fewer than ``min_symbols``
    valid names are skipped rather than producing an unstable correlation.
    """
    if min_symbols < 2:
        raise ValueError("min_symbols must be >= 2")
    merged = factor_frame.select(["timestamp", "symbol", factor_col]).join(
        labels.select(["timestamp", "symbol", label_col]),
        on=["timestamp", "symbol"],
        how="inner",
    )

    timestamps: list[object] = []
    ics: list[float] = []
    counts: list[int] = []
    for timestamp, group in merged.group_by("timestamp", maintain_order=True):
        clean = group.select([factor_col, label_col]).drop_nulls()
        if clean.height < min_symbols:
            continue
        x = clean[factor_col].to_numpy()
        y = clean[label_col].to_numpy()
        if np.nanstd(x) == 0.0 or np.nanstd(y) == 0.0:
            continue
        # scipy returns a named result in recent versions; index 0 is stable
        # across versions and avoids depending on the attribute name.
        rho = float(stats.spearmanr(x, y).statistic)
        if np.isfinite(rho):
            timestamps.append(timestamp[0] if isinstance(timestamp, tuple) else timestamp)
            ics.append(rho)
            counts.append(clean.height)

    return pl.DataFrame(
        {
            "timestamp": timestamps,
            "ic": ics,
            "n_symbols": counts,
        },
        schema={"timestamp": merged.schema["timestamp"], "ic": pl.Float64, "n_symbols": pl.UInt32},
    )


def summarize_ic(ic_series: pl.DataFrame, *, n_subperiods: int = 4) -> ICSummary:
    values = ic_series["ic"].drop_nulls().to_numpy()
    n_periods = int(values.size)
    if n_periods == 0:
        return ICSummary(
            rank_ic_mean=float("nan"),
            ic_std=float("nan"),
            icir=float("nan"),
            ic_win_rate=float("nan"),
            t_stat=float("nan"),
            n_periods=0,
            subperiod_positive_ratio=float("nan"),
        )

    mean = float(np.mean(values))
    std = float(np.std(values, ddof=1)) if n_periods > 1 else float("nan")
    icir = float(mean / std) if n_periods > 1 and std > 0 else float("nan")
    win_rate = float(np.mean(values > 0.0))
    t_stat = newey_west_t(values)
    positive_ratio = subperiod_positive_ratio(values, n_subperiods=n_subperiods)
    return ICSummary(
        rank_ic_mean=mean,
        ic_std=std,
        icir=icir,
        ic_win_rate=win_rate,
        t_stat=t_stat,
        n_periods=n_periods,
        subperiod_positive_ratio=positive_ratio,
    )


def newey_west_t(values: np.ndarray, *, max_lag: int | None = None) -> float:
    """Newey-West adjusted t-statistic for the mean of a time series.

    ``max_lag`` defaults to the common data-dependent rule
    ``floor(4 * (n / 100) ** (2/9))``. The variance is guaranteed to be
    non-negative by the Bartlett kernel weights.
    """
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    n = x.size
    if n < 2:
        return float("nan")
    mean = float(np.mean(x))
    demeaned = x - mean
    gamma0 = float(np.dot(demeaned, demeaned) / n)
    lag = max_lag if max_lag is not None else int(np.floor(4.0 * (n / 100.0) ** (2.0 / 9.0)))
    lag = max(0, min(lag, n - 1))
    variance = gamma0
    for offset in range(1, lag + 1):
        gamma = float(np.dot(demeaned[offset:], demeaned[:-offset]) / n)
        weight = 1.0 - offset / (lag + 1.0)
        variance += 2.0 * weight * gamma
    if variance <= 0.0:
        return float("nan")
    return float(mean / np.sqrt(variance / n))


def subperiod_positive_ratio(values: np.ndarray, *, n_subperiods: int = 4) -> float:
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return float("nan")
    chunks = min(n_subperiods, x.size)
    if chunks < 1:
        return float("nan")
    means = [float(np.mean(chunk)) for chunk in np.array_split(x, chunks)]
    return float(np.mean([value > 0.0 for value in means]))
