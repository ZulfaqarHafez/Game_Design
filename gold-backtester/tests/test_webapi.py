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


# ---- every strategy on every timeframe with both cost models -------------------------------------------------
import json  # noqa: E402

from goldlab.webapi import MAX_BODY, route  # noqa: E402

STRATEGIES = [s["id"] for s in handle("strategies", None)[1]["strategies"]]
TIMEFRAMES = ["5m", "15m", "30m", "1h", "4h", "1d"]


@pytest.mark.parametrize("preset", ["realistic", "tradingview"])
@pytest.mark.parametrize("tf", TIMEFRAMES)
@pytest.mark.parametrize("slug", STRATEGIES)
def test_matrix_results_are_consistent(slug, tf, preset):
    code, r = handle("backtest", {"strategy": slug, "timeframe": tf, "preset": preset})
    assert code == 200, r
    json.dumps(r, allow_nan=False)                         # browsers reject NaN/Infinity in JSON
    m = r["metrics"]
    assert r["data"]["timeframe"] == tf

    times = [c[0] for c in r["candles"]]
    assert times == sorted(set(times)), "candles strictly increasing"
    for t, o, h, lo, c, v in r["candles"]:
        assert lo <= min(o, c) + 1e-9 and h >= max(o, c) - 1e-9 and v >= 0

    assert r["trades_total"] == m["total_trades"]
    assert m["winning_trades"] + m["losing_trades"] + m["even_trades"] == m["total_trades"]
    assert m["long_trades"] + m["short_trades"] == m["total_trades"]
    if not r["trades_truncated"]:
        assert len(r["trades"]) == m["total_trades"]
        assert sum(t["pnl"] for t in r["trades"]) == pytest.approx(m["net_profit"], abs=0.05)
    for t in r["trades"]:
        assert t["entry_time"] <= t["exit_time"] and t["side"] in ("long", "short") and t["lots"] > 0
        if t["risk"]:
            assert t["r"] == pytest.approx(t["pnl"] / t["risk"], rel=1e-3, abs=1e-3)

    assert len(r["equity"]) == len(r["drawdown"]) == len(r["buyhold"]) > 0
    assert all(d[1] <= 1e-9 for d in r["drawdown"]), "drawdown is never positive"
    if preset == "tradingview":
        assert m["commission_paid"] == 0 and m["swap_paid"] == 0


def test_every_input_has_a_plain_label():
    for s in handle("strategies", None)[1]["strategies"]:
        missing = set(s["params"]) - set(s.get("labels") or {})
        assert not missing, f"{s['id']} has no label for {missing}"


@pytest.mark.parametrize("method,op,raw,status", [
    ("GET", "strategies", None, 200),
    ("GET", "backtest", None, 405),
    ("PUT", "backtest", b"{}", 405),
    ("GET", "hack", None, 404),
    ("POST", "hack", b"{}", 404),
    ("POST", "backtest", b"{not json", 400),
    ("POST", "backtest", b"[1, 2]", 400),
    ("POST", "backtest", b"\xff\xfe", 400),
    ("POST", "backtest", b"x" * (MAX_BODY + 1), 413),
    ("POST", "pine", json.dumps({"strategy": "ema_trend_4h"}).encode(), 200),
])
def test_http_rules(method, op, raw, status):
    code, body = route(method, op, raw)
    assert code == status, body
    if status != 200:
        assert body["error"]
