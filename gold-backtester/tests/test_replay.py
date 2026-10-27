"""Bar replay on the server: bars for the browser, manual trades re-run through the engine, and
turning those trades into a strategy card."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from goldlab import indicators as ta
from goldlab.engine import Settings, run
from goldlab.rules import Context, RuleStrategy
from goldlab.strategy import Strategy
from goldlab.webapi import _data, handle, route

ROOT = Path(__file__).resolve().parents[1]
DF = _data("1h")
SECS = DF.index.as_unit("s").asi8


def at(date: str) -> int:
    return int(np.searchsorted(SECS, int(pd.Timestamp(date, tz="UTC").timestamp())))


def hidden_rule_trades(start="2024-01-01", end="2024-04-01", hold=10):
    """Trades placed exactly where 'close crosses above the 20 EMA while above the 200 EMA' fires."""
    sig = Context(DF, {}, {}).eval_static("crossover(close, ema(close, 20)) and close > ema(close, 200)").to_numpy()
    atr = ta.atr(DF.high, DF.low, DF.close, 14).to_numpy()
    lo, hi = at(start), at(end)
    trades, busy_until = [], -1
    for i in range(lo, hi):
        if not sig[i] or i <= busy_until:
            continue
        e = float(DF.close.iloc[i] + DF.spread.iloc[i] + 0.05)
        sl = e - 1.5 * atr[i]
        j = min(i + hold, hi - 1)
        trades.append({"side": "long", "lots": 0.1, "entry_time": int(SECS[i]), "entry_price": e, "sl": sl,
                       "tp": e + 2 * (e - sl), "exit_time": int(SECS[j]), "exit_by": "Close"})
        busy_until = j
    return trades, [[int(SECS[lo]), int(SECS[hi - 1])]]


# ------------------------------------------------------------------ engine
def test_fill_on_close_pays_spread_and_slippage():
    class BuyOnce(Strategy):
        params = {}

        def next(self, i):
            if i == 5:
                self.entry("L", "long", lots=0.1)
            if i == 6:
                self.entry("S", "short", lots=0.1)

    df = DF.iloc[:20]
    res = run(BuyOnce(), df, Settings.realistic(process_orders_on_close=True))
    t = res.trades.iloc[0]
    assert t.entry_price == pytest.approx(df.close.iloc[5] + df.spread.iloc[5] + 0.05)
    # the reversal at bar 6 sells at the bid minus slippage
    assert t.exit_price == pytest.approx(df.close.iloc[6] - 0.05)
    assert t.exit_kind == "reverse"


def test_exit_kinds_are_reported():
    code, r = handle("backtest", {"strategy": "ema_trend_4h", "timeframe": "4h"})
    kinds = {t["exit_kind"] for t in r["trades"]}
    assert code == 200 and kinds <= {"stop", "target", "close", "reverse", "margin"} and "stop" in kinds


# ------------------------------------------------------------------ bars
def test_bars_for_replay_are_exact_and_continue():
    from goldlab.webapi import unpack_bars
    t0 = int(SECS[at("2025-03-03")])
    code, b = handle("bars", {"timeframe": "1h", "at": t0, "before": 100, "after": 50})
    assert code == 200, b
    rows = unpack_bars(b["bars"])
    assert rows[b["index"]][0] == t0 and b["index"] == 100 and len(rows) == 150
    assert len(b["bars"]["sp"]) == len(b["bars"]["roll"]) == 150
    i = at("2025-03-03")
    assert rows[100][4] == DF.close.iloc[i] and rows[100][1] == DF.open.iloc[i]      # full precision survives the encoding
    assert abs(b["bars"]["sp"][100] - DF.spread.iloc[i]) < 1e-8
    assert set(b["bars"]["roll"]) <= {0, 1, 3}
    code, nxt = handle("bars", {"timeframe": "1h", "at": rows[-1][0] + 1, "before": 0, "after": 10})
    assert nxt["index"] == 0 and unpack_bars(nxt["bars"])[0][0] == int(SECS[i + 50])
    code, d = handle("bars", {"timeframe": "1h", "at": "2025-03-03", "before": 0, "after": 1})
    assert unpack_bars(d["bars"])[0][0] == t0
    assert handle("bars", {"timeframe": "2m", "at": t0})[0] == 400
    assert handle("bars", {"timeframe": "1h", "at": "2099-01-01"})[0] == 400


# ------------------------------------------------------------------ manual review
def test_manual_review_matches_hand_calculation():
    i = at("2025-03-03")
    c, sp = DF.close.iloc[i], DF.spread.iloc[i]
    trades = [{"side": "long", "lots": 0.2, "entry_time": int(SECS[i]), "sl": None, "tp": None,
               "exit_time": int(SECS[i + 5]), "exit_by": "Close"}]
    code, r = handle("manual", {"timeframe": "1h", "start_time": int(SECS[i - 3]), "end_time": int(SECS[i + 8]), "trades": trades})
    assert code == 200, r
    t = r["trades"][0]
    entry = c + sp + 0.05
    exit_ = DF.close.iloc[i + 5] - 0.05
    assert t["entry_price"] == pytest.approx(entry, abs=1e-6) and t["exit_price"] == pytest.approx(exit_, abs=1e-6)
    fees = 2 * 0.2 * 3.5
    swap = r["metrics"]["swap_paid"]
    assert t["pnl"] == pytest.approx((exit_ - entry) * 20 - fees, abs=1e-4)
    assert r["metrics"]["net_profit"] == pytest.approx(t["pnl"] + swap, abs=1e-4)
    assert t["exit_kind"] == "close" and r["strategy"]["manual"] is True


def test_manual_stops_targets_and_moves():
    i = at("2025-03-03")
    c = float(DF.close.iloc[i])
    # an unreachable target, a stop moved up 2 bars later, then left to run out
    trades = [{"side": "long", "lots": 0.1, "entry_time": int(SECS[i]), "sl": c - 500, "tp": c + 500,
               "mods": [{"time": int(SECS[i + 2]), "sl": c - 1, "tp": c + 500}]}]
    code, r = handle("manual", {"timeframe": "1h", "start_time": int(SECS[i]), "end_time": int(SECS[i + 200]), "trades": trades})
    assert code == 200, r
    t = r["trades"][0]
    assert t["exit_kind"] == "stop" and t["exit_time"] > int(SECS[i + 2])
    assert t["exit_price"] <= c - 1 - 0.05 + 1e-9          # filled at the moved stop (or a gap through it)
    assert t["risk"] == pytest.approx((t["entry_price"] - (c - 500)) * 10, rel=1e-6)   # R uses the first stop


@pytest.mark.parametrize("trades,msg", [
    ([{"side": "up", "lots": 1, "entry_time": 0}], "side"),
    ([{"side": "long", "lots": 0.001, "entry_time": 0}], "lots"),
    ([{"side": "long", "lots": 1, "entry_time": 0, "sl": -5}], "Stop loss"),
    ([{"side": "long", "lots": 1, "entry_time": 1}], "inside the session"),
    ([], "no trades"),
])
def test_manual_rejects_bad_input(trades, msg):
    i = at("2025-03-03")
    code, r = handle("manual", {"timeframe": "1h", "start_time": int(SECS[i]), "end_time": int(SECS[i + 10]), "trades": trades})
    assert code == 400 and msg.lower() in r["error"].lower()


def test_manual_rejects_time_between_bars():
    i = at("2025-03-03")
    trades = [{"side": "long", "lots": 1, "entry_time": int(SECS[i]) + 60}]
    code, r = handle("manual", {"timeframe": "1h", "start_time": int(SECS[i]), "end_time": int(SECS[i + 10]), "trades": trades})
    assert code == 400 and "not a bar" in r["error"]


def test_big_sessions_fit_in_one_request():
    trades, seen = hidden_rule_trades("2023-01-01", "2024-06-01")
    trades = (trades * 10)[:400]
    body = json.dumps({"timeframe": "1h", "trades": trades, "seen": seen}).encode()
    assert len(body) < 200_000
    assert route("POST", "learn", body)[0] in (200, 400)


# ------------------------------------------------------------------ learn
def test_learn_recovers_a_hidden_rule():
    trades, seen = hidden_rule_trades()
    code, out = handle("learn", {"timeframe": "1h", "trades": trades, "seen": seen})
    assert code == 200, out
    long = out["sides"]["long"]
    keys = {c["key"] for c in long["conditions"]}
    assert keys == {"above_ema200", "cross_up_ema20"}
    assert long["stop"]["atr_multiple"] == 1.5 and long["target"]["r_multiple"] == 2.0
    assert out["reproduction"]["reproduced"] >= 0.85 * len(trades)
    card = yaml.safe_load(out["card"])
    assert card["timeframe"] == "1h" and card["settings"] == {"qty_type": "lots", "qty_value": 0.1}
    RuleStrategy(card)                                     # a valid card the engine accepts
    assert {"net_profit", "total_trades", "profit_factor"} <= set(out["backtest"])
    code, bt = handle("backtest", {"card": out["card"]})
    assert code == 200 and bt["metrics"]["total_trades"] > 0


def test_learn_needs_enough_trades_and_says_why():
    trades, seen = hidden_rule_trades()
    assert handle("learn", {"timeframe": "1h", "trades": trades[:2], "seen": seen})[0] == 400
    shorts = [dict(t, side="short") for t in trades[:2]]
    code, out = handle("learn", {"timeframe": "1h", "trades": trades[:6] + shorts, "seen": seen})
    assert code == 200 and any("short" in n for n in out["notes"]) and "short:" not in out["card"]


def test_learn_random_entries_find_little():
    rng = np.random.default_rng(7)
    lo, hi = at("2024-01-01"), at("2024-04-01")
    idx = sorted(rng.choice(np.arange(lo, hi), 20, replace=False))
    trades = [{"side": "long", "lots": 0.1, "entry_time": int(SECS[i]), "entry_price": float(DF.close.iloc[i]),
               "exit_time": int(SECS[i + 1]), "exit_by": "Close"} for i in idx]
    code, out = handle("learn", {"timeframe": "1h", "trades": trades, "seen": [[int(SECS[lo]), int(SECS[hi - 1])]]})
    assert code == 200
    long = out["sides"]["long"]
    assert not long["found"] or long["f1"] < 0.5         # no strong pattern from coin flips


def test_cli_learn_writes_a_card(tmp_path):
    trades, seen = hidden_rule_trades()
    session = {"format": "goldlab-replay-session", "version": 1, "name": "Replay 1h test", "timeframe": "1h",
               "start_time": seen[0][0], "current_time": seen[0][1], "trades": trades}
    f = tmp_path / "session.json"
    f.write_text(json.dumps(session))
    out = tmp_path / "card.yaml"
    p = subprocess.run([sys.executable, "-m", "goldlab", "learn", str(f), "--out", str(out)], cwd=ROOT,
                       capture_output=True, text=True, timeout=300)
    assert p.returncode == 0, p.stderr
    assert "Close crosses above the 20 EMA" in p.stdout and out.exists()
    RuleStrategy(yaml.safe_load(out.read_text()))
    bad = tmp_path / "bad.json"
    bad.write_text("{}")
    p = subprocess.run([sys.executable, "-m", "goldlab", "learn", str(bad)], cwd=ROOT, capture_output=True, text=True)
    assert p.returncode != 0 and "replay session" in p.stderr
