"""Binance USDT-M perpetual adapter for the existing local parquet layout.

Expected layout::

    <base_dir>/<SYMBOL>/<SYMBOL>-<frequency>.parquet

The existing files store ``datetime`` as epoch seconds. They are treated as
event/available time because Binance klines are only complete at close.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from quant.data.panel import Panel, PanelError

_TIME_COLUMN_CANDIDATES = ("datetime", "timestamp", "event_time")


@dataclass(frozen=True)
class BinancePerpAdapter:
    base_dir: Path
    frequency: str = "1h"
    symbols: tuple[str, ...] | None = None

    @property
    def market(self) -> str:
        return "crypto_perp"

    def available_symbols(self) -> list[str]:
        if not self.base_dir.exists():
            return []
        result: list[str] = []
        for path in sorted(self.base_dir.iterdir()):
            if path.is_dir() and (path / f"{path.name}-{self.frequency}.parquet").exists():
                result.append(path.name)
        return result

    def load_panel(
        self,
        *,
        fields: list[str] | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        symbols: list[str] | None = None,
    ) -> Panel:
        requested = symbols if symbols is not None else list(self.symbols or self.available_symbols())
        if not requested:
            raise PanelError(f"no symbols found under {self.base_dir} for frequency {self.frequency}")

        frames: list[pl.DataFrame] = []
        for symbol in requested:
            path = self.base_dir / symbol / f"{symbol}-{self.frequency}.parquet"
            if not path.exists():
                if symbols is not None:
                    raise PanelError(f"missing parquet for requested symbol {symbol}: {path}")
                continue
            frame = pl.read_parquet(path)
            time_column = next((name for name in _TIME_COLUMN_CANDIDATES if name in frame.columns), None)
            if time_column is None:
                raise PanelError(f"{path} has no datetime/timestamp column")
            if time_column != "timestamp":
                frame = frame.rename({time_column: "timestamp"})

            available = [name for name in frame.columns if name != "timestamp"]
            chosen = fields if fields is not None else available
            missing = sorted(set(chosen) - set(frame.columns))
            if missing:
                raise PanelError(f"{path} is missing fields: {missing}")

            frame = frame.select(["timestamp", *chosen]).with_columns(
                pl.lit(symbol).alias("symbol"),
                pl.lit(_file_mtime(path)).alias("ingested_at"),
            )
            frames.append(frame)

        if not frames:
            raise PanelError(f"no readable parquet files for frequency {self.frequency}")

        combined = pl.concat(frames, how="vertical_relaxed")
        panel = Panel.from_frame(combined)
        return panel.slice(start=start, end=end)


def _file_mtime(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).replace(tzinfo=None)
