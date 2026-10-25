"""Indicators that match TradingView's Pine Script `ta.*` built-ins.

Formulas follow the "Pine equivalent" code in the Pine Script reference:
  * ta.ema   alpha = 2/(len+1)
  * ta.rma   alpha = 1/len, seeded with an SMA (used by RSI, ATR, DMI)
  * ta.stdev population standard deviation (biased), as Pine does by default
All functions take and return pandas Series aligned to the bar index.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _s(x) -> pd.Series:
    return x if isinstance(x, pd.Series) else pd.Series(x)


def sma(src: pd.Series, length: int) -> pd.Series:
    return src.rolling(int(length), min_periods=int(length)).mean()


def _recursive(src: pd.Series, length: int, alpha: float) -> pd.Series:
    """Exponential smoothing seeded with the SMA of the first `length` values."""
    vals = src.to_numpy(dtype="float64")
    out = np.full(len(vals), np.nan)
    length = int(length)
    prev = np.nan
    window: list[float] = []
    for i, v in enumerate(vals):
        if np.isnan(prev):
            if np.isnan(v):
                window.clear()
                continue
            window.append(v)
            if len(window) >= length:
                prev = float(np.mean(window[-length:]))
                out[i] = prev
            continue
        if not np.isnan(v):
            prev = alpha * v + (1 - alpha) * prev
        out[i] = prev
    return pd.Series(out, index=src.index)


def ema(src: pd.Series, length: int) -> pd.Series:
    return _recursive(src, length, 2.0 / (int(length) + 1))


def rma(src: pd.Series, length: int) -> pd.Series:
    return _recursive(src, length, 1.0 / int(length))


def wma(src: pd.Series, length: int) -> pd.Series:
    length = int(length)
    w = np.arange(1, length + 1, dtype="float64")
    return src.rolling(length).apply(lambda x: np.dot(x, w) / w.sum(), raw=True)


def hma(src: pd.Series, length: int) -> pd.Series:
    length = int(length)
    return wma(2 * wma(src, length // 2) - wma(src, length), int(np.sqrt(length)))


def vwma(src: pd.Series, volume: pd.Series, length: int) -> pd.Series:
    return sma(src * volume, length) / sma(volume, length)


def stdev(src: pd.Series, length: int) -> pd.Series:
    return src.rolling(int(length)).std(ddof=0)


def change(src: pd.Series, length: int = 1) -> pd.Series:
    return src - src.shift(int(length))


def roc(src: pd.Series, length: int) -> pd.Series:
    prev = src.shift(int(length))
    return 100 * (src - prev) / prev


def highest(src: pd.Series, length: int) -> pd.Series:
    return src.rolling(int(length), min_periods=int(length)).max()


def lowest(src: pd.Series, length: int) -> pd.Series:
    return src.rolling(int(length), min_periods=int(length)).min()


def tr(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    pc = close.shift(1)
    out = pd.concat([high - low, (high - pc).abs(), (low - pc).abs()], axis=1).max(axis=1)
    out.iloc[0] = high.iloc[0] - low.iloc[0]
    return out


def atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    return rma(tr(high, low, close), length)


def rsi(src: pd.Series, length: int = 14) -> pd.Series:
    d = src.diff()
    up = rma(d.clip(lower=0), length)
    dn = rma((-d).clip(lower=0), length)
    with np.errstate(divide="ignore", invalid="ignore"):
        raw = 100 - 100 / (1 + up / dn)
    out = np.where(dn == 0, 100.0, np.where(up == 0, 0.0, raw))
    return pd.Series(out, index=src.index).where(up.notna() & dn.notna())


def bb(src: pd.Series, length: int = 20, mult: float = 2.0):
    basis = sma(src, length)
    dev = mult * stdev(src, length)
    return basis, basis + dev, basis - dev


def macd(src: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    line = ema(src, fast) - ema(src, slow)
    sig = ema(line, signal)
    return line, sig, line - sig


def stoch(close: pd.Series, high: pd.Series, low: pd.Series, length: int = 14) -> pd.Series:
    hh, ll = highest(high, length), lowest(low, length)
    return 100 * (close - ll) / (hh - ll)


def cci(src: pd.Series, length: int = 20) -> pd.Series:
    m = sma(src, length)
    md = src.rolling(int(length)).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
    return (src - m) / (0.015 * md)


def dmi(high: pd.Series, low: pd.Series, close: pd.Series, di_len: int = 14, adx_len: int = 14):
    up = high.diff()
    dn = -low.diff()
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    trur = rma(tr(high, low, close), di_len)
    plus = 100 * rma(pd.Series(plus_dm, index=high.index), di_len) / trur
    minus = 100 * rma(pd.Series(minus_dm, index=high.index), di_len) / trur
    s = (plus + minus).replace(0, np.nan)
    adx_ = 100 * rma(((plus - minus).abs() / s).fillna(0), adx_len)
    return plus, minus, adx_


def adx(high, low, close, length: int = 14) -> pd.Series:
    return dmi(high, low, close, length, length)[2]


def supertrend(high: pd.Series, low: pd.Series, close: pd.Series, factor: float = 3.0,
               atr_len: int = 10):
    """Returns (line, direction). direction = -1 in an uptrend, +1 in a downtrend (Pine convention)."""
    a = atr(high, low, close, atr_len).to_numpy()
    hl2 = ((high + low) / 2).to_numpy()
    c = close.to_numpy()
    n = len(c)
    upper = hl2 + factor * a
    lower = hl2 - factor * a
    st = np.full(n, np.nan)
    direction = np.full(n, np.nan)
    for i in range(n):
        if np.isnan(a[i]):
            continue
        if i > 0 and not np.isnan(st[i - 1]):
            lower[i] = lower[i] if (lower[i] > lower[i - 1] or c[i - 1] < lower[i - 1]) else lower[i - 1]
            upper[i] = upper[i] if (upper[i] < upper[i - 1] or c[i - 1] > upper[i - 1]) else upper[i - 1]
            prev_st = st[i - 1]
            if prev_st == upper[i - 1]:
                direction[i] = -1 if c[i] > upper[i] else 1
            else:
                direction[i] = 1 if c[i] < lower[i] else -1
        else:
            direction[i] = 1
        st[i] = lower[i] if direction[i] == -1 else upper[i]
    return pd.Series(st, index=close.index), pd.Series(direction, index=close.index)


def keltner(high, low, close, length: int = 20, mult: float = 1.5):
    basis = ema(close, length)
    rng = atr(high, low, close, length)
    return basis, basis + mult * rng, basis - mult * rng


def crossover(a: pd.Series, b) -> pd.Series:
    b = b if isinstance(b, pd.Series) else pd.Series(b, index=a.index)
    return ((a > b) & (a.shift(1) <= b.shift(1))).fillna(False)


def crossunder(a: pd.Series, b) -> pd.Series:
    b = b if isinstance(b, pd.Series) else pd.Series(b, index=a.index)
    return ((a < b) & (a.shift(1) >= b.shift(1))).fillna(False)


def vwap(high, low, close, volume, tz: str = "America/New_York", roll_hour: int = 17) -> pd.Series:
    """Session-anchored VWAP that resets at the FX day roll (17:00 New York)."""
    tp = (high + low + close) / 3
    key = (close.index.tz_convert(tz) + pd.Timedelta(hours=24 - roll_hour)).date
    pv = (tp * volume).groupby(key).cumsum()
    vv = volume.groupby(key).cumsum()
    return (pv / vv.replace(0, np.nan)).fillna(tp)


# --- time and session helpers -----------------------------------------

def _parse_window(window: str):
    a, b = window.replace(":", "").split("-")
    return int(a[:2]) * 60 + int(a[2:]), int(b[:2]) * 60 + int(b[2:])


def in_session(index: pd.DatetimeIndex, window: str, tz: str = "UTC") -> pd.Series:
    """True for bars whose open time is inside 'HHMM-HHMM' in the given time zone."""
    local = index.tz_convert(tz)
    mins = local.hour * 60 + local.minute
    s, e = _parse_window(window)
    mask = (mins >= s) & (mins < e) if s < e else (mins >= s) | (mins < e)
    return pd.Series(mask, index=index)


def session_range(df: pd.DataFrame, window: str, tz: str = "UTC"):
    """High/low of the most recent completed `window` session (e.g. the Asian range).

    The value appears on the first bar after the window closes and is held
    until the next window opens; bars inside a window are NaN, so a strategy
    can never peek at a range that is still forming. Matches the Pine helper
    emitted by goldlab.pine.
    """
    inside = in_session(df.index, window, tz).to_numpy()
    hi_src = df["high"].to_numpy(float)
    lo_src = df["low"].to_numpy(float)
    n = len(df)
    hi = np.full(n, np.nan)
    lo = np.full(n, np.nan)
    run_hi = run_lo = np.nan
    done_hi = done_lo = np.nan
    for i in range(n):
        if inside[i]:
            if i == 0 or not inside[i - 1]:
                run_hi, run_lo = hi_src[i], lo_src[i]
                done_hi = done_lo = np.nan
            else:
                run_hi = max(run_hi, hi_src[i])
                run_lo = min(run_lo, lo_src[i])
            continue
        if i > 0 and inside[i - 1]:
            done_hi, done_lo = run_hi, run_lo
        hi[i], lo[i] = done_hi, done_lo
    return pd.Series(hi, index=df.index), pd.Series(lo, index=df.index)


def barssince(cond: pd.Series) -> pd.Series:
    c = cond.fillna(False).to_numpy(bool)
    out = np.full(len(c), np.nan)
    last = -1
    for i, v in enumerate(c):
        if v:
            last = i
        if last >= 0:
            out[i] = i - last
    return pd.Series(out, index=cond.index)


def valuewhen(cond: pd.Series, src: pd.Series, occurrence: int = 0) -> pd.Series:
    c = cond.fillna(False).to_numpy(bool)
    v = src.to_numpy(float)
    out = np.full(len(c), np.nan)
    hits: list[float] = []
    for i in range(len(c)):
        if c[i]:
            hits.append(v[i])
        if len(hits) > occurrence:
            out[i] = hits[-1 - occurrence]
    return pd.Series(out, index=src.index)


def hour(index: pd.DatetimeIndex, tz: str = "UTC") -> pd.Series:
    return pd.Series(index.tz_convert(tz).hour, index=index)


def minute(index: pd.DatetimeIndex, tz: str = "UTC") -> pd.Series:
    return pd.Series(index.tz_convert(tz).minute, index=index)


def weekday(index: pd.DatetimeIndex, tz: str = "UTC") -> pd.Series:
    """Monday=0 ... Sunday=6."""
    return pd.Series(index.tz_convert(tz).weekday, index=index)


def new_day(index: pd.DatetimeIndex, tz: str = "America/New_York", roll_hour: int = 17) -> pd.Series:
    key = pd.Series((index.tz_convert(tz) + pd.Timedelta(hours=24 - roll_hour)).date, index=index)
    return key != key.shift(1)
