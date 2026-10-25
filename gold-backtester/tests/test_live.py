"""Paper trading, risk guard and webhook checks (no network, no real broker)."""
import io
import contextlib
from pathlib import Path

import pandas as pd
import pytest

from goldlab.api import load_strategy
from goldlab.engine import Settings, run
from goldlab.live.brokers.paper import PaperBroker, ReplayFeed
from goldlab.live.risk import RiskConfig, RiskGuard
from goldlab.live.runner import LiveRunner
from goldlab.live.webhook import AlertProcessor


def guard(tmp_path, **kw):
    cfg = dict(max_lots=5, max_order_lots=5, max_daily_loss_usd=1e9, max_orders_per_day=1000, max_spread=5,
               blackout_file=None)
    cfg.update(kw)
    return RiskGuard(RiskConfig(**cfg), tmp_path / "risk.json", tmp_path)


def test_risk_guard_blocks(tmp_path):
    g = guard(tmp_path, max_lots=0.1, max_order_lots=0.1)
    ok = dict(side=1, qty=10, price=2000, stop=1990, equity=10_000, position_qty=0, spread=0.3, market=2000)
    assert g.check(**ok) == []
    assert any("max" in r for r in g.check(**{**ok, "qty": 20}))
    assert any("stop" in r for r in g.check(**{**ok, "stop": None}))
    assert any("far from market" in r for r in g.check(**{**ok, "price": 2100}))
    assert g.check(**{**ok, "price": 2100}, kind="pending") == []
    (tmp_path / "KILL").write_text("")
    assert any("kill switch" in r for r in g.check(**ok))


def test_daily_loss_limit(tmp_path):
    g = guard(tmp_path, max_daily_loss_usd=100)
    now = pd.Timestamp("2026-03-03 12:00", tz="UTC")
    assert not g.daily_loss_hit(10_000, now)
    assert g.daily_loss_hit(9_890, now)


def test_paper_runner_matches_backtest(tmp_path, random_walk):
    s = load_strategy("donchian_breakout_4h", entry_len=20, exit_len=10)
    st = Settings.realistic(qty_type="lots", qty_value=0.1)
    start = 2750
    feed = ReplayFeed(random_walk, start)
    pb = PaperBroker(feed, tmp_path / "paper.json", 10_000, commission_per_lot=3.5, slippage=0.05)
    r = LiveRunner(s, "1h", pb, guard(tmp_path), st, tmp_path / "state", history=3000, max_signal_age=float("inf"))
    with contextlib.redirect_stdout(io.StringIO()):
        r.step()
        while feed.advance():
            r.step()
    fills = pd.DataFrame(pb.st["fills"])
    entries = fills[fills["reason"].str.contains("entry|market")]
    bt = run(s, random_walk, st).trades
    bt = bt[bt["entry_time"] > random_walk.index[start - 1]]
    assert len(bt) > 3
    n = min(len(bt), len(entries))
    # same entries, same prices (the paper account uses the same in-bar path rule)
    assert list(pd.to_datetime(entries["time"]).iloc[:n]) == list(bt["entry_time"].iloc[:n])
    assert (entries["price"].iloc[:n].to_numpy() - bt["entry_price"].iloc[:n].to_numpy()).__abs__().max() < 0.01


class FakeBroker:
    name = "fake"

    def __init__(self):
        self.pos = 0.0
        self.orders = []

    def position(self):
        from goldlab.live.brokers.base import Position
        return Position(1 if self.pos > 0 else (-1 if self.pos < 0 else 0), abs(self.pos), 2000.0)

    def quote(self):
        return 2000.0, 2000.3

    def equity(self):
        return 10_000.0

    def market_order(self, side, qty, cid, stop=None, tp=None):
        self.pos += side * qty
        self.orders.append((side, qty, stop))
        return {"ok": True}

    def close_position(self, cid):
        self.pos = 0.0
        return {"ok": True}


def test_webhook_validation_and_target_position(tmp_path, monkeypatch):
    monkeypatch.setenv("GOLDLAB_WEBHOOK_SECRET", "s3cret")
    b = FakeBroker()
    p = AlertProcessor(b, guard(tmp_path), {"allowed_ips": ["1.2.3.4"], "max_age_seconds": 60}, tmp_path / "wh")
    now = pd.Timestamp.now(tz="UTC").isoformat()
    msg = {"secret": "s3cret", "id": "a1", "target_position": 10, "time": now}
    assert p.validate({**msg, "secret": "nope"}, "1.2.3.4") == "bad secret"
    assert "not allowed" in p.validate(msg, "9.9.9.9")
    assert "stale" in p.validate({**msg, "time": "2020-01-01T00:00:00Z"}, "1.2.3.4")
    assert p.validate(msg, "1.2.3.4") is None
    with contextlib.redirect_stdout(io.StringIO()):
        p.execute(msg)                       # flat -> long 10
        assert b.pos == 10 and b.orders[-1][2] is not None   # always a broker-side stop
        p.execute({**msg, "id": "a2", "target_position": -10})   # reverse
        assert b.pos == -10
        p.execute({**msg, "id": "a3", "target_position": -10})   # already there: no order
        assert len(b.orders) == 2
    p.submit(msg)
    assert p.validate(msg, "1.2.3.4") == "duplicate"
