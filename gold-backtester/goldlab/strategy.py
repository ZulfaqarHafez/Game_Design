"""Strategy base class with a Pine-Script-like API.

Write a strategy by subclassing Strategy:

    class EmaCross(Strategy):
        name = "EMA cross"
        params = {"fast": 20, "slow": 50, "atr_mult": 2.0}

        def init(self):
            self.fast = ta.ema(self.data.close, self.p.fast)
            self.slow = ta.ema(self.data.close, self.p.slow)
            self.atr = ta.atr(self.data.high, self.data.low, self.data.close, 14)

        def next(self, i):
            if ta_cross_up(...):
                self.entry("L", "long", sl_dist=self.p.atr_mult * self.atr[i])

`init` runs once with the whole DataFrame (precompute indicators there).
`next(i)` runs at the close of every bar, exactly like a Pine script.
Orders placed in next(i) fill on bar i+1 (see engine/broker.py).
"""
from __future__ import annotations

import hashlib
import inspect
from types import SimpleNamespace

import numpy as np
import pandas as pd

from .engine.broker import LONG, SHORT, Broker


def _side(direction) -> int:
    if direction in (1, "long", "buy", LONG):
        return LONG
    if direction in (-1, "short", "sell", SHORT):
        return SHORT
    raise ValueError(f"direction must be long/short, got {direction!r}")


class Strategy:
    name: str = "Unnamed strategy"
    description: str = ""
    timeframe: str | None = None       # suggested timeframe
    params: dict = {}

    def __init__(self, **params):
        unknown = set(params) - set(self.params)
        if unknown:
            raise ValueError(f"Unknown params for {self.name}: {sorted(unknown)}")
        self.p = SimpleNamespace(**{**self.params, **params})
        self.broker: Broker | None = None
        self.data: pd.DataFrame | None = None
        self.plots: dict[str, pd.Series] = {}

    # -- hooks ---------------------------------------------------------
    def init(self) -> None:
        pass

    def next(self, i: int) -> None:
        raise NotImplementedError

    # -- identity (used by the journal) --------------------------------
    def source(self) -> str:
        try:
            return inspect.getsource(type(self))
        except (OSError, TypeError):
            return repr(type(self))

    def fingerprint(self) -> str:
        return hashlib.sha256(self.source().encode()).hexdigest()[:12]

    def spec(self) -> dict:
        return {"name": self.name, "kind": "python", "class": type(self).__name__,
                "params": vars(self.p), "description": self.description}

    # -- data accessors --------------------------------------------------
    def _bind(self, data: pd.DataFrame, broker: Broker) -> None:
        self.data = data
        self.broker = broker
        self.open = data["open"].to_numpy(float)
        self.high = data["high"].to_numpy(float)
        self.low = data["low"].to_numpy(float)
        self.close = data["close"].to_numpy(float)
        self.time = data.index

    def plot(self, name: str, series) -> None:
        """Ask the HTML report to draw a line (e.g. an EMA) over the candles."""
        self.plots[name] = series if isinstance(series, pd.Series) else pd.Series(series, index=self.data.index)

    @property
    def position_size(self) -> float:
        """Signed units: >0 long, <0 short, 0 flat (strategy.position_size)."""
        return self.broker.position

    @property
    def position_avg_price(self) -> float:
        return self.broker.position_avg_price

    @property
    def equity(self) -> float:
        b = self.broker
        return b.equity_at(self.close[b.bar], b.spread[b.bar])

    @property
    def open_trades(self) -> int:
        return len(self.broker.trades)

    # -- orders (Pine: strategy.entry / exit / close / cancel) ---------
    def entry(self, id: str, direction, qty: float | None = None, lots: float | None = None,
              limit: float | None = None, stop: float | None = None,
              sl: float | None = None, tp: float | None = None,
              sl_dist: float | None = None, tp_dist: float | None = None,
              trail_offset: float | None = None, trail_trigger_dist: float | None = None,
              comment: str = "", oca: str | None = None) -> None:
        """Place an entry. Opposite positions are reversed, like strategy.entry.

        sl/tp are absolute prices; sl_dist/tp_dist are distances from the actual
        fill price (like strategy.exit's loss=/profit= but in price, not ticks).
        Sizing follows Settings.qty_type unless qty (units) or lots is given; with
        qty_type="risk_percent" the stop distance sets the size.
        """
        side = _side(direction)
        b = self.broker
        # TradingView sizes cash / %-of-equity orders off the signal bar's close.
        px = stop if stop is not None else (limit if limit is not None else self.close[b.bar])
        risk = sl_dist if sl_dist is not None else (abs(px - sl) if sl is not None else None)
        if risk is not None and not np.isfinite(risk):
            return
        q = b.size(side, self.close[b.bar], qty=qty, lots=lots, risk_dist=risk)
        bracket = {}
        if sl is not None:
            bracket["stop"] = sl
        if tp is not None:
            bracket["limit"] = tp
        if sl_dist is not None:
            bracket["loss_dist"] = sl_dist
        if tp_dist is not None:
            bracket["profit_dist"] = tp_dist
        if trail_offset is not None:
            bracket["trail_offset"] = trail_offset
            bracket["trail_trigger_dist"] = trail_trigger_dist
        if any(v is not None and not np.isfinite(v) for v in bracket.values() if isinstance(v, float)):
            return  # an indicator was still warming up
        b.entry(id, side, q, limit=limit, stop=stop, comment=comment, oca=oca, bracket=bracket or None)

    def exit(self, id: str, from_entry: str | None = None, stop: float | None = None,
             limit: float | None = None, loss_dist: float | None = None, profit_dist: float | None = None,
             trail_offset: float | None = None, trail_trigger_dist: float | None = None,
             qty_percent: float = 100.0, comment: str = "") -> None:
        self.broker.exit(id, from_entry, stop=stop, limit=limit, loss_dist=loss_dist, profit_dist=profit_dist,
                         trail_offset=trail_offset, trail_trigger_dist=trail_trigger_dist,
                         qty_percent=qty_percent, comment=comment)

    def close_position(self, id: str | None = None, comment: str = "", qty_percent: float = 100.0) -> None:
        self.broker.close(id, comment, qty_percent)

    def cancel(self, id: str) -> None:
        self.broker.cancel(id)

    def cancel_all(self) -> None:
        self.broker.cancel_all()
