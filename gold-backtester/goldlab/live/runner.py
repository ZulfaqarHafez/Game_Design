"""The live loop: the SAME strategy code as the backtest, mirrored to a broker.

Each time a bar closes:
  1. fetch recent bars from the broker's own feed and drop the bar still forming
  2. replay the strategy through the backtest engine from a fixed anchor
     (so live decisions are exactly what the backtest would have done)
  3. read what the engine wants right now (working_orders) and mirror it:
       - a market entry placed at this bar's close  -> send a market order now
       - a pending stop/limit entry                  -> keep a matching resting order at the broker
       - the stop/target of the open trade           -> keep the broker's stop/target in sync (trailing)
       - engine flat but broker holds a position     -> close it
  4. every new-risk order passes RiskGuard first; every decision goes to an audit log

Trades the engine "took" before the bot started are never chased. If the broker
stopped out but the engine still shows the trade (feeds differ slightly), the bot
does not re-enter; it logs the divergence.
"""
from __future__ import annotations

import json
import time
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

from ..api import ROOT, load_strategy, make_settings
from ..data.resample import MINUTES
from ..engine.backtest import run
from ..journal import slugify
from .brokers.base import BrokerAdapter
from .risk import RiskConfig, RiskGuard


class LiveRunner:
    def __init__(self, strategy, timeframe: str, broker: BrokerAdapter, risk: RiskGuard, settings,
                 state_dir: Path, history: int = 1500, price_tolerance: float = 0.05,
                 max_signal_age: float | None = None):
        self.s = strategy
        self.tf = timeframe
        self.b = broker
        self.risk = risk
        self.settings = settings
        self.history = history
        self.tol = price_tolerance
        # act on a market signal only shortly after its bar closed (default: a quarter of a bar, min 2 min)
        self.max_signal_age = max_signal_age if max_signal_age is not None else max(120, MINUTES[timeframe] * 15)
        self.slug = slugify(strategy.name)
        self.dir = Path(state_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.audit_path = self.dir / "audit.jsonl"
        self.state_path = self.dir / "runner.json"
        st = json.loads(self.state_path.read_text()) if self.state_path.exists() else {}
        self.live_start = pd.Timestamp(st["live_start"]) if st.get("live_start") else None
        self.last_bar = pd.Timestamp(st["last_bar"]) if st.get("last_bar") else None
        self.sent = set(st.get("sent", []))
        self.diverged: set = set()
        self.cache: pd.DataFrame | None = None
        cache_file = self.dir / "bars.csv.gz"
        if cache_file.exists():
            from ..data.csv_io import read_bars
            self.cache = read_bars(cache_file)

    # -- bookkeeping --------------------------------------------------------
    def log(self, event: str, **kw):
        row = {"time": datetime.now(timezone.utc).isoformat(), "event": event, **kw}
        with self.audit_path.open("a") as f:
            f.write(json.dumps(row, default=str) + "\n")
        print(f"[{row['time'][:19]}] {event} {json.dumps(kw, default=str)[:300]}", flush=True)

    def save(self):
        self.state_path.write_text(json.dumps({"live_start": str(self.live_start) if self.live_start else None,
                                               "last_bar": str(self.last_bar) if self.last_bar else None,
                                               "sent": sorted(self.sent)[-500:]}, indent=2))
        if self.cache is not None:
            from ..data.csv_io import write_bars
            write_bars(self.cache.iloc[-20000:], self.dir / "bars.csv.gz")

    # -- bars ---------------------------------------------------------------
    def closed_bars(self) -> pd.DataFrame:
        df = self.b.candles(self.tf, self.history)
        if "complete" in df:
            df = df[df["complete"].astype(bool)].drop(columns=["complete"])
        else:
            end = df.index + pd.Timedelta(minutes=MINUTES[self.tf])
            df = df[end <= pd.Timestamp.now(tz="UTC")] if self.b.name != "paper" else df
        df = df[["open", "high", "low", "close"] + [c for c in ("volume", "spread") if c in df]]
        self.cache = df if self.cache is None else pd.concat([self.cache, df[df.index > self.cache.index[-1]]])
        self.cache.attrs.update(symbol="XAUUSD", timeframe=self.tf, source=self.b.name)
        return self.cache

    # -- the step -------------------------------------------------------------
    def step(self) -> str:
        bars = self.closed_bars()
        if bars.empty:
            return "no data"
        last = bars.index[-1]
        if self.last_bar is not None and last <= self.last_bar:
            return "waiting"
        if hasattr(self.b, "on_bars"):
            self.b.on_bars(bars)
        if self.live_start is None:
            self.live_start = last
            self.log("start", strategy=self.s.name, timeframe=self.tf, broker=self.b.name, first_bar=last)
        self.last_bar = last

        res = run(self.s, bars, self.settings)
        eng = res.strategy.broker
        want = eng.working_orders()
        mine = [t for t in eng.trades if t.entry_time > self.live_start]
        pos = self.b.position()
        bid, ask = self.b.quote()
        equity = self.b.equity()
        scale = 1.0
        if self.settings.qty_type in ("risk_percent", "percent_of_equity", "cash"):
            eng_eq = eng.equity_at(bid, ask - bid)
            scale = equity / eng_eq if eng_eq > 0 else 1.0

        # kill switch / daily loss: flatten and stand down
        if self.risk.kill_switch() or self.risk.daily_loss_hit(equity):
            reason = "kill switch" if self.risk.kill_switch() else "daily loss limit"
            if pos.side != 0:
                self.log("flatten", reason=reason, result=self.b.close_position(f"{self.slug}-halt-{last:%Y%m%d%H%M}"))
            for o in self.b.pending_orders():
                if o.client_id.startswith(self.slug) or self.b.name == "mt5":
                    self.b.cancel(o)
            self.log("halted", reason=reason)
            self.save()
            return "halted"

        # 1) exits the engine wants at this bar's close
        if want["pending_closes"] and pos.side != 0:
            self.log("close", why="strategy exit", result=self.b.close_position(f"{self.slug}-x-{last:%Y%m%d%H%M}"))
            pos = self.b.position()

        # 2) new market entries (fill at the next open in the backtest == now)
        bar_close = last + pd.Timedelta(minutes=MINUTES[self.tf])
        age = (pd.Timestamp.now(tz="UTC") - bar_close).total_seconds()
        stale = self.max_signal_age is not None and age > self.max_signal_age
        for o in [o for o in want["pending_entries"] if o["type"] == "market"]:
            cid = f"{self.slug}-{o['id']}-{last:%Y%m%d%H%M}"
            if cid in self.sent:
                continue
            if stale:
                self.log("skipped", order=cid, reason=f"signal is {age / 60:.0f} min old (bot started mid-bar)")
                self.sent.add(cid)
                continue
            if pos.side == -o["side"]:
                self.log("reverse", result=self.b.close_position(f"{cid}-rev"))
                pos = self.b.position()
            elif pos.side == o["side"] and self.settings.pyramiding <= 1:
                continue
            qty = max(round(o["qty"] * scale), 1)
            px = ask if o["side"] > 0 else bid
            stop, tp = self._bracket(o, px)
            blocked = self.risk.check(side=o["side"], qty=qty, price=px, stop=stop, equity=equity,
                                      position_qty=pos.qty if pos.side == o["side"] else 0.0,
                                      spread=ask - bid, market=bid)
            if blocked:
                self.log("blocked", order=cid, reasons=blocked)
                self.sent.add(cid)
                continue
            r = self.b.market_order(o["side"], qty, cid, stop, tp)
            self.risk.record_order()
            self.sent.add(cid)
            self.log("market_order", order=cid, side=o["side"], qty=qty, stop=stop, tp=tp, result=r)
            pos = self.b.position()

        # 3) resting stop/limit entries
        desired = {f"{self.slug}-{o['id']}-pending": o for o in want["pending_entries"] if o["type"] in ("stop", "limit")}
        for po in self.b.pending_orders():
            if not po.client_id.startswith(self.slug):
                continue
            o = desired.get(po.client_id.rsplit("#", 1)[0])
            price = o and (o["stop"] if o["type"] == "stop" else o["limit"])
            if o is None or abs(po.price - price) > self.tol:
                self.b.cancel(po)
                self.log("cancel_pending", order=po.client_id, reason="strategy cancelled or moved it")
            else:
                desired.pop(po.client_id.rsplit("#", 1)[0], None)
        for base_cid, o in desired.items():
            if (pos.side == o["side"] and self.settings.pyramiding <= 1):
                continue
            qty = max(round(o["qty"] * scale), 1)
            price = o["stop"] if o["type"] == "stop" else o["limit"]
            stop, tp = self._bracket(o, price)
            blocked = self.risk.check(side=o["side"], qty=qty, price=price, stop=stop, equity=equity,
                                      position_qty=pos.qty if pos.side == o["side"] else 0.0,
                                      spread=ask - bid, market=bid, kind="pending")
            if blocked:
                self.log("blocked", order=base_cid, reasons=blocked)
                continue
            cid = f"{base_cid}#{last:%Y%m%d%H%M}"
            r = self.b.pending_order(o["side"], qty, o["type"], price, cid, stop, tp)
            self.risk.record_order()
            self.log("pending_order", order=cid, side=o["side"], type=o["type"], price=price, qty=qty, stop=stop, tp=tp, result=r)

        # 4) keep the open position's stop/target in line with the engine (trailing stops)
        pos = self.b.position()
        if pos.side != 0 and mine:
            prot = [p for p in want["protective"] if p["tid"] == mine[0].tid]
            if prot:
                stop, tp = prot[0]["stop"], prot[0]["limit"]
                moved = (stop is not None and (pos.stop is None or abs(stop - pos.stop) > self.tol)) or \
                        (tp is not None and (pos.take_profit is None or abs(tp - pos.take_profit) > self.tol))
                if moved:
                    self.b.set_protection(stop, tp)
                    self.log("protection", stop=stop, tp=tp)
        # 5) divergence handling
        eng_side = 1 if eng.position > 0 else (-1 if eng.position < 0 else 0)
        if pos.side != 0 and not mine and not want["pending_entries"]:
            self.log("close", why="engine is flat but broker holds a position",
                     result=self.b.close_position(f"{self.slug}-sync-{last:%Y%m%d%H%M}"))
        elif mine and pos.side == 0 and mine[0].tid not in self.diverged:
            self.diverged.add(mine[0].tid)
            self.log("divergence", note="engine is in a trade the broker does not hold (blocked, missed or "
                     "already stopped out); not chasing it", engine_side=eng_side, entry=mine[0].entry_time)
        self.save()
        return "ok"

    def _bracket(self, o: dict, ref: float):
        br = o.get("bracket") or {}
        side = o["side"]
        stop = br.get("stop")
        if br.get("loss_dist") is not None:
            d = ref - side * br["loss_dist"]
            stop = d if stop is None else (max(stop, d) if side > 0 else min(stop, d))
        tp = br.get("limit")
        if br.get("profit_dist") is not None:
            d = ref + side * br["profit_dist"]
            tp = d if tp is None else (min(tp, d) if side > 0 else max(tp, d))
        return stop, tp

    def loop(self, poll_seconds: int = 10):
        step = pd.Timedelta(minutes=MINUTES[self.tf])
        while True:
            try:
                status = self.step()
            except Exception as e:  # keep running; the broker keeps the stop loss
                self.log("error", error=repr(e))
                status = "error"
            if status == "halted":
                time.sleep(60)
                continue
            now = pd.Timestamp.now(tz="UTC")
            nxt = (now.floor(step) + step) if status != "error" else now + pd.Timedelta(seconds=30)
            time.sleep(max(poll_seconds, (nxt - now).total_seconds() + 3) if status == "ok" else poll_seconds)


# ---------------------------------------------------------------------------

def load_config(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        example = ROOT / "live.example.yaml"
        raise SystemExit(f"No {p}. Copy {example.name} to {p.name} and edit it.")
    return yaml.safe_load(p.read_text()) or {}


def make_broker(name: str, cfg: dict, state_dir: Path) -> BrokerAdapter:
    if name == "paper":
        from .brokers.paper import PaperBroker
        pc = cfg.get("paper", {})
        feed_name = pc.get("feed", "yahoo")
        if feed_name == "oanda":
            from .brokers.oanda import OandaBroker
            o = OandaBroker(**cfg["oanda"])
            feed = lambda tf, n: o.candles(tf, n)
        else:
            from ..data import yahoo
            from ..data.resample import resample

            def feed(tf, n):
                native = {"4h": "1h", "2h": "1h"}.get(tf, tf)
                df = yahoo.load("GC=F", native)
                df = resample(df, tf) if native != tf else df
                end = df.index + pd.Timedelta(minutes=MINUTES[tf])
                return df[end <= pd.Timestamp.now(tz="UTC")].iloc[-n:]
        return PaperBroker(feed, state_dir / "paper_account.json", pc.get("initial_equity", 10_000.0))
    if name == "oanda":
        from .brokers.oanda import OandaBroker
        return OandaBroker(**cfg["oanda"])
    if name == "mt5":
        from .brokers.mt5 import MT5Broker
        return MT5Broker(**cfg["mt5"])
    raise ValueError(name)


def main(strategy_spec: str, timeframe: str | None = None, broker: str = "paper", once: bool = False,
         config: str | Path = ROOT / "live.yaml"):
    cfg = load_config(config)
    s = load_strategy(strategy_spec)
    tf = timeframe or s.timeframe or "1h"
    if broker != "paper":
        env = (cfg.get(broker) or {}).get("environment", "live")
        if env == "live" and not cfg.get("i_understand_this_trades_real_money"):
            raise SystemExit("Refusing to trade a live account: set i_understand_this_trades_real_money: true in "
                             "live.yaml after you have paper traded this strategy.")
    state_dir = ROOT / "journal" / "live" / f"{slugify(s.name)}-{broker}"
    names = {f.name for f in fields(RiskConfig)}
    risk = RiskGuard(RiskConfig(**{k: v for k, v in (cfg.get("risk") or {}).items() if k in names}),
                     state_dir / "risk_state.json", ROOT)
    b = make_broker(broker, cfg, state_dir)
    st = make_settings(s, "realistic")
    r = LiveRunner(s, tf, b, risk, st, state_dir, history=int(cfg.get("history_bars", 1500)))
    if once:
        print(r.step())
    else:
        r.loop()
