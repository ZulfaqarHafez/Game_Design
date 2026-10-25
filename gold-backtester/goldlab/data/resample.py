"""Resample OHLC bars to higher timeframes.

Daily bars follow the FX convention TradingView uses for spot gold: the
trading day rolls at 17:00 New York time, not UTC midnight.
"""
from __future__ import annotations

import pandas as pd

RULES = {
    "1m": "1min", "3m": "3min", "5m": "5min", "15m": "15min", "30m": "30min",
    "1h": "1h", "2h": "2h", "4h": "4h", "1d": "1D", "1w": "1W",
}
MINUTES = {"1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "2h": 120,
           "4h": 240, "1d": 1440, "1w": 10080}
# Which Dukascopy native file to build each timeframe from.
NATIVE_SOURCE = {"1m": "1m", "3m": "1m", "5m": "1m", "15m": "1m", "30m": "1m",
                 "1h": "1h", "2h": "1h", "4h": "1h", "1d": "1h", "1w": "1h"}


def resample(df: pd.DataFrame, timeframe: str, day_roll_tz: str = "America/New_York",
             day_roll_hour: int = 17) -> pd.DataFrame:
    if timeframe not in RULES:
        raise ValueError(f"Unknown timeframe {timeframe}; use one of {list(RULES)}")
    agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
    if "volume" in df:
        agg["volume"] = "sum"
    if "spread" in df:
        agg["spread"] = "mean"
    if timeframe in ("1d", "1w"):
        # Shift so that 17:00 New York becomes midnight, group, then label the
        # bar with the session date (like TradingView's daily FX bars).
        local = df.tz_convert(day_roll_tz)
        shifted = local.index + pd.Timedelta(hours=24 - day_roll_hour)
        g = local.set_axis(shifted.tz_localize(None).normalize() if timeframe == "1d"
                           else shifted.tz_localize(None))
        out = g.resample(RULES[timeframe]).agg(agg) if timeframe == "1w" else g.groupby(level=0).agg(agg)
        out.index = pd.DatetimeIndex(out.index).tz_localize("UTC")
    else:
        out = df.resample(RULES[timeframe], label="left", closed="left").agg(agg)
    out = out.dropna(subset=["open", "close"])
    out.index.name = "time"
    out.attrs = dict(df.attrs, timeframe=timeframe)
    return out


def infer_timeframe(df: pd.DataFrame) -> str:
    if len(df) < 3:
        return "1h"
    step = pd.Series(df.index).diff().dropna().dt.total_seconds().median() / 60
    best = min(MINUTES, key=lambda k: abs(MINUTES[k] - step))
    return best
