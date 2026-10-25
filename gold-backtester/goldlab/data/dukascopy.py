"""Download XAUUSD candles from Dukascopy's public datafeed.

Dukascopy publishes free bid and ask candles. Having both sides lets the
backtest charge the real spread instead of assuming zero spread like a
TradingView chart does.

File layout (months are 0-based, times are UTC):
    {base}/{SYMBOL}/{YYYY}/{MM}/{DD}/BID_candles_min_1.bi5   one day of 1m bars
    {base}/{SYMBOL}/{YYYY}/{MM}/BID_candles_hour_1.bi5      one month of 1h bars
    {base}/{SYMBOL}/{YYYY}/BID_candles_day_1.bi5            one year of 1d bars

Each file is LZMA-compressed. Each record is 24 bytes, big endian:
    int32 seconds-from-file-start, open, close, low, high (int32), volume (float32)
Prices are integers scaled by 1/1000 for XAUUSD.

The server rate-limits (HTTP 429), so requests are throttled, retried with
backoff and cached on disk. Weekend/holiday files are empty.
"""
from __future__ import annotations

import lzma
import struct
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

BASE_URL = "https://datafeed.dukascopy.com/datafeed"
POINT = {"XAUUSD": 1000.0, "XAGUSD": 1000.0}
RECORD = struct.Struct(">5if")

DEFAULT_CACHE = Path(__file__).resolve().parents[2] / "data" / "cache" / "dukascopy"


class DukascopyClient:
    def __init__(self, cache_dir: Path | str = DEFAULT_CACHE, pause: float = 0.6,
                 max_retries: int = 12, session: requests.Session | None = None,
                 verbose: bool = True):
        self.cache_dir = Path(cache_dir)
        self.pause = pause
        self.max_retries = max_retries
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", "goldlab-backtester/0.1")
        self.verbose = verbose
        self._last = 0.0

    # -- low level -----------------------------------------------------
    def _fetch(self, rel: str, recent: bool = False) -> bytes:
        path = self.cache_dir / rel
        if path.exists() and not (recent and path.stat().st_size == 0):
            return path.read_bytes()
        url = f"{BASE_URL}/{rel}"
        delay = 2.0
        for attempt in range(self.max_retries + 1):
            wait = self.pause - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.time()
            try:
                r = self.session.get(url, timeout=30)
            except requests.RequestException:
                r = None
            if r is not None and r.status_code == 200 and r.content:
                try:
                    lzma.decompress(r.content)
                except lzma.LZMAError:  # throttled/garbled body: retry
                    r = None
            if r is not None and r.status_code == 200:
                if not (recent and not r.content):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(r.content)
                return r.content
            if r is not None and r.status_code == 404:
                if not recent:  # old empty periods never change; recent ones might still be published
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"")
                return b""
            if attempt == self.max_retries:
                code = r.status_code if r is not None else "network error"
                raise RuntimeError(f"Dukascopy download failed ({code}): {url}. "
                                   "Files fetched so far are cached; run again later to resume.")
            if r is not None and r.status_code == 429:
                self.pause = min(self.pause * 1.5, 5.0)  # slow down for the rest of the session
            time.sleep(delay)
            delay = min(delay * 2, 120)
        return b""

    @staticmethod
    def _decode(raw: bytes, start: datetime, point: float) -> pd.DataFrame:
        if not raw:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        data = lzma.decompress(raw)
        n = len(data) // RECORD.size
        arr = np.frombuffer(data[: n * RECORD.size], dtype=">i4").reshape(n, 6)
        secs = arr[:, 0].astype("int64")
        vol = np.frombuffer(data[: n * RECORD.size], dtype=">f4").reshape(n, 6)[:, 5]
        idx = pd.to_datetime(start) + pd.to_timedelta(secs, unit="s")
        df = pd.DataFrame({
            "open": arr[:, 1] / point,
            "high": arr[:, 4] / point,
            "low": arr[:, 3] / point,
            "close": arr[:, 2] / point,
            "volume": vol.astype("float64"),
        }, index=pd.DatetimeIndex(idx, tz="UTC", name="time"))
        return df

    # -- public --------------------------------------------------------
    def candles(self, symbol: str, timeframe: str, start: str | date, end: str | date,
                side: str = "BID") -> pd.DataFrame:
        """Return candles for [start, end) in UTC. timeframe: '1m', '1h' or '1d'."""
        symbol = symbol.upper().replace("/", "")
        point = POINT.get(symbol, 1000.0)
        start_d = pd.Timestamp(start).date()
        end_d = pd.Timestamp(end).date()
        frames = []
        if timeframe == "1m":
            units = [start_d + timedelta(days=k) for k in range((end_d - start_d).days)]
            units = [d for d in units if d.weekday() != 5]  # Saturday files are empty
            for k, d in enumerate(units):
                rel = f"{symbol}/{d.year}/{d.month - 1:02d}/{d.day:02d}/{side}_candles_min_1.bi5"
                self._progress(k, len(units), rel)
                recent = (date.today() - d).days < 3
                frames.append(self._decode(self._fetch(rel, recent), datetime(d.year, d.month, d.day), point))
        elif timeframe == "1h":
            m = date(start_d.year, start_d.month, 1)
            months = []
            while m < end_d:
                months.append(m)
                m = date(m.year + (m.month == 12), m.month % 12 + 1, 1)
            this_month = date.today().replace(day=1)
            for k, m in enumerate(months):
                if m >= this_month:
                    # The current month's hourly file appears only after the month ends:
                    # build it from daily 1-minute files instead.
                    from .resample import resample
                    mm = self.candles(symbol, "1m", max(m, start_d), end_d, side)
                    if len(mm):
                        frames.append(resample(mm, "1h"))
                    continue
                rel = f"{symbol}/{m.year}/{m.month - 1:02d}/{side}_candles_hour_1.bi5"
                self._progress(k, len(months), rel)
                frames.append(self._decode(self._fetch(rel), datetime(m.year, m.month, 1), point))
        elif timeframe == "1d":
            for k, y in enumerate(range(start_d.year, end_d.year + 1)):
                rel = f"{symbol}/{y}/{side}_candles_day_1.bi5"
                frames.append(self._decode(self._fetch(rel, y == date.today().year), datetime(y, 1, 1), point))
        else:
            raise ValueError("Dukascopy timeframe must be 1m, 1h or 1d (resample for others)")
        frames = [f for f in frames if len(f)]
        if not frames:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        df = pd.concat(frames)
        df = df[~df.index.duplicated()].sort_index()
        df = df[(df.index >= pd.Timestamp(start_d, tz="UTC")) & (df.index < pd.Timestamp(end_d, tz="UTC"))]
        # Dukascopy pads closed-market minutes/hours with flat zero-volume bars.
        flat = (df["volume"] <= 0) & (df["high"] == df["low"])
        return df[~flat]

    def bid_ask(self, symbol: str, timeframe: str, start, end) -> pd.DataFrame:
        """Bid OHLC plus an ask_close / spread column. Chart prices are bid, like most FX feeds."""
        bid = self.candles(symbol, timeframe, start, end, "BID")
        ask = self.candles(symbol, timeframe, start, end, "ASK")
        df = bid.copy()
        ask = ask.reindex(df.index)
        spread = ((ask["open"] - bid["open"]) + (ask["close"] - bid["close"])) / 2
        df["spread"] = spread.clip(lower=0).ffill().fillna(0.0)
        return df

    def _progress(self, k: int, n: int, rel: str) -> None:
        if self.verbose and n > 20 and (k % 25 == 0 or k == n - 1):
            print(f"  dukascopy {k + 1}/{n} {rel}", flush=True)


def load(symbol: str = "XAUUSD", timeframe: str = "1h", start="2024-01-01", end=None,
         with_spread: bool = True, cache_dir: Path | str = DEFAULT_CACHE, verbose: bool = True) -> pd.DataFrame:
    """Convenience loader. Any timeframe; non-native ones are resampled from 1m or 1h."""
    from .resample import resample, NATIVE_SOURCE

    end = end or (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()
    client = DukascopyClient(cache_dir=cache_dir, verbose=verbose)
    src = NATIVE_SOURCE.get(timeframe)
    if src is None:
        raise ValueError(f"Unsupported timeframe {timeframe}")
    df = client.bid_ask(symbol, src, start, end) if with_spread else client.candles(symbol, src, start, end)
    if src != timeframe:
        df = resample(df, timeframe)
    df.attrs.update({"symbol": symbol, "timeframe": timeframe, "source": "dukascopy",
                     "price_side": "bid", "start": str(start), "end": str(end)})
    return df
