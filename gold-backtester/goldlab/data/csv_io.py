"""Read bars from CSV, including TradingView's "Export chart data" files.

TradingView exports look like:  time,open,high,low,close,Volume,...
where time is unix seconds (or ISO text, depending on the export option).
MetaTrader and generic CSVs (Date,Time,Open,High,Low,Close,Volume) also work.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def read_bars(path: str | Path, tz: str = "UTC") -> pd.DataFrame:
    path = Path(path)
    sep = "\t" if path.suffix.lower() in (".tsv",) else None
    raw = pd.read_csv(path, sep=sep, engine="python", compression="infer")
    cols = {c: c.strip().lower().strip("<>") for c in raw.columns}
    raw = raw.rename(columns=cols)

    if "date" in raw and "time" in raw:
        ts = pd.to_datetime(raw["date"].astype(str) + " " + raw["time"].astype(str))
    else:
        tcol = next(c for c in ("time", "datetime", "date", "timestamp") if c in raw)
        col = raw[tcol]
        if pd.api.types.is_numeric_dtype(col):
            unit = "ms" if col.iloc[0] > 1e11 else "s"
            ts = pd.to_datetime(col, unit=unit, utc=True)
        else:
            ts = pd.to_datetime(col, utc=False, format="mixed")
    ts = pd.DatetimeIndex(ts)
    ts = ts.tz_localize(tz) if ts.tz is None else ts
    ts = ts.tz_convert("UTC")

    out = pd.DataFrame(index=ts)
    for k in ("open", "high", "low", "close"):
        out[k] = pd.to_numeric(raw[k], errors="coerce").values
    vol = next((c for c in ("volume", "tickvol", "vol", "tick_volume") if c in raw), None)
    out["volume"] = pd.to_numeric(raw[vol], errors="coerce").fillna(0).values if vol else 0.0
    if "spread" in raw:
        out["spread"] = pd.to_numeric(raw["spread"], errors="coerce").values
    out.index.name = "time"
    out = out.dropna(subset=["open", "high", "low", "close"]).sort_index()
    out = out[~out.index.duplicated()]
    out.attrs.update({"symbol": path.stem, "source": f"csv:{path.name}"})
    return out


def write_bars(df: pd.DataFrame, path: str | Path) -> None:
    out = df.copy()
    out.index = out.index.strftime("%Y-%m-%dT%H:%M:%SZ")
    out.to_csv(path, float_format="%.3f")
