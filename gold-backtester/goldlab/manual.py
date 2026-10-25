"""Manual trades from bar replay, re-run through the backtest engine.

In replay you see a bar close and decide: buy, sell, close, or move a stop. Each
decision is stored with that bar's time. ManualStrategy places the same orders at
the same bars with process_orders_on_close, so fills, stops, targets, spread,
commission, slippage and swap follow exactly the rules every backtest uses.

A session file (exported from the website) looks like:

    {"format": "goldlab-replay-session", "timeframe": "1h", "preset": "realistic",
     "settings": {"initial_capital": 10000, ...}, "start_time": 1735689600, "current_time": 1738368000,
     "trades": [{"id": "M1", "side": "long", "lots": 0.1, "entry_time": 1735776000,
                 "sl": 2601.5, "tp": 2650.0, "exit_time": 1735862400, "exit_by": "TP",
                 "note": "pullback to the 20 EMA", "mods": [{"time": 1735790400, "sl": 2610.0, "tp": 2650.0}]}]}

exit_time is only needed for trades you closed by hand; stop and target exits happen
by themselves when the engine replays the bars.
"""
from __future__ import annotations

import math

import pandas as pd

from .strategy import Strategy

MAX_TRADES = 500
MAX_MODS = 60


class ManualError(ValueError):
    pass


def _price(v, what: str):
    if v is None or v == "":
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        raise ManualError(f"{what} must be a number") from None
    if not math.isfinite(v) or v <= 0 or v > 1e7:
        raise ManualError(f"{what} must be a positive price")
    return v


def clean_trades(trades) -> list[dict]:
    """Validate trades sent by the browser (or read from a session file)."""
    if not isinstance(trades, list):
        raise ManualError("trades must be a list")
    if len(trades) > MAX_TRADES:
        raise ManualError(f"At most {MAX_TRADES} trades per session")
    out = []
    for k, t in enumerate(trades):
        if not isinstance(t, dict):
            raise ManualError("Each trade must be an object")
        side = t.get("side")
        if side not in ("long", "short"):
            raise ManualError("side must be long or short")
        try:
            lots = float(t.get("lots"))
        except (TypeError, ValueError):
            raise ManualError("lots must be a number") from None
        if not (0.01 <= lots <= 100) or not math.isfinite(lots):
            raise ManualError("lots must be between 0.01 and 100")
        try:
            entry = int(t["entry_time"])
        except (KeyError, TypeError, ValueError):
            raise ManualError("entry_time must be a unix time in seconds") from None
        exit_t = t.get("exit_time")
        exit_t = int(exit_t) if exit_t not in (None, "") else None
        mods = t.get("mods") or []
        if not isinstance(mods, list) or len(mods) > MAX_MODS:
            raise ManualError(f"mods must be a list of at most {MAX_MODS} changes")
        clean_mods = []
        for m in mods:
            if not isinstance(m, dict):
                raise ManualError("Each stop/target change must be an object")
            clean_mods.append({"time": int(m["time"]), "sl": _price(m.get("sl"), "Stop loss"),
                               "tp": _price(m.get("tp"), "Take profit")})
        out.append({
            "id": f"M{k + 1}", "side": side, "lots": round(lots, 2), "entry_time": entry,
            "sl": _price(t.get("sl"), "Stop loss"), "tp": _price(t.get("tp"), "Take profit"),
            "exit_time": exit_t, "exit_by": str(t.get("exit_by") or "")[:12],
            "note": str(t.get("note") or "")[:300], "mods": clean_mods,
            "entry_price": _price(t.get("entry_price"), "Entry price"),
        })
    return out


class ManualStrategy(Strategy):
    """Places recorded manual orders at the bars they were made on."""
    name = "Replay session"
    description = "Trades you placed by hand in bar replay."
    params: dict = {}
    card: dict = {}

    def __init__(self, trades: list[dict], name: str | None = None):
        super().__init__()
        self.manual = trades
        if name:
            self.name = name

    def source(self) -> str:
        return repr([(t["side"], t["lots"], t["entry_time"], t["sl"], t["tp"], t["exit_time"], t["mods"])
                     for t in self.manual])

    def init(self):
        secs = self.data.index.as_unit("s").asi8
        where = {int(s): i for i, s in enumerate(secs)}
        self.actions: dict[int, list] = {}

        def at(ts, what):
            if ts not in where:
                raise ManualError(f"{what} time {pd.Timestamp(ts, unit='s', tz='UTC')} is not a bar on this timeframe")
            return where[ts]

        for t in self.manual:
            i = at(t["entry_time"], "Entry")
            self.actions.setdefault(i, []).append((2, "open", t))
            for m in t["mods"]:
                self.actions.setdefault(at(m["time"], "Stop/target change"), []).append((0, "modify", t, m))
            if t["exit_time"] is not None and t["exit_by"].lower() in ("close", "manual", ""):
                j = at(t["exit_time"], "Exit")
                self.actions.setdefault(j, []).append((1, "close", t))
        for v in self.actions.values():
            v.sort(key=lambda a: a[0])   # changes, then closes, then new entries on the same bar

    def next(self, i: int):
        for a in self.actions.get(i, []):
            kind, t = a[1], a[2]
            if kind == "modify":
                if any(tr.entry_id == t["id"] for tr in self.broker.trades):
                    m = a[3]
                    self.exit(f"{t['id']} exit", t["id"], stop=m["sl"], limit=m["tp"])
            elif kind == "close":
                self.close_position(t["id"], "Close")
            else:
                self.entry(t["id"], t["side"], lots=t["lots"], sl=t["sl"], tp=t["tp"], comment=t["note"][:80])
