"""Gold price data: Dukascopy (spot bid/ask), Yahoo (GC futures), CSV files."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .csv_io import read_bars, write_bars
from .resample import resample, infer_timeframe

SAMPLE_DIR = Path(__file__).resolve().parents[2] / "data" / "sample"


def load(source: str = "dukascopy", symbol: str = "XAUUSD", timeframe: str = "1h",
         start: str | None = None, end: str | None = None, path: str | None = None) -> pd.DataFrame:
    """One entry point for every data source.

    source: 'dukascopy' | 'yahoo' | 'csv' | 'sample'
    """
    if source == "dukascopy":
        from . import dukascopy
        return dukascopy.load(symbol, timeframe, start or "2024-01-01", end)
    if source == "yahoo":
        from . import yahoo
        sym = "GC=F" if symbol.upper() in ("XAUUSD", "GOLD") else symbol
        native = "1h" if timeframe in ("2h", "4h") else timeframe
        df = yahoo.load(sym, native, start=start, end=end)
        return resample(df, timeframe) if native != timeframe else df
    if source in ("csv", "sample"):
        if source == "sample":
            path = path or str(SAMPLE_DIR / "XAUUSD_1h.csv.gz")
        df = read_bars(path)
        native = infer_timeframe(df)
        if timeframe and timeframe != native:
            df = resample(df, timeframe)
        if start:
            df = df[df.index >= pd.Timestamp(start, tz="UTC")]
        if end:
            df = df[df.index < pd.Timestamp(end, tz="UTC")]
        df.attrs.update({"symbol": symbol, "timeframe": timeframe or native,
                         "source": source if source == "sample" else df.attrs.get("source")})
        return df
    raise ValueError(f"Unknown data source {source}")


__all__ = ["load", "read_bars", "write_bars", "resample", "infer_timeframe"]
