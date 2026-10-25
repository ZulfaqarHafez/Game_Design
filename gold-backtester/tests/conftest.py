import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def bars(rows, start="2026-01-05 00:00", freq="1h", spread=None):
    """rows: list of (open, high, low, close)."""
    idx = pd.date_range(start, periods=len(rows), freq=freq, tz="UTC")
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx, dtype=float)
    df["volume"] = 1.0
    if spread is not None:
        df["spread"] = spread
    df.attrs.update(symbol="XAUUSD", timeframe="1h", source="test")
    return df


@pytest.fixture
def make_bars():
    return bars


@pytest.fixture
def random_walk():
    rng = np.random.default_rng(42)
    n = 3000
    c = 2000 + np.cumsum(rng.normal(0, 3, n))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + rng.uniform(0, 2, n)
    l = np.minimum(o, c) - rng.uniform(0, 2, n)
    df = pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "volume": 1.0, "spread": 0.3},
                      index=pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC"))
    df.attrs.update(symbol="XAUUSD", timeframe="1h", source="synthetic")
    return df
