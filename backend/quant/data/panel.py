"""Canonical long-form panel used by the research kernel."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast

import polars as pl

RESERVED_COLUMNS = {"timestamp", "symbol", "event_time", "available_at", "ingested_at"}


class PanelError(ValueError):
    """Raised when panel data violates the research contract."""


@dataclass(frozen=True)
class Panel:
    """A long panel with one row per (timestamp, symbol).

    The mandatory time semantics are:

    - ``timestamp``: the event/decision time used by factor expressions.
    - ``available_at``: the first time the row was observable; never later
      than the time a factor is evaluated.
    - ``ingested_at``: when the platform recorded the row (optional).
    """

    frame: pl.DataFrame
    time_col: str = "timestamp"
    symbol_col: str = "symbol"

    def __post_init__(self) -> None:
        object.__setattr__(self, "frame", self._normalize(self.frame))
        self._validate()

    @classmethod
    def from_frame(
        cls,
        frame: pl.DataFrame,
        *,
        time_col: str = "timestamp",
        symbol_col: str = "symbol",
    ) -> Panel:
        return cls(frame=frame, time_col=time_col, symbol_col=symbol_col)

    @staticmethod
    def _normalize(frame: pl.DataFrame) -> pl.DataFrame:
        if frame.is_empty():
            raise PanelError("panel must not be empty")

        columns = set(frame.columns)
        source_time: str | None = None
        for candidate in ("timestamp", "datetime", "event_time"):
            if candidate in columns:
                source_time = candidate
                break
        if source_time is None:
            raise PanelError("panel is missing a timestamp/datetime/event_time column")

        if "symbol" not in columns:
            raise PanelError("panel is missing a symbol column")

        result = frame.rename({source_time: "timestamp", "symbol": "symbol"})
        result = result.with_columns(_to_datetime(result["timestamp"]).alias("timestamp"))
        result = result.with_columns(pl.col("symbol").cast(pl.Utf8))

        if "event_time" in result.columns:
            result = result.with_columns(_to_datetime(result["event_time"]).alias("event_time"))
        else:
            result = result.with_columns(pl.col("timestamp").alias("event_time"))

        if "available_at" in result.columns:
            result = result.with_columns(_to_datetime(result["available_at"]).alias("available_at"))
        else:
            result = result.with_columns(pl.col("timestamp").alias("available_at"))

        if "ingested_at" in result.columns:
            result = result.with_columns(_to_datetime(result["ingested_at"]).alias("ingested_at"))

        result = result.sort(["timestamp", "symbol"])
        return result

    def _validate(self) -> None:
        frame = self.frame
        if frame["timestamp"].null_count() > 0:
            raise PanelError("timestamp contains nulls")
        if frame["symbol"].null_count() > 0:
            raise PanelError("symbol contains nulls")

        duplicate_count = frame.select(["timestamp", "symbol"]).is_duplicated().sum()
        if duplicate_count:
            raise PanelError(f"panel contains {duplicate_count} duplicate (timestamp, symbol) rows")

        if self.time_col not in frame.columns or self.symbol_col not in frame.columns:
            raise PanelError("panel lost required time/symbol columns")

        for name in self.field_names:
            dtype = frame[name].dtype
            if not dtype.is_numeric():
                raise PanelError(f"field '{name}' must be numeric, got {dtype}")

    @property
    def field_names(self) -> tuple[str, ...]:
        return tuple(name for name in self.frame.columns if name not in RESERVED_COLUMNS)

    def require_fields(self, names: Iterable[str]) -> None:
        missing = sorted(set(names) - set(self.field_names))
        if missing:
            raise PanelError(f"panel is missing required fields: {missing}")

    def slice(self, start: datetime | None = None, end: datetime | None = None) -> Panel:
        frame = self.frame
        if start is not None:
            frame = frame.filter(pl.col("timestamp") >= start)
        if end is not None:
            frame = frame.filter(pl.col("timestamp") <= end)
        return Panel(frame=frame, time_col=self.time_col, symbol_col=self.symbol_col)

    def as_of(self, as_of: datetime) -> Panel:
        """Return only rows that were observable at ``as_of``."""
        return Panel(
            frame=self.frame.filter(pl.col("available_at") <= as_of),
            time_col=self.time_col,
            symbol_col=self.symbol_col,
        )

    def add_forward_return(
        self,
        *,
        close_col: str = "close",
        horizon_bars: int = 1,
        execution_lag_bars: int = 1,
    ) -> pl.DataFrame:
        """Add a label using execution-delayed, forward-looking returns.

        The label is intentionally future-looking; it must never be used as a
        factor input. With the default lag of one bar, a signal observed at
        ``t`` is executed at ``t+1`` and held for ``horizon_bars``.
        """
        if horizon_bars < 1:
            raise ValueError("horizon_bars must be >= 1")
        if execution_lag_bars < 0:
            raise ValueError("execution_lag_bars must be >= 0")
        self.require_fields([close_col])

        entry_offset = execution_lag_bars
        exit_offset = execution_lag_bars + horizon_bars
        entry = pl.col(close_col).shift(-entry_offset).over(self.symbol_col)
        exit_price = pl.col(close_col).shift(-exit_offset).over(self.symbol_col)
        return self.frame.with_columns((exit_price / entry - 1.0).alias("forward_return"))

    def fingerprint(self) -> str:
        """Content-sensitive fingerprint for factor cache keys."""
        schema = json.dumps(
            [(name, str(dtype)) for name, dtype in self.frame.schema.items()],
            ensure_ascii=True,
        )
        row_hash = int(self.frame.hash_rows(seed=0).sum() or 0)
        payload = f"{schema}|{self.frame.height}|{row_hash}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _to_datetime(series: pl.Series) -> pl.Series:
    dtype = series.dtype
    if isinstance(dtype, pl.Datetime):
        return series.cast(pl.Datetime("us"))
    if dtype in {pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64}:
        max_abs = series.cast(pl.Int64).abs().max()
        if max_abs is None:
            raise PanelError("timestamp column contains only nulls")
        value = int(cast(int, max_abs))
        unit: Literal["ns", "us", "ms"]
        if value >= 10**17:
            unit = "ns"
        elif value >= 10**14:
            unit = "us"
        elif value >= 10**11:
            unit = "ms"
        else:
            series = series.cast(pl.Int64) * 1000
            unit = "ms"
        return series.cast(pl.Int64).cast(pl.Datetime(unit)).cast(pl.Datetime("us"))
    if dtype == pl.Utf8:
        return (
            series.str.to_datetime(time_zone="UTC")
            .dt.replace_time_zone(None)
            .cast(pl.Datetime("us"))
        )
    raise PanelError(f"unsupported timestamp dtype: {dtype}")
