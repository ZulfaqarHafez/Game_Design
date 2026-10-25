"""Pre-trade risk checks. Every new order passes through RiskGuard.check().

Defaults are deliberately small. Raise them in live.yaml only after weeks of
paper trading that matches the backtest.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml


@dataclass
class RiskConfig:
    max_lots: float = 0.10                 # largest position allowed (lots of 100 oz)
    max_order_lots: float = 0.10
    max_daily_loss_usd: float = 200.0      # stop trading for the day after losing this much (equity based)
    max_orders_per_day: int = 10
    max_spread: float = 1.00               # USD per oz; skip entries when the spread is wider
    trade_window_utc: str = "00:00-24:00"  # entries only inside this window
    blackout_file: str | None = "news_blackout.yaml"   # list of high-impact events to avoid
    blackout_minutes_before: int = 15
    blackout_minutes_after: int = 15
    kill_switch_file: str = "KILL"         # create this file to stop all new orders and flatten
    require_stop_loss: bool = True         # every entry must carry a broker-side stop
    max_price_deviation: float = 0.005     # market orders: reject if >0.5% away from the last price


@dataclass
class RiskState:
    day: str = ""
    start_equity: float = 0.0
    orders_today: int = 0
    halted: bool = False
    reasons: list = field(default_factory=list)


class RiskGuard:
    def __init__(self, cfg: RiskConfig, state_path: Path, root: Path):
        self.cfg = cfg
        self.root = root
        self.path = state_path
        self.state = RiskState(**json.loads(state_path.read_text())) if state_path.exists() else RiskState()

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.state.__dict__, indent=2))

    def _roll_day(self, equity: float, now: datetime):
        # trading day rolls at 17:00 New York, like the market
        day = str((pd.Timestamp(now).tz_convert("America/New_York") + pd.Timedelta(hours=7)).date())
        if day != self.state.day:
            self.state = RiskState(day=day, start_equity=equity)
            self.save()

    def kill_switch(self) -> bool:
        return (self.root / self.cfg.kill_switch_file).exists()

    def daily_loss_hit(self, equity: float, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        self._roll_day(equity, now)
        return self.state.start_equity - equity >= self.cfg.max_daily_loss_usd

    def in_blackout(self, now: datetime) -> str | None:
        if not self.cfg.blackout_file:
            return None
        f = self.root / self.cfg.blackout_file
        if not f.exists():
            return None
        events = yaml.safe_load(f.read_text()) or []
        t = pd.Timestamp(now)
        for ev in events:
            at = pd.Timestamp(ev["time"])
            at = at.tz_localize("UTC") if at.tz is None else at.tz_convert("UTC")
            if at - pd.Timedelta(minutes=self.cfg.blackout_minutes_before) <= t <= at + pd.Timedelta(minutes=self.cfg.blackout_minutes_after):
                return ev.get("name", "news event")
        return None

    def _in_window(self, now: datetime) -> bool:
        a, b = self.cfg.trade_window_utc.split("-")
        m = now.hour * 60 + now.minute
        s = int(a[:2]) * 60 + int(a[3:5])
        e = int(b[:2]) * 60 + int(b[3:5])
        return s <= m < e if s < e else (m >= s or m < e)

    def check(self, *, side: int, qty: float, price: float, stop: float | None, equity: float,
              position_qty: float, spread: float, market: float, now: datetime | None = None,
              kind: str = "market") -> list[str]:
        """Return a list of reasons to block this NEW-RISK order (empty list = allowed)."""
        now = now or datetime.now(timezone.utc)
        c = self.cfg
        why = []
        if self.kill_switch():
            why.append(f"kill switch file '{c.kill_switch_file}' exists")
        if self.daily_loss_hit(equity, now):
            why.append(f"daily loss limit ${c.max_daily_loss_usd:,.0f} reached")
        if self.state.orders_today >= c.max_orders_per_day:
            why.append(f"{c.max_orders_per_day} orders already sent today")
        lots = qty / 100
        if lots > c.max_order_lots + 1e-9:
            why.append(f"order {lots:.2f} lots > max {c.max_order_lots:.2f}")
        if (position_qty + qty) / 100 > c.max_lots + 1e-9:
            why.append(f"position would be {(position_qty + qty) / 100:.2f} lots > max {c.max_lots:.2f}")
        if spread > c.max_spread:
            why.append(f"spread ${spread:.2f} > max ${c.max_spread:.2f}")
        if not self._in_window(now):
            why.append(f"outside trading window {c.trade_window_utc} UTC")
        ev = self.in_blackout(now)
        if ev:
            why.append(f"news blackout: {ev}")
        if c.require_stop_loss and stop is None:
            why.append("no stop loss on the order")
        if kind == "market" and market and abs(price - market) / market > c.max_price_deviation:
            why.append(f"order price {price:.2f} is too far from market {market:.2f}")
        return why

    def record_order(self):
        self.state.orders_today += 1
        self.save()
