"""The broker emulator must follow TradingView's documented fill rules."""
import pytest

from goldlab.engine import Settings, run
from goldlab.strategy import Strategy


class Script(Strategy):
    """Runs a dict {bar_index: callable(strategy)} so each test can place exact orders."""
    name = "script"
    params = {"plan": None}

    def next(self, i):
        f = (self.p.plan or {}).get(i)
        if f:
            f(self)


def tv(**kw):
    return Settings.tradingview(**kw)


def test_market_order_fills_next_bar_open(make_bars):
    d = make_bars([(100, 101, 99, 100.5), (102, 103, 101, 102.5), (103, 104, 102, 103)])
    r = run(Script(plan={0: lambda s: s.entry("L", "long", qty=1), 1: lambda s: s.close_position()}), d, tv())
    t = r.trades.iloc[0]
    assert t.entry_price == 102          # bar 1 open, not bar 0 close
    assert t.exit_price == 103           # close() placed at bar 1 close fills at bar 2 open
    assert t.pnl == pytest.approx(1.0)


def test_process_orders_on_close(make_bars):
    d = make_bars([(100, 101, 99, 100.5), (102, 103, 101, 102.5), (103, 104, 102, 103)])
    r = run(Script(plan={0: lambda s: s.entry("L", "long", qty=1), 1: lambda s: s.close_position()}), d,
            tv(process_orders_on_close=True))
    t = r.trades.iloc[0]
    assert t.entry_price == 100.5 and t.exit_price == 102.5


def test_stop_entry_gap_fills_at_open(make_bars):
    d = make_bars([(100, 101, 99, 100), (105, 106, 104, 105.5)])
    r = run(Script(plan={0: lambda s: s.entry("L", "long", qty=1, stop=102)}), d, tv(close_open_at_end=True))
    assert r.trades.iloc[0].entry_price == 105    # gapped through 102: fills at the open


def test_stop_entry_fills_at_level(make_bars):
    d = make_bars([(100, 101, 99, 100), (100, 103, 99.5, 102.5)])
    r = run(Script(plan={0: lambda s: s.entry("L", "long", qty=1, stop=102)}), d, tv(close_open_at_end=True))
    assert r.trades.iloc[0].entry_price == 102


def test_path_high_first_when_high_is_nearer_the_open(make_bars):
    # open 100, high 104 (4 away), low 97 (3 away)... low is nearer -> O-L-H-C -> stop at 98 first
    d = make_bars([(100, 100.5, 99.5, 100), (100, 104, 97, 101)])
    r = run(Script(plan={0: lambda s: s.entry("L", "long", qty=1, sl=98, tp=104)}), d, tv())
    assert r.trades.iloc[0].exit_price == 98
    # open 100, high 102 (2 away), low 96 (4 away): high nearer -> O-H-L-C -> target first
    d = make_bars([(100, 100.5, 99.5, 100), (100, 102, 96, 101)])
    r = run(Script(plan={0: lambda s: s.entry("L", "long", qty=1, sl=97, tp=101.5)}), d, tv())
    assert r.trades.iloc[0].exit_price == 101.5


def test_entry_and_exit_in_the_same_bar(make_bars):
    # buy stop at 101 fills on the way up, then the 103 target is hit later in the same bar
    d = make_bars([(100, 100.5, 99.5, 100), (100, 104, 99.8, 103.5)])
    r = run(Script(plan={0: lambda s: s.entry("L", "long", qty=1, stop=101, tp_dist=2)}), d, tv())
    t = r.trades.iloc[0]
    assert (t.entry_price, t.exit_price, t.bars) == (101, 103, 0)


def test_slippage_market_and_stop_not_limit(make_bars):
    d = make_bars([(100, 101, 99, 100), (100, 100.5, 98, 99), (99, 99.5, 97, 98)])
    st = tv(slippage_ticks=10, mintick=0.01)
    r = run(Script(plan={0: lambda s: s.entry("L", "long", qty=1, limit=98.5)}), d, st)
    assert r.open_trades[0]["entry_price"] == 98.5        # limit: no slippage
    r = run(Script(plan={0: lambda s: s.entry("L", "long", qty=1)}), d, st)
    assert r.open_trades[0]["entry_price"] == pytest.approx(100.10)


def test_spread_buys_on_ask_and_long_stop_on_bid(make_bars):
    d = make_bars([(100, 101, 99, 100), (100, 100.2, 99, 99.5), (99.5, 99.6, 98.9, 99)], spread=0.5)
    st = Settings(spread_mode="data", qty_type="units", qty_value=1, commission_value=0, margin_percent=None)
    r = run(Script(plan={0: lambda s: s.entry("L", "long", qty=1, sl=99.2)}), d, st)
    t = r.trades.iloc[0]
    assert t.entry_price == pytest.approx(100.5)          # ask = bid + spread
    assert t.exit_price == pytest.approx(99.2)            # long stop triggers on the bid
    # a short's stop triggers when the ASK reaches it: bid 100.2 + 0.5 spread > 100.6
    d2 = make_bars([(100, 101, 99, 100), (100, 100.2, 99.5, 100), (100, 100.05, 99.9, 100)], spread=0.5)
    r2 = run(Script(plan={0: lambda s: s.entry("S", "short", qty=1, sl=100.6)}), d2, st)
    assert r2.trades.iloc[0].exit_price == pytest.approx(100.6)


def test_reversal_closes_then_opens(make_bars):
    d = make_bars([(100, 101, 99, 100), (101, 102, 100, 101), (102, 103, 101, 102), (103, 104, 102, 103)])
    r = run(Script(plan={0: lambda s: s.entry("L", "long", qty=1), 1: lambda s: s.entry("S", "short", qty=1)}),
            d, tv())
    assert len(r.trades) == 1 and r.trades.iloc[0].exit_price == 102
    assert r.open_trades[0]["side"] == "short"


def test_pyramiding_limit(make_bars):
    d = make_bars([(100, 101, 99, 100)] * 5)
    plan = {i: (lambda s, i=i: s.entry(f"L{i}", "long", qty=1)) for i in range(3)}
    assert len(run(Script(plan=plan), d, tv(pyramiding=1)).open_trades) == 1
    assert len(run(Script(plan=plan), d, tv(pyramiding=3)).open_trades) == 3


def test_commission_per_lot(make_bars):
    d = make_bars([(100, 101, 99, 100), (100, 101, 99, 100), (100, 101, 99, 100)])
    st = tv(commission_type="cash_per_lot", commission_value=3.5)
    r = run(Script(plan={0: lambda s: s.entry("L", "long", lots=1), 1: lambda s: s.close_position()}), d, st)
    assert r.trades.iloc[0].commission == pytest.approx(7.0)   # $3.5 per side per lot
    assert r.trades.iloc[0].pnl == pytest.approx(-7.0)


def test_trailing_stop(make_bars):
    d = make_bars([(100, 100.5, 99.5, 100), (100, 105, 99.9, 104.8), (104.8, 104.9, 102, 102.5)])
    r = run(Script(plan={0: lambda s: s.entry("L", "long", qty=1, sl_dist=5, trail_offset=2)}), d, tv())
    assert r.trades.iloc[0].exit_price == pytest.approx(103.0)   # best 105 - 2


def test_risk_percent_sizing(make_bars):
    d = make_bars([(100, 101, 99, 100), (100, 101, 99, 100)])
    st = Settings(spread_mode="none", qty_type="risk_percent", qty_value=1.0, initial_capital=10_000,
                  margin_percent=None)
    r = run(Script(plan={0: lambda s: s.entry("L", "long", sl_dist=5)}), d, st)
    assert r.open_trades[0]["qty"] == 20     # $100 risk / $5 per oz


def test_tiny_orders_are_counted_not_silently_dropped(make_bars):
    d = make_bars([(100, 101, 99, 100), (100, 101, 99, 100)])
    st = Settings(spread_mode="none", qty_type="risk_percent", qty_value=0.1, initial_capital=1_000,
                  margin_percent=None)
    r = run(Script(plan={0: lambda s: s.entry("L", "long", sl_dist=50)}), d, st)  # $1 risk / $50 = 0.02 oz
    assert r.metrics["rejected_orders"] == 1 and not r.open_trades


def test_swap_charged_at_rollover_and_triple_wednesday(make_bars):
    # hourly bars from Tue 12:00 UTC to Thu 12:00 UTC crosses two 17:00 New York rolls
    rows = [(100, 100.1, 99.9, 100)] * 49
    d = make_bars(rows, start="2026-01-06 12:00")      # Tuesday
    st = Settings(spread_mode="none", qty_type="lots", qty_value=1, swap_long=-10, swap_short=0,
                  margin_percent=None)
    r = run(Script(plan={0: lambda s: s.entry("L", "long", lots=1)}), d, st)
    # Tue->Wed roll: x1, Wed->Thu roll: x3  => -40
    assert r.metrics["swap_paid"] == pytest.approx(40.0)
