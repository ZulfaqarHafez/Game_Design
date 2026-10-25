"""Quick-start gold data from Yahoo Finance (COMEX gold futures, GC=F).

No account needed. Limits (measured Oct 2026): 1m bars within the last 30 days
(max 8 days per request), 2m-90m within 60 days, 1h within 730 days, daily unlimited.
GC=F is the futures front month, so prices sit a little above spot XAUUSD
and jump at contract rolls. Use Dukascopy for spot XAUUSD with spreads.
Yahoo data is for personal use under Yahoo's terms.
"""
from __future__ import annotations

import pandas as pd
import requests

URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
INTERVALS = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "60m", "1d": "1d", "1w": "1wk"}
MAX_RANGE = {"1m": "8d", "5m": "60d", "15m": "60d", "30m": "60d", "1h": "730d", "1d": "max", "1w": "max"}


def load(symbol: str = "GC=F", timeframe: str = "1d", range_: str | None = None,
         start: str | None = None, end: str | None = None) -> pd.DataFrame:
    if timeframe not in INTERVALS:
        raise ValueError(f"Yahoo timeframe must be one of {list(INTERVALS)} (resample for 4h)")
    params = {"interval": INTERVALS[timeframe], "includePrePost": "true"}
    if start:
        params["period1"] = int(pd.Timestamp(start, tz="UTC").timestamp())
        params["period2"] = int(pd.Timestamp(end or pd.Timestamp.now(tz="UTC"), tz="UTC").timestamp())
    else:
        params["range"] = range_ or MAX_RANGE[timeframe]
    r = requests.get(URL.format(symbol=symbol), params=params, timeout=30,
                     headers={"User-Agent": "Mozilla/5.0 goldlab"})
    r.raise_for_status()
    res = r.json()["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    df = pd.DataFrame({k: q[k] for k in ("open", "high", "low", "close", "volume")},
                      index=pd.to_datetime(res["timestamp"], unit="s", utc=True))
    df.index.name = "time"
    df = df.dropna(subset=["open", "high", "low", "close"]).astype(float)
    df.attrs.update({"symbol": symbol, "timeframe": timeframe, "source": "yahoo", "price_side": "last"})
    return df
