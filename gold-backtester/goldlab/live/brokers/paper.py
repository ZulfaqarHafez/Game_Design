"""A paper broker: simulated account, real (or replayed) prices.

Fills are simulated on each newly closed bar with the same pessimistic rule
a careful broker test would use: if a bar touches both the stop and the
target, the stop is assumed to fill first. State is saved to JSON so a
restart resumes the same paper account.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import pandas as pd

from .base import BrokerAdapter, PendingOrder, Position


class PaperBroker(BrokerAdapter):
    name = "paper"

    def __init__(self, feed: Callable[[str, int], pd.DataFrame], state_path: Path, initial_equity: float = 10_000.0,
                 commission_per_lot: float = 3.5, slippage: float = 0.05, default_spread: float = 0.35):
        self.feed = feed
        self.path = Path(state_path)
        self.commission_per_lot = commission_per_lot
        self.slippage = slippage
        self.default_spread = default_spread
        if self.path.exists():
            self.st = json.loads(self.path.read_text())
        else:
            self.st = {"cash": initial_equity, "side": 0, "qty": 0.0, "avg": 0.0, "stop": None, "tp": None,
                       "pending": [], "fills": [], "last_bar": None, "seq": 0, "client_ids": []}
        self._last = None

    # -- persistence ------------------------------------------------------
    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.st, indent=2, default=str))

    # -- data ---------------------------------------------------------------
    def candles(self, timeframe: str, count: int = 1500) -> pd.DataFrame:
        df = self.feed(timeframe, count)
        self._last = df
        return df

    def quote(self):
        df = self._last if self._last is not None else self.feed("1m", 5)
        bid = float(df["close"].iloc[-1])
        sp = float(df["spread"].iloc[-1]) if "spread" in df and pd.notna(df["spread"].iloc[-1]) else self.default_spread
        return bid, bid + sp

    # -- account ------------------------------------------------------------
    def equity(self) -> float:
        bid, ask = self.quote()
        s = self.st
        if s["side"] == 0:
            return s["cash"]
        mark = bid if s["side"] > 0 else ask
        return s["cash"] + s["side"] * (mark - s["avg"]) * s["qty"]

    def position(self) -> Position:
        s = self.st
        return Position(s["side"], s["qty"], s["avg"], s["stop"], s["tp"])

    def pending_orders(self) -> list[PendingOrder]:
        return [PendingOrder(**{k: v for k, v in p.items() if k in PendingOrder.__dataclass_fields__})
                for p in self.st["pending"]]

    # -- internals ------------------------------------------------------------
    def _fill(self, side: int, qty: float, price: float, reason: str, client_id: str, time=None):
        s = self.st
        fee = qty / 100 * self.commission_per_lot
        s["cash"] -= fee
        if s["side"] == 0 or s["side"] == side:
            new_qty = s["qty"] + qty
            s["avg"] = (s["avg"] * s["qty"] + price * qty) / new_qty
            s["qty"], s["side"] = new_qty, side
        else:
            closing = min(qty, s["qty"])
            s["cash"] += s["side"] * (price - s["avg"]) * closing
            s["qty"] -= closing
            rest = qty - closing
            if s["qty"] <= 1e-9:
                s["side"], s["qty"], s["avg"], s["stop"], s["tp"] = 0, 0.0, 0.0, None, None
            if rest > 1e-9:
                s["side"], s["qty"], s["avg"] = side, rest, price
        s["fills"].append({"time": str(time or pd.Timestamp.now(tz="UTC")), "side": side, "qty": qty,
                           "price": round(price, 3), "reason": reason, "client_id": client_id,
                           "cash": round(s["cash"], 2)})
        self._save()

    def on_bars(self, bars: pd.DataFrame):
        """Simulate what resting orders did during bars that closed since the last call."""
        s = self.st
        new = bars if s["last_bar"] is None else bars[bars.index > pd.Timestamp(s["last_bar"])]
        if s["last_bar"] is None and len(bars):
            s["last_bar"] = str(bars.index[-1])
            self._save()
            return
        for t, b in new.iterrows():
            sp = float(b["spread"]) if "spread" in b and pd.notna(b["spread"]) else self.default_spread
            o, h, l, c = float(b["open"]), float(b["high"]), float(b["low"]), float(b["close"])
            # same in-bar path assumption as the backtest engine (TradingView's rule)
            path = [o, h, l, c] if (h - o) <= (o - l) else [o, l, h, c]
            self._walk(path, sp, t)
            s["last_bar"] = str(t)
        self._save()

    def _triggers(self, sp):
        """(direction, threshold on the bid, kind, payload). direction +1 fires when the bid rises to it."""
        s = self.st
        out = []
        for p in s["pending"]:
            thr = p["price"] - (sp if p["side"] > 0 else 0)
            rising = (p["type"] == "stop") == (p["side"] > 0)
            out.append((1 if rising else -1, thr, "entry", p))
        if s["side"] != 0:
            side = s["side"]
            off = 0 if side > 0 else sp           # longs exit on the bid, shorts on the ask
            if s["stop"] is not None:
                out.append((-1 if side > 0 else 1, s["stop"] - off, "stop", None))
            if s["tp"] is not None:
                out.append((1 if side > 0 else -1, s["tp"] - off, "tp", None))
        return out

    def _fire(self, kind, p, level, bid, sp, t, gap):
        s = self.st
        if kind == "entry":
            ask = bid + sp
            if gap:
                px = (ask if p["side"] > 0 else bid)
            else:
                px = p["price"]
            if p["type"] == "stop":
                px += p["side"] * self.slippage
            s["pending"].remove(p)
            self._fill(p["side"], p["qty"], px, f"{p['type']} entry", p["client_id"], t)
            s["stop"], s["tp"] = p.get("stop"), p.get("take_profit")
            self._save()
        else:
            side = s["side"]
            px = (bid if side > 0 else bid + sp) if gap else (s["stop"] if kind == "stop" else s["tp"])
            if kind == "stop":
                px -= side * self.slippage
            self._fill(-side, s["qty"], px, "stop loss" if kind == "stop" else "take profit",
                       "broker-stop" if kind == "stop" else "broker-tp", t)

    def _walk(self, path, sp, t):
        cur = path[0]
        for _ in range(20):  # gaps: anything already through its level fills at the open
            hit = [x for x in self._triggers(sp) if (x[0] > 0 and cur >= x[1]) or (x[0] < 0 and cur <= x[1])]
            if not hit:
                break
            hit.sort(key=lambda x: 0 if x[2] != "entry" else 1)
            self._fire(hit[0][2], hit[0][3], hit[0][1], cur, sp, t, gap=True)
        for nxt in path[1:]:
            for _ in range(20):
                trig = self._triggers(sp)
                if nxt > cur:
                    c = [x for x in trig if x[0] > 0 and cur < x[1] <= nxt]
                    best = min(c, key=lambda x: x[1]) if c else None
                else:
                    c = [x for x in trig if x[0] < 0 and nxt <= x[1] < cur]
                    best = max(c, key=lambda x: x[1]) if c else None
                if best is None:
                    break
                self._fire(best[2], best[3], best[1], best[1], sp, t, gap=False)
                cur = best[1]
            cur = nxt

    # -- orders ---------------------------------------------------------------
    def market_order(self, side, qty, client_id, stop=None, take_profit=None):
        if client_id in self.st["client_ids"]:
            return {"status": "duplicate", "client_id": client_id}
        bid, ask = self.quote()
        px = (ask if side > 0 else bid) + side * self.slippage
        self.st["client_ids"].append(client_id)
        self._fill(side, qty, px, "market", client_id, self._last.index[-1] if self._last is not None else None)
        if self.st["side"] == side:
            self.st["stop"], self.st["tp"] = stop, take_profit
        self._save()
        return {"status": "filled", "price": px, "client_id": client_id}

    def pending_order(self, side, qty, type, price, client_id, stop=None, take_profit=None):
        self.st["seq"] += 1
        self.st["pending"].append({"id": f"P{self.st['seq']}", "client_id": client_id, "side": side, "type": type,
                                   "qty": qty, "price": price, "stop": stop, "take_profit": take_profit})
        self._save()
        return {"status": "placed", "client_id": client_id}

    def cancel(self, order: PendingOrder):
        self.st["pending"] = [p for p in self.st["pending"] if p["id"] != order.id]
        self._save()

    def set_protection(self, stop, take_profit):
        self.st["stop"], self.st["tp"] = stop, take_profit
        self._save()

    def close_position(self, client_id):
        s = self.st
        if s["side"] == 0:
            return {"status": "flat"}
        bid, ask = self.quote()
        px = (bid if s["side"] > 0 else ask) - s["side"] * self.slippage
        self._fill(-s["side"], s["qty"], px, "close", client_id, self._last.index[-1] if self._last is not None else None)
        return {"status": "closed", "price": px}

    def find_client_order(self, client_id):
        return {"client_id": client_id} if client_id in self.st["client_ids"] else None


class ReplayFeed:
    """Reveals historical bars one at a time, to rehearse the live loop offline."""

    def __init__(self, bars: pd.DataFrame, start: int):
        self.bars = bars
        self.i = start

    def __call__(self, timeframe: str, count: int) -> pd.DataFrame:
        return self.bars.iloc[max(0, self.i - count): self.i]

    def advance(self) -> bool:
        if self.i >= len(self.bars):
            return False
        self.i += 1
        return True
