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


# -- order sizes: a tenth of an ounce stays a tenth of an ounce -------------------

class FakeResponse:
    def __init__(self, body, status=200):
        self.status_code, self._body, self.text = status, body, str(body)

    def json(self):
        return self._body


class FakeOandaSession:
    """Stands in for requests.Session: answers the instrument lookup and records orders."""

    def __init__(self, precision, minimum):
        self.rules = {"tradeUnitsPrecision": precision, "minimumTradeSize": str(minimum)}
        self.headers, self.posted, self.lookups = {}, [], 0

    def request(self, method, url, **kw):
        if url.endswith("/instruments"):
            self.lookups += 1
            return FakeResponse({"instruments": [{"name": "XAU_USD", **self.rules}]})
        if method == "GET" and "/orders/@" in url:
            return FakeResponse({"errorMessage": "no such order"}, 404)
        if method == "POST" and url.endswith("/orders"):
            self.posted.append(kw["json"]["order"])
            return FakeResponse({"orderFillTransaction": {"id": "1"}})
        raise AssertionError(f"unexpected request {method} {url}")


def oanda(monkeypatch, precision, minimum):
    from goldlab.live.brokers.oanda import OandaBroker
    monkeypatch.setenv("OANDA_TOKEN", "test-token")
    b = OandaBroker("001-001-1234567-001")
    b.s = FakeOandaSession(precision, minimum)
    return b


def test_oanda_sends_a_tenth_of_an_ounce_where_the_account_allows_it(monkeypatch):
    b = oanda(monkeypatch, precision=1, minimum=0.1)
    assert b.size_problem(0.1) is None
    b.market_order(1, 0.1, "c1", stop=3990.0, take_profit=4030.0)
    b.market_order(-1, 0.3, "c2", stop=4020.0)
    b.pending_order(1, 2.0, "stop", 4010.0, "c3", stop=3995.0)
    assert [o["units"] for o in b.s.posted] == ["0.1", "-0.3", "2.0"]
    assert b.s.posted[0]["stopLossOnFill"]["price"] == "3990.000"
    assert b.s.lookups == 1                      # the account's size rules are read once
    assert "steps of 0.1 oz" in b.size_problem(0.25)


def test_oanda_refuses_a_size_the_account_cannot_trade(monkeypatch):
    b = oanda(monkeypatch, precision=0, minimum=1)   # an account that trades whole ounces only
    assert "from 1 oz" in b.size_problem(0.1)
    with pytest.raises(RuntimeError, match="Order not sent"):
        b.market_order(1, 0.1, "c1", stop=3990.0)
    with pytest.raises(RuntimeError, match="Order not sent"):
        b.pending_order(1, 1.5, "stop", 4010.0, "c2", stop=3995.0)
    assert b.s.posted == []                      # nothing reached the broker, and nothing was rounded up
    b.market_order(-1, 3, "c3", stop=4020.0)
    assert b.s.posted[0]["units"] == "-3"


def test_mt5_lot_sizes_are_exact_or_refused():
    from types import SimpleNamespace
    from goldlab.live.brokers.mt5 import MT5Broker
    b = MT5Broker.__new__(MT5Broker)
    b.symbol, b.contract = "XAUUSD", 100.0
    b.info = SimpleNamespace(volume_step=0.001, volume_min=0.001)
    assert b._lots(0.1) == 0.001 and b._lots(1.0) == 0.01
    b.info = SimpleNamespace(volume_step=0.01, volume_min=0.01)
    assert b._lots(1.0) == 0.01
    with pytest.raises(RuntimeError, match="Order not sent"):
        b._lots(0.1)                             # was silently sent as 0.01 lot (ten times the size)


class SizeCheckingPaper(PaperBroker):
    least = 1.0

    def size_problem(self, qty):
        return None if qty >= self.least else f"account minimum is {self.least:g} oz; the order was for {qty:g} oz"


def run_small_card(tmp_path, bars, least):
    s = load_strategy("donchian_breakout_4h", entry_len=20, exit_len=10)
    st = Settings.realistic(initial_capital=100_000, qty_type="lots", qty_value=0.001, qty_step=0.1, min_qty=0.1)
    start = 2750
    feed = ReplayFeed(bars, start)
    pb = SizeCheckingPaper(feed, tmp_path / "paper.json", 100_000, commission_per_lot=3.5, slippage=0.05)
    pb.least = least
    r = LiveRunner(s, "1h", pb, guard(tmp_path), st, tmp_path / "state", history=3000, max_signal_age=float("inf"))
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        r.step()
        while feed.advance():
            r.step()
    return pb, out.getvalue()


def test_runner_sends_the_cards_own_size(tmp_path, random_walk):
    pb, _ = run_small_card(tmp_path, random_walk, least=0.1)
    entries = [f for f in pb.st["fills"] if "market" in f["reason"] or "entry" in f["reason"]]
    assert len(entries) > 3
    assert {round(f["qty"], 6) for f in entries} == {0.1}      # never rounded up to a whole ounce


def test_runner_blocks_orders_below_the_account_minimum(tmp_path, random_walk):
    pb, log = run_small_card(tmp_path, random_walk, least=1.0)
    assert pb.st["fills"] == []
    assert "blocked" in log and "account minimum is 1 oz" in log
