import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from goldlab import indicators as ta
from goldlab.engine import Settings, run
from goldlab.engine.metrics import compute
from goldlab.journal import Journal, read_tradingview_trades
from goldlab.pine import to_pine
from goldlab.rules import RuleError, RuleStrategy, load_card
from goldlab.strategy import Strategy
from goldlab.validate import deflated_sharpe, lookahead_test, min_backtest_years, monte_carlo, pbo

EXAMPLES = sorted((Path(__file__).resolve().parents[1] / "strategies" / "examples").glob("*.yaml"))


# --- indicators --------------------------------------------------------------

def test_ema_matches_recursion(random_walk):
    c = random_walk["close"]
    e = ta.ema(c, 10)
    a = 2 / 11
    prev = c.iloc[:10].mean()
    assert e.iloc[9] == pytest.approx(prev)
    for i in range(10, 30):
        prev = a * c.iloc[i] + (1 - a) * prev
        assert e.iloc[i] == pytest.approx(prev)


def test_rsi_bounds_and_crossover(random_walk):
    r = ta.rsi(random_walk["close"], 14).dropna()
    assert r.between(0, 100).all()
    a = pd.Series([1, 2, 3, 2, 1.0])
    assert ta.crossover(a, 2.5).tolist() == [False, False, True, False, False]
    assert ta.crossunder(a, 1.5).tolist() == [False, False, False, False, True]


def test_session_range_never_peeks(random_walk):
    hi, lo = ta.session_range(random_walk, "00:00-07:00", "UTC")
    inside = ta.in_session(random_walk.index, "00:00-07:00", "UTC")
    assert hi[inside].isna().all()                      # unknown while the range is forming
    first = random_walk.index[(random_walk.index.hour == 7)][0]
    window = random_walk.loc[first - pd.Timedelta(hours=7): first - pd.Timedelta(hours=1)]
    assert hi[first] == pytest.approx(window["high"].max())


# --- strategy cards ------------------------------------------------------------

@pytest.mark.parametrize("expr", ["__import__('os').system('ls')", "close.__class__", "open('x')",
                                  "[c for c in close]", "lambda: 1", "close[-1] > close"])
def test_cards_reject_unsafe_or_future_expressions(random_walk, expr):
    card = {"name": "bad", "long": {"when": expr}}
    s = RuleStrategy(card)
    with pytest.raises(RuleError):
        run(s, random_walk, Settings.tradingview())


def test_card_unknown_keys_rejected():
    with pytest.raises(RuleError):
        RuleStrategy({"name": "x", "long": {"when": "true", "stoploss": 3}})


def test_security_uses_only_completed_higher_timeframe_bars(random_walk):
    from goldlab.data.resample import resample
    s = RuleStrategy({"name": "htf", "vars": {"d": 'security("1d", "close")'}, "long": {"when": "close > d"}})
    d = run(s, random_walk, Settings.tradingview()).strategy.ctx.eval_static("d")
    daily = resample(random_walk, "1d")
    # a daily bar labelled D covers 17:00 New York on D-1 .. 17:00 New York on D
    ends = (daily.index.tz_convert(None) + pd.Timedelta(hours=17)).tz_localize("America/New_York").tz_convert("UTC")
    for t in random_walk.index[100:400:7]:
        done = daily["close"][ends <= t]
        if len(done):
            assert d[t] == pytest.approx(done.iloc[-1])
        else:
            assert np.isnan(d[t])


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.stem)
def test_example_cards_run_and_export_to_pine(random_walk, path):
    s = load_card(path)
    res = run(s, random_walk, Settings.realistic(**(s.card.get("settings") or {})))
    assert "net_profit" in res.metrics
    code = to_pine(s)
    assert "//@version=6" in code and "strategy.entry(" in code
    assert code.count("(") == code.count(")")


# --- metrics -------------------------------------------------------------------

def test_profit_factor_and_win_rate(random_walk):
    trades = pd.DataFrame({"pnl": [100.0, -50.0, 0.0, 30.0], "pnl_pct": [1, -0.5, 0, 0.3],
                           "bars": [3, 2, 1, 4], "side": ["long"] * 4, "entry_price": [100.0] * 4})
    eq = pd.Series(10_000.0, index=random_walk.index[:10])
    m = compute(trades, eq, eq, eq, random_walk.iloc[:10], 10_000)
    assert m["profit_factor"] == pytest.approx(130 / 50)
    assert m["percent_profitable"] == pytest.approx(50.0)     # even trade stays in the denominator
    assert m["avg_trade"] == pytest.approx(80 / 4)


# --- validation statistics -------------------------------------------------------

def test_deflated_sharpe_penalises_many_trials():
    one = deflated_sharpe(0.1, 1000, 1, 0.0025)
    many = deflated_sharpe(0.1, 1000, 200, 0.0025)
    assert one > 0.99 and many < one


def test_min_backtest_length_grows_with_trials():
    assert 4 < min_backtest_years(45) < 6       # ~5 years for 45 trials at Sharpe 1
    assert min_backtest_years(1000) > min_backtest_years(45)


def test_pbo_on_pure_noise_is_high():
    rng = np.random.default_rng(0)
    noise = pd.DataFrame(rng.normal(0, 1, (160, 20)))
    assert pbo(noise, 8) > 0.2


def test_monte_carlo_percentiles():
    trades = pd.DataFrame({"pnl": [10.0, -5, 7, -3, 12, -8, 4, 6, -2, 9]})
    mc = monte_carlo(trades, 1000, n=2000)
    assert mc["final_p5"] <= mc["final_p50"] <= mc["final_p95"]


class Cheater(Strategy):
    name = "cheater"

    def init(self):
        self.future = self.data["close"].shift(-1).to_numpy()

    def next(self, i):
        if self.future[i] > self.close[i] and self.position_size <= 0:
            self.entry("L", "long", qty=1)
        elif self.future[i] < self.close[i] and self.position_size >= 0:
            self.entry("S", "short", qty=1)


def test_lookahead_test_catches_a_cheater(random_walk):
    assert not lookahead_test(Cheater(), random_walk, Settings.tradingview())["ok"]


# --- journal -----------------------------------------------------------------------

def test_journal_records_versions_and_trials(tmp_path, random_walk):
    j = Journal(tmp_path)
    s = load_card(EXAMPLES[0])
    for _ in range(3):
        j.record_run(run(s, random_walk, Settings.realistic()), kind="trial")
    slug = j.runs()["slug"].iloc[0]
    assert j.trial_count(slug) == 3
    assert len(list((tmp_path / "strategies" / slug).glob("*.yaml"))) == 1


def test_tradingview_trade_list_import(tmp_path):
    csv = tmp_path / "tv.csv"
    csv.write_text(
        "Trade #,Type,Signal,Date/Time,Price USD,Contracts,Profit USD,Profit %\n"
        "1,Exit long,TP,2026-01-02 10:00,2050.5,1,50.5,2.5\n"
        "1,Entry long,LONG,2026-01-02 08:00,2000,1,50.5,2.5\n"
        "2,Exit short,SL,2026-01-03 12:00,2010,1,-20,-1\n"
        "2,Entry short,SHORT,2026-01-03 09:00,1990,1,-20,-1\n")
    t = read_tradingview_trades(csv)
    assert list(t["side"]) == ["long", "short"] and list(t["pnl"]) == [50.5, -20.0]
    out = Journal(tmp_path / "j").import_tradingview(csv, "My TV idea")
    assert out["metrics"]["net_profit"] == pytest.approx(30.5)
