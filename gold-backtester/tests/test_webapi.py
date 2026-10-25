"""The website's backtest API: results come back, bad input is refused."""
import pytest

from goldlab.webapi import handle


def test_strategies_listed():
    code, body = handle("strategies", None)
    assert code == 200 and len(body["strategies"]) >= 7
    assert {"1h", "4h", "1d"} <= set(body["data"])


def test_backtest_returns_aligned_chart_data():
    code, r = handle("backtest", {"strategy": "london_breakout_15m", "timeframe": "15m"})
    assert code == 200, r
    times = {c[0] for c in r["candles"]}
    first = r["candles"][0][0]
    assert r["candles"][0][0] > 1_500_000_000          # unix seconds, not ms or us
    for t in r["trades"]:
        for k in ("entry_time", "exit_time"):
            assert t[k] < first or t[k] in times         # every marker sits on a candle
    for pts in r["plots"].values():
        assert all(p[0] in times for p in pts)
    assert len(r["equity"]) == len(r["buyhold"]) == len(r["drawdown"])


def test_overrides_apply():
    base = handle("backtest", {"strategy": "ema_trend_4h"})[1]
    other = handle("backtest", {"strategy": "ema_trend_4h", "params": {"fast": 20},
                                "settings": {"initial_capital": 50_000, "qty_type": "lots", "qty_value": 0.5}})[1]
    assert other["strategy"]["params"]["fast"] == 20 and other["settings"]["initial_capital"] == 50_000
    assert other["metrics"]["total_trades"] != base["metrics"]["total_trades"]
    tv = handle("backtest", {"strategy": "ema_trend_4h", "preset": "tradingview"})[1]
    assert tv["settings"]["spread_mode"] == "none" and tv["metrics"]["commission_paid"] == 0


@pytest.mark.parametrize("req,msg", [
    ({"strategy": "nope"}, "Unknown strategy"),
    ({"strategy": "ema_trend_4h", "params": {"fast": "x"}}, "must be a number"),
    ({"strategy": "ema_trend_4h", "params": {"bogus": 1}}, "Unknown parameter"),
    ({"strategy": "ema_trend_4h", "settings": {"initial_capital": 1}}, "Account size"),
    ({"strategy": "ema_trend_4h", "settings": {"evil": 1}}, "Unknown settings"),
    ({"strategy": "ema_trend_4h", "timeframe": "2m"}, "Timeframe"),
    ({"card": "name: x\nlong:\n  when: 10**10**10 > 1\n"}, "Powers"),
    ({"card": "name: x\nlong:\n  when: wma(close, 100000) > 1\n"}, "at most"),
    ({"card": "name: x\nlong:\n  when: close[-1] > close\n"}, "future"),
    ({"card": "name: x\nlong:\n  when: __import__('os')\n"}, "Unknown function"),
    ({"card": "!!python/object/apply:os.system ['ls']"}, "YAML"),
    ({"card": "x" * 30_000}, "too long"),
])
def test_bad_requests_are_refused(req, msg):
    code, body = handle("backtest", req)
    assert code == 400 and msg.lower() in body["error"].lower()


def test_pine_and_validate():
    code, p = handle("pine", {"strategy": "tsmom_daily"})
    assert code == 200 and "//@version=6" in p["pine"]
    code, v = handle("validate", {"strategy": "tsmom_daily"})
    assert code == 200 and v["verdict"] in ("ready", "caution", "not-ready") and len(v["checks"]) >= 8
