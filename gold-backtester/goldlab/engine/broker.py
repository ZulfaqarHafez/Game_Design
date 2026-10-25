"""A broker emulator that follows TradingView's Strategy Tester rules.

How TradingView simulates fills on historical bars (Pine Script docs,
"Strategies" page), and how this module copies it:

* The script runs once at the close of each bar. Orders it places are
  filled on the NEXT bar. Market orders fill at that bar's open (or at the
  current close when process_orders_on_close=True).
* Inside a bar the emulator only knows OHLC, so it assumes a price path:
  if the high is nearer the open than the low, price went open->high->low->close,
  otherwise open->low->high->close. Stop and limit orders (entries, stop
  losses, take profits, trailing stops) fill in the order the path touches them.
* An order that is already through its price at the open (a gap) fills at the open.
* Slippage (in ticks) is added to market and stop fills, never to limit fills.
* Bar magnifier: pass lower-timeframe bars and the path is built from them instead.

Extra realism that TradingView does not do by default:
* spread: chart prices are treated as BID. Buys fill on the ask (bid + spread),
  long stops/targets trigger on the bid, short stops/targets on the ask.
  Use spread_mode="none" for TradingView-identical results.
* margin: positions need margin_percent of notional; a margin call closes
  the position if equity at the worst intrabar price can't cover it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

LONG, SHORT = 1, -1


@dataclass
class Settings:
    initial_capital: float = 10_000.0
    currency: str = "USD"
    # position sizing ------------------------------------------------
    qty_type: str = "lots"           # lots | units | cash | percent_of_equity | risk_percent
    qty_value: float = 0.1           # meaning depends on qty_type
    contract_size: float = 100.0     # ounces per lot for XAUUSD
    qty_step: float = 1.0            # smallest tradeable units (1 oz = 0.01 lot)
    min_qty: float = 1.0
    max_qty: float | None = None
    pyramiding: int = 1              # max open entries in one direction (TradingView 0 == 1)
    point_value: float = 1.0         # USD per 1.00 price move per unit (1 oz)
    mintick: float = 0.01
    # costs ----------------------------------------------------------
    commission_type: str = "cash_per_lot"  # percent | cash_per_contract | cash_per_order | cash_per_lot
    commission_value: float = 0.0          # charged on every fill (entry and exit)
    slippage_ticks: int = 0
    spread_mode: str = "data"              # none | fixed | data
    spread_fixed: float = 0.0              # price units, used when spread_mode == "fixed"
    swap_long: float = 0.0                 # USD per lot per night held long (negative = you pay)
    swap_short: float = 0.0                # USD per lot per night held short
    swap_triple_weekday: int = 2           # Wednesday rollover is charged x3 (covers the weekend)
    # behaviour ------------------------------------------------------
    process_orders_on_close: bool = False
    limit_fill_ticks: int = 0              # TradingView backtest_fill_limits_assumption
    margin_percent: float | None = 5.0     # 5% = 1:20 leverage; None disables margin checks
    close_entries_rule: str = "FIFO"
    close_open_at_end: bool = False
    intrabar: str = "tv"                   # tv | pessimistic (adverse extreme first for open positions)

    @classmethod
    def tradingview(cls, **kw) -> "Settings":
        """Defaults that reproduce a plain TradingView strategy() as closely as possible."""
        base = dict(spread_mode="none", commission_value=0.0, slippage_ticks=0,
                    qty_type="units", qty_value=1.0, margin_percent=100.0)
        base.update(kw)
        return cls(**base)

    @classmethod
    def realistic(cls, **kw) -> "Settings":
        """Retail XAUUSD CFD-like costs (2026 research): real bid/ask spread, $7 per lot round
        turn commission, $0.05 slippage, overnight swap -$40/lot long, -$5/lot short (x3 Wednesday)."""
        base = dict(spread_mode="data", commission_type="cash_per_lot", commission_value=3.5,
                    slippage_ticks=5, margin_percent=5.0, swap_long=-40.0, swap_short=-5.0)
        base.update(kw)
        return cls(**base)


@dataclass
class EntryOrder:
    id: str
    side: int
    type: str                      # market | limit | stop | stop_limit
    qty: float
    limit: float | None = None
    stop: float | None = None
    bar: int = 0
    comment: str = ""
    oca: str | None = None
    stop_hit: bool = False
    bracket: dict | None = None    # sl/tp attached at fill


@dataclass
class ExitOrder:
    id: str
    from_entry: str | None
    stop: float | None = None
    limit: float | None = None
    loss_dist: float | None = None
    profit_dist: float | None = None
    trail_trigger_dist: float | None = None   # activate trailing once in profit by this much
    trail_offset: float | None = None         # trail this far behind the best price
    trail_price: float | None = None          # absolute activation price
    qty_percent: float = 100.0
    comment: str = ""
    attached: set = field(default_factory=set)
    done: set = field(default_factory=set)


@dataclass
class CloseOrder:
    entry_id: str | None           # None closes everything
    comment: str = ""
    qty_percent: float = 100.0


@dataclass
class Trade:
    tid: int
    entry_id: str
    side: int
    qty: float
    entry_price: float
    entry_bar: int
    entry_time: Any
    entry_comment: str
    entry_commission: float
    best: float          # most favourable price seen
    worst: float         # most adverse price seen
    trail_active: dict = field(default_factory=dict)  # exit id -> watermark


class Broker:
    def __init__(self, data: pd.DataFrame, settings: Settings, magnifier: pd.DataFrame | None = None):
        self.s = settings
        self.data = data
        self.n = len(data)
        self.time = data.index
        self.o = data["open"].to_numpy(float)
        self.h = data["high"].to_numpy(float)
        self.l = data["low"].to_numpy(float)
        self.c = data["close"].to_numpy(float)
        if settings.spread_mode == "data" and "spread" in data:
            self.spread = data["spread"].fillna(0).to_numpy(float)
        elif settings.spread_mode == "fixed":
            self.spread = np.full(self.n, settings.spread_fixed)
        else:
            self.spread = np.zeros(self.n)
        self.sub_paths = self._magnifier_paths(magnifier) if magnifier is not None else None
        # FX day rolls at 17:00 New York; bars that start a new trading day trigger swap.
        ny = self.time.tz_convert("America/New_York") if self.time.tz is not None else self.time
        day = (ny + pd.Timedelta(hours=7)).normalize()
        roll = np.zeros(self.n, dtype=int)
        if self.n:
            dd = np.asarray((day.values[1:] - day.values[:-1]).astype("timedelta64[D]").astype(int))
            roll[1:] = dd
            prev_wd = np.asarray(pd.DatetimeIndex(day[:-1]).weekday)
            # rolling through Wednesday's close (into Thursday) is charged triple
            triple = (prev_wd == settings.swap_triple_weekday)
            roll[1:] = np.where(dd > 0, np.where(triple, 3, np.minimum(dd, 1)), 0)
        self.rollovers = roll
        self.total_swap = 0.0

        self.cash = settings.initial_capital      # realized equity
        self.trades: list[Trade] = []             # open trades
        self.closed: list[dict] = []
        self.entries: dict[str, EntryOrder] = {}
        self.exits: dict[str, ExitOrder] = {}
        self.closes: list[CloseOrder] = []
        self.events: list[dict] = []
        self.placed: list[tuple] = []             # every order the strategy placed: (bar, kind, id, ...)
        self._last_reject: dict[str, int] = {}
        self._tid = 0
        self.bar = -1
        self.cur_spread = 0.0
        self.equity_close = np.full(self.n, np.nan)
        self.equity_low = np.full(self.n, np.nan)
        self.equity_high = np.full(self.n, np.nan)
        self.pos_size = np.zeros(self.n)
        self.realized = np.full(self.n, np.nan)   # initial capital + net P&L of closed trades
        self.realized_pnl = 0.0
        self.total_commission = 0.0

    # ------------------------------------------------------------------
    # state helpers
    # ------------------------------------------------------------------
    @property
    def position(self) -> float:
        return sum(t.side * t.qty for t in self.trades)

    @property
    def position_avg_price(self) -> float:
        q = sum(t.qty for t in self.trades)
        return sum(t.entry_price * t.qty for t in self.trades) / q if q else float("nan")

    def open_profit(self, bid: float, spread: float) -> float:
        pv = self.s.point_value
        out = 0.0
        for t in self.trades:
            mark = bid if t.side == LONG else bid + spread
            out += t.side * (mark - t.entry_price) * t.qty * pv
        return out

    def equity_at(self, bid: float, spread: float) -> float:
        return self.cash + self.open_profit(bid, spread)

    def _round_qty(self, q: float) -> float:
        step = self.s.qty_step
        q = math.floor(q / step + 1e-9) * step
        if self.s.max_qty is not None:
            q = min(q, self.s.max_qty)
        return round(q, 8)

    def _commission(self, qty: float, price: float) -> float:
        s = self.s
        v = s.commission_value
        if not v:
            return 0.0
        if s.commission_type == "percent":
            return qty * price * s.point_value * v / 100
        if s.commission_type == "cash_per_contract":
            return qty * v
        if s.commission_type == "cash_per_lot":
            return qty / s.contract_size * v
        if s.commission_type == "cash_per_order":
            return v
        raise ValueError(f"unknown commission_type {s.commission_type}")

    def size(self, side: int, ref_price: float, qty: float | None = None, lots: float | None = None,
             risk_dist: float | None = None) -> float:
        """Turn the sizing settings into units (ounces)."""
        s = self.s
        if lots is not None:
            q = lots * s.contract_size
        elif qty is not None:
            q = qty
        else:
            eq = self.equity_at(self.c[self.bar], self.spread[self.bar]) if self.bar >= 0 else s.initial_capital
            t, v = s.qty_type, s.qty_value
            if t == "lots":
                q = v * s.contract_size
            elif t == "units":
                q = v
            elif t == "cash":
                q = v / (ref_price * s.point_value)
            elif t == "percent_of_equity":
                q = eq * v / 100 / (ref_price * s.point_value)
            elif t == "risk_percent":
                if not risk_dist or risk_dist <= 0:
                    raise ValueError("qty_type risk_percent needs a stop distance (sl or sl_dist) on the entry")
                q = eq * v / 100 / (risk_dist * s.point_value)
            else:
                raise ValueError(f"unknown qty_type {t}")
        return self._round_qty(q)

    # ------------------------------------------------------------------
    # order API (called by the strategy at bar close)
    # ------------------------------------------------------------------
    def entry(self, id: str, side: int, qty: float, limit=None, stop=None, comment="", oca=None,
              bracket: dict | None = None):
        if qty < self.s.min_qty:
            # count a signal once, even when the strategy re-sends it on consecutive bars
            if self._last_reject.get(id) != self.bar - 1:
                self._log("rejected", order=id, reason="size below the minimum (0.01 lot); risk % too small for the stop")
            self._last_reject[id] = self.bar
            self.entries.pop(id, None)
            return
        if limit is not None and stop is not None:
            typ = "stop_limit"
        elif limit is not None:
            typ = "limit"
        elif stop is not None:
            typ = "stop"
        else:
            typ = "market"
        self.entries[id] = EntryOrder(id, side, typ, qty, limit, stop, self.bar, comment, oca, False, bracket)
        self.placed.append((self.bar, "entry", id, side, typ, round(limit or 0, 6), round(stop or 0, 6), qty))
        if self.s.process_orders_on_close and typ == "market":
            self._fill_entry(self.entries.pop(id), self.c[self.bar], self.bar, at_close=True)

    def exit(self, id: str, from_entry: str | None = None, **kw):
        prev = self.exits.get(id)
        ex = ExitOrder(id, from_entry, **kw)
        if prev is not None and prev.from_entry == from_entry:
            ex.attached, ex.done = prev.attached, prev.done
        self.exits[id] = ex

    def close(self, entry_id: str | None = None, comment: str = "", qty_percent: float = 100.0):
        if not self.trades:
            return
        self.placed.append((self.bar, "close", entry_id, 0, "market", 0, 0, qty_percent))
        if entry_id is not None and not any(t.entry_id == entry_id for t in self.trades):
            return
        if self.s.process_orders_on_close:
            self._fill_close(CloseOrder(entry_id, comment, qty_percent), self.c[self.bar], self.bar, at_close=True)
        else:
            self.closes.append(CloseOrder(entry_id, comment, qty_percent))

    def cancel(self, id: str):
        self.entries.pop(id, None)
        self.exits.pop(id, None)

    def cancel_all(self):
        self.entries.clear()
        self.exits.clear()

    # ------------------------------------------------------------------
    # fills
    # ------------------------------------------------------------------
    def _log(self, kind: str, **kw):
        kw.update(kind=kind, bar=self.bar, time=self.time[self.bar] if self.bar >= 0 else None)
        self.events.append(kw)

    def _open_trade(self, o: EntryOrder, price: float, bar: int, qty: float):
        if self.s.margin_percent:
            eq = self.equity_at(price if o.side == SHORT else price - self.cur_spread, self.cur_spread)
            used = sum(t.qty * t.entry_price for t in self.trades) * self.s.point_value * self.s.margin_percent / 100
            free = eq - used
            max_q = free / (price * self.s.point_value * self.s.margin_percent / 100)
            if qty > max_q:
                new_q = self._round_qty(max(max_q, 0))
                self._log("margin_reduce", order=o.id, wanted=qty, got=new_q)
                qty = new_q
        if qty < self.s.min_qty:
            self._log("rejected", order=o.id, reason="insufficient margin or qty below minimum")
            return
        fee = self._commission(qty, price)
        self.cash -= fee
        self.total_commission += fee
        self._tid += 1
        t = Trade(self._tid, o.id, o.side, qty, price, bar, self.time[bar], o.comment, fee, price, price)
        self.trades.append(t)
        self._log("fill", order=o.id, side=o.side, qty=qty, price=price)
        if o.bracket:
            self.exit(f"{o.id} exit", o.id, **o.bracket)
        if o.oca:
            for k in [k for k, e in self.entries.items() if e.oca == o.oca and k != o.id]:
                del self.entries[k]

    def _fill_entry(self, o: EntryOrder, price: float, bar: int, at_close: bool = False):
        pos = self.position
        if pos * o.side < 0:  # reversal: close everything first, like strategy.entry does
            for t in list(self.trades):
                self._close_trade(t, t.qty, price if t.side == SHORT else price, bar, o.id, o.comment)
        elif pos * o.side > 0:
            same = [t for t in self.trades if t.side == o.side]
            if len(same) >= max(1, self.s.pyramiding):
                self._log("ignored", order=o.id, reason="pyramiding limit")
                return
        self._open_trade(o, price, bar, o.qty)

    def _close_trade(self, t: Trade, qty: float, price: float, bar: int, exit_id: str, comment: str = ""):
        qty = min(qty, t.qty)
        fee = self._commission(qty, price)
        frac = qty / t.qty
        entry_fee = t.entry_commission * frac
        gross = t.side * (price - t.entry_price) * qty * self.s.point_value
        pnl = gross - fee - entry_fee
        self.realized_pnl += pnl
        self.cash += gross - fee
        self.total_commission += fee
        pv = self.s.point_value
        self.closed.append({
            "trade": t.tid, "side": "long" if t.side == LONG else "short", "entry_id": t.entry_id,
            "entry_time": t.entry_time, "entry_price": t.entry_price, "entry_bar": t.entry_bar,
            "exit_id": exit_id, "exit_time": self.time[bar], "exit_price": price, "exit_bar": bar,
            "qty": qty, "lots": qty / self.s.contract_size,
            "pnl": pnl, "pnl_pct": 100 * pnl / (t.entry_price * qty * pv),
            "commission": fee + entry_fee,
            "runup": max(0.0, t.side * (t.best - t.entry_price)) * qty * pv,
            "drawdown": max(0.0, -t.side * (t.worst - t.entry_price)) * qty * pv,
            "bars": bar - t.entry_bar, "comment": comment or t.entry_comment,
        })
        self._log("fill", order=exit_id, side=-t.side, qty=qty, price=price)
        t.qty = round(t.qty - qty, 8)
        t.entry_commission -= entry_fee
        if t.qty <= 1e-9:
            self.trades.remove(t)
            for ex in list(self.exits.values()):
                if t.tid in ex.attached and not any(tt.tid in ex.attached for tt in self.trades):
                    del self.exits[ex.id]

    def _fill_close(self, c: CloseOrder, bid: float, bar: int, at_close: bool = False):
        slip = self.s.slippage_ticks * self.s.mintick
        for t in [t for t in self.trades if c.entry_id is None or t.entry_id == c.entry_id]:
            price = bid - slip if t.side == LONG else bid + self.cur_spread + slip
            q = t.qty if c.qty_percent >= 100 else max(self._round_qty(t.qty * c.qty_percent / 100), self.s.qty_step)
            self._close_trade(t, q, price, bar, "Close" if c.entry_id is None else f"Close {c.entry_id}", c.comment)

    # ------------------------------------------------------------------
    # trigger handling along the intrabar path
    # ------------------------------------------------------------------
    def _exit_levels(self, ex: ExitOrder, t: Trade):
        """Stop and limit prices this exit order currently implies for trade t."""
        # Pine v6: when both a price and a distance are given, whichever would trigger first wins.
        stop = ex.stop
        if ex.loss_dist is not None:
            d = t.entry_price - t.side * ex.loss_dist
            stop = d if stop is None else (max(stop, d) if t.side == LONG else min(stop, d))
        limit = ex.limit
        if ex.profit_dist is not None:
            d = t.entry_price + t.side * ex.profit_dist
            limit = d if limit is None else (min(limit, d) if t.side == LONG else max(limit, d))
        if ex.trail_offset is not None and ex.id in t.trail_active:
            wm = t.trail_active[ex.id]
            tstop = wm - t.side * ex.trail_offset
            if stop is None or (t.side == LONG and tstop > stop) or (t.side == SHORT and tstop < stop):
                stop = tstop
        return stop, limit

    def _triggers(self):
        """Every live price trigger as (direction, threshold_in_bid_space, payload).

        direction +1 means it fires when the bid rises to the threshold, -1 when it falls to it.
        """
        sp = self.cur_spread
        out = []
        for ex in self.exits.values():
            for t in self.trades:
                if ex.from_entry is not None and t.entry_id != ex.from_entry:
                    continue
                if t.tid in ex.done:
                    continue
                ex.attached.add(t.tid)
                stop, limit = self._exit_levels(ex, t)
                if t.side == LONG:   # exits sell on the bid
                    if stop is not None:
                        out.append((-1, stop, ("exit_stop", ex, t, stop)))
                    if limit is not None:
                        out.append((+1, limit + self.s.limit_fill_ticks * self.s.mintick, ("exit_limit", ex, t, limit)))
                else:                # short exits buy on the ask
                    if stop is not None:
                        out.append((+1, stop - sp, ("exit_stop", ex, t, stop)))
                    if limit is not None:
                        out.append((-1, limit - sp - self.s.limit_fill_ticks * self.s.mintick, ("exit_limit", ex, t, limit)))
        for o in self.entries.values():
            off = sp if o.side == LONG else 0.0
            lt = self.s.limit_fill_ticks * self.s.mintick
            if o.type == "stop" or (o.type == "stop_limit" and not o.stop_hit):
                out.append((o.side, o.stop - off, ("entry_stop", o, None, o.stop)))
            elif o.type == "limit" or (o.type == "stop_limit" and o.stop_hit):
                out.append((-o.side, o.limit - off - o.side * lt, ("entry_limit", o, None, o.limit)))
        return out

    def _execute(self, payload, bid: float, gap: bool):
        kind, order, t, level = payload
        sp = self.cur_spread
        slip = self.s.slippage_ticks * self.s.mintick
        bar = self.bar
        if kind == "exit_stop":
            if t.side == LONG:
                price = (min(level, bid) if gap else level) - slip
            else:
                price = (max(level, bid + sp) if gap else level) + slip
        elif kind == "exit_limit":
            if t.side == LONG:
                price = max(level, bid) if gap else level
            else:
                price = min(level, bid + sp) if gap else level
        elif kind == "entry_stop":
            ask = bid + sp
            if order.side == LONG:
                price = (max(level, ask) if gap else level) + slip
            else:
                price = (min(level, bid) if gap else level) - slip
            if order.type == "stop_limit":
                order.stop_hit = True
                return
        else:  # entry_limit
            if order.side == LONG:
                price = min(level, bid + sp) if gap else level
            else:
                price = max(level, bid) if gap else level
        if kind.startswith("exit"):
            q = t.qty if order.qty_percent >= 100 else max(self._round_qty(t.qty * order.qty_percent / 100), self.s.qty_step)
            order.done.add(t.tid)
            self._close_trade(t, q, price, bar, order.id, order.comment)
        else:
            self.entries.pop(order.id, None)
            self._fill_entry(order, price, bar)

    def _fire_immediate(self, bid: float):
        """Fill anything whose trigger is already satisfied at the current price (gaps)."""
        for _ in range(100):
            fired = False
            trig = self._triggers()
            trig.sort(key=lambda x: 0 if x[2][0].startswith("exit") else 1)
            for d, thr, payload in trig:
                if (d > 0 and bid >= thr) or (d < 0 and bid <= thr):
                    self._execute(payload, bid, gap=True)
                    fired = True
                    break
            if not fired:
                return

    def _walk(self, a: float, b: float):
        cur = a
        for _ in range(100):
            trig = self._triggers()
            if b > cur:
                cands = [x for x in trig if x[0] > 0 and cur < x[1] <= b]
                if not cands:
                    break
                best = min(x[1] for x in cands)
            elif b < cur:
                cands = [x for x in trig if x[0] < 0 and b <= x[1] < cur]
                if not cands:
                    break
                best = max(x[1] for x in cands)
            else:
                break
            group = [x for x in cands if x[1] == best]
            group.sort(key=lambda x: 0 if x[2][0].startswith("exit") else 1)
            self._execute(group[0][2], best, gap=False)
            cur = best
            self._fire_immediate(cur)
        self._update_trailing(b)

    def _update_trailing(self, bid: float):
        sp = self.cur_spread
        for t in self.trades:
            px = bid if t.side == LONG else bid + sp
            if t.side * (px - t.best) > 0:
                t.best = px
            if t.side * (px - t.worst) < 0:
                t.worst = px
            for ex in self.exits.values():
                if ex.trail_offset is None or (ex.from_entry is not None and ex.from_entry != t.entry_id):
                    continue
                act = ex.trail_price
                if ex.trail_trigger_dist is not None:
                    act = t.entry_price + t.side * ex.trail_trigger_dist
                if ex.id in t.trail_active:
                    if t.side * (px - t.trail_active[ex.id]) > 0:
                        t.trail_active[ex.id] = px
                elif act is None or t.side * (px - act) >= 0:
                    t.trail_active[ex.id] = px

    # ------------------------------------------------------------------
    # bar processing
    # ------------------------------------------------------------------
    @staticmethod
    def _ohlc_path(o, h, l, c):
        # TradingView: if the high is closer to the open than the low, assume O-H-L-C.
        return [o, h, l, c] if (h - o) <= (o - l) else [o, l, h, c]

    def _magnifier_paths(self, ltf: pd.DataFrame):
        paths = []
        idx = ltf.index
        pos = np.searchsorted(idx.values, self.time.values)
        pos = list(pos) + [len(ltf)]
        lo, lh, ll, lc = (ltf[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        lsp = ltf["spread"].fillna(0).to_numpy(float) if ("spread" in ltf and self.s.spread_mode == "data") else None
        for i in range(self.n):
            a, b = pos[i], pos[i + 1]
            if b <= a:
                paths.append(None)
                continue
            pts = []
            for j in range(a, b):
                sp = lsp[j] if lsp is not None else None
                for p in self._ohlc_path(lo[j], lh[j], ll[j], lc[j]):
                    pts.append((p, sp))
            paths.append(pts)
        return paths

    def process_bar(self, i: int):
        """Fill orders placed at the previous bar's close against bar i."""
        self.bar = i
        sp_bar = self.spread[i]
        path = None
        if self.sub_paths is not None and self.sub_paths[i]:
            path = [(p, sp if sp is not None else sp_bar) for p, sp in self.sub_paths[i]]
        if path is None:
            o, h, l, c = self.o[i], self.h[i], self.l[i], self.c[i]
            pos = self.position
            if self.s.intrabar == "pessimistic" and pos != 0:
                pts = [o, l, h, c] if pos > 0 else [o, h, l, c]
            else:
                pts = self._ohlc_path(o, h, l, c)
            path = [(p, sp_bar) for p in pts]

        open_px, self.cur_spread = path[0]
        # 0) overnight financing for positions carried through the 17:00 New York roll
        if self.rollovers[i] and self.trades and (self.s.swap_long or self.s.swap_short):
            fee = 0.0
            for t in self.trades:
                rate = self.s.swap_long if t.side == LONG else self.s.swap_short
                fee += rate * t.qty / self.s.contract_size * self.rollovers[i]
            self.cash += fee
            self.realized_pnl += fee
            self.total_swap += fee
        # 1) queued market closes and entries fill at the open
        closes, self.closes = self.closes, []
        for c in closes:
            self._fill_close(c, open_px, i)
        slip = self.s.slippage_ticks * self.s.mintick
        for o in [o for o in list(self.entries.values()) if o.type == "market"]:
            self.entries.pop(o.id, None)
            price = open_px + self.cur_spread + slip if o.side == LONG else open_px - slip
            self._fill_entry(o, price, i)
        # 2) gaps, then walk the path
        self._fire_immediate(open_px)
        self._update_trailing(open_px)
        for k in range(1, len(path)):
            self.cur_spread = path[k][1]
            self._walk(path[k - 1][0], path[k][0])
        self.cur_spread = sp_bar
        self._mark(i)

    def _mark(self, i: int):
        sp = self.spread[i]
        eq_c = self.equity_at(self.c[i], sp)
        eq_hi = self.equity_at(self.h[i], sp)
        eq_lo = self.equity_at(self.l[i], sp)
        self.equity_close[i] = eq_c
        self.equity_low[i] = min(eq_c, eq_hi, eq_lo)
        self.equity_high[i] = max(eq_c, eq_hi, eq_lo)
        self.pos_size[i] = self.position
        self.realized[i] = self.s.initial_capital + self.realized_pnl
        if self.s.margin_percent and self.trades:
            need = sum(t.qty * self.c[i] for t in self.trades) * self.s.point_value * self.s.margin_percent / 100
            if self.equity_low[i] < need * 0.5:  # stop-out at 50% margin level, typical for CFD brokers
                worst = self.l[i] if self.position > 0 else self.h[i]
                for t in list(self.trades):
                    px = worst if t.side == LONG else worst + sp
                    self._close_trade(t, t.qty, px, i, "Margin call")
                self.entries.clear()
                self._log("margin_call", equity=self.equity_low[i])
                self.equity_close[i] = self.cash
                self.pos_size[i] = 0.0
                self.realized[i] = self.s.initial_capital + self.realized_pnl

    def finish(self):
        if self.s.close_open_at_end and self.trades:
            i = self.n - 1
            self.bar = i
            self.cur_spread = self.spread[i]
            self._fill_close(CloseOrder(None, "End of data"), self.c[i], i)
            self.equity_close[i] = self.cash
            self.realized[i] = self.s.initial_capital + self.realized_pnl

    # ------------------------------------------------------------------
    # for the live runner: what should be resting at the broker right now
    # ------------------------------------------------------------------
    def working_orders(self) -> dict:
        trades = [{"tid": t.tid, "entry_id": t.entry_id, "side": t.side, "qty": t.qty,
                   "entry_price": t.entry_price} for t in self.trades]
        protective = []
        for ex in self.exits.values():
            for t in self.trades:
                if ex.from_entry is not None and t.entry_id != ex.from_entry:
                    continue
                stop, limit = self._exit_levels(ex, t)
                protective.append({"exit_id": ex.id, "tid": t.tid, "stop": stop, "limit": limit})
        pending = [{"id": o.id, "side": o.side, "type": o.type, "qty": o.qty, "limit": o.limit,
                    "stop": o.stop, "bracket": o.bracket} for o in self.entries.values()]
        return {"position": self.position, "trades": trades, "protective": protective,
                "pending_entries": pending, "pending_closes": [c.entry_id for c in self.closes]}
