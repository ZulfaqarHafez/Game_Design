"""Turn trades you placed by hand (bar replay) into a strategy card.

The idea: when you trade by eye you are reacting to something you can see on the
chart. This module checks a library of chart conditions (trend, momentum,
breakouts, candle patterns, sessions, volatility) at the bars where you entered,
and at the bars you looked at and passed on. It then picks the few conditions
that, combined, best reproduce your entries, takes your usual stop distance
(in ATRs) and target (in R) from your trades, and writes a normal strategy card
that the backtester, the checklist and the Pine exporter all understand.

It is pattern-matching, not mind-reading: with fewer than ~10 trades per side the
result is a starting point to edit, and the report says how many of your entries
the card reproduces so you can judge.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

import numpy as np
import pandas as pd
import yaml

from . import indicators as ta
from .rules import Context

TOLERANCE = 3          # an entry counts as reproduced if the card signals up to 3 bars earlier (or 1 later)
MIN_TRADES = 3         # per side
MAX_CONDITIONS = 4


@dataclass(frozen=True)
class Cond:
    key: str
    label: str
    expr: str
    kind: str = "state"          # state (true for a stretch of bars) or event (true on a single bar)
    intraday: bool = False       # only meaningful below 4h


SESSION = 'in_session("{w}", "America/New_York")'
CONDITIONS = [
    # trend
    Cond("above_ema200", "Price above the 200 EMA", "close > ema(close, 200)"),
    Cond("below_ema200", "Price below the 200 EMA", "close < ema(close, 200)"),
    Cond("above_ema50", "Price above the 50 EMA", "close > ema(close, 50)"),
    Cond("below_ema50", "Price below the 50 EMA", "close < ema(close, 50)"),
    Cond("above_ema20", "Price above the 20 EMA", "close > ema(close, 20)"),
    Cond("below_ema20", "Price below the 20 EMA", "close < ema(close, 20)"),
    Cond("ema_stack_up", "EMAs stacked up (20 > 50 > 200)", "ema(close, 20) > ema(close, 50) and ema(close, 50) > ema(close, 200)"),
    Cond("ema_stack_down", "EMAs stacked down (20 < 50 < 200)", "ema(close, 20) < ema(close, 50) and ema(close, 50) < ema(close, 200)"),
    Cond("ema20_rising", "20 EMA rising", "ema(close, 20) > ema(close, 20)[3]"),
    Cond("ema20_falling", "20 EMA falling", "ema(close, 20) < ema(close, 20)[3]"),
    Cond("supertrend_up", "Supertrend (3, 10) is up", "supertrend_dir(3, 10) < 0"),
    Cond("supertrend_down", "Supertrend (3, 10) is down", "supertrend_dir(3, 10) > 0"),
    Cond("adx_trending", "Trending: ADX(14) above 25", "adx(14) > 25"),
    Cond("adx_ranging", "Ranging: ADX(14) below 20", "adx(14) < 20"),
    # momentum
    Cond("rsi_below_30", "RSI(14) below 30 (oversold)", "rsi(close, 14) < 30"),
    Cond("rsi_below_40", "RSI(14) below 40", "rsi(close, 14) < 40"),
    Cond("rsi_above_60", "RSI(14) above 60", "rsi(close, 14) > 60"),
    Cond("rsi_above_70", "RSI(14) above 70 (overbought)", "rsi(close, 14) > 70"),
    Cond("rsi_above_50", "RSI(14) above 50", "rsi(close, 14) > 50"),
    Cond("rsi_below_50", "RSI(14) below 50", "rsi(close, 14) < 50"),
    Cond("macd_positive", "MACD histogram above zero", "macd_hist(close) > 0"),
    Cond("macd_negative", "MACD histogram below zero", "macd_hist(close) < 0"),
    # location
    Cond("near_ema20", "Price within 0.5 ATR of the 20 EMA", "abs(close - ema(close, 20)) < 0.5 * atr(14)"),
    Cond("near_ema50", "Price within 0.5 ATR of the 50 EMA", "abs(close - ema(close, 50)) < 0.5 * atr(14)"),
    Cond("below_bb", "Close below the lower Bollinger Band (20, 2)", "close < bb_lower(close, 20, 2)"),
    Cond("above_bb", "Close above the upper Bollinger Band (20, 2)", "close > bb_upper(close, 20, 2)"),
    Cond("high_vol", "Volatility above normal: ATR(14) above its 100-bar average", "atr(14) > sma(atr(14), 100)"),
    Cond("low_vol", "Volatility below normal: ATR(14) below its 100-bar average", "atr(14) < sma(atr(14), 100)"),
    # events
    Cond("cross_up_ema20", "Close crosses above the 20 EMA", "crossover(close, ema(close, 20))", "event"),
    Cond("cross_down_ema20", "Close crosses below the 20 EMA", "crossunder(close, ema(close, 20))", "event"),
    Cond("cross_up_ema50", "Close crosses above the 50 EMA", "crossover(close, ema(close, 50))", "event"),
    Cond("cross_down_ema50", "Close crosses below the 50 EMA", "crossunder(close, ema(close, 50))", "event"),
    Cond("ema20_50_up", "20 EMA crosses above the 50 EMA", "crossover(ema(close, 20), ema(close, 50))", "event"),
    Cond("ema20_50_down", "20 EMA crosses below the 50 EMA", "crossunder(ema(close, 20), ema(close, 50))", "event"),
    Cond("ema50_200_up", "50 EMA crosses above the 200 EMA", "crossover(ema(close, 50), ema(close, 200))", "event"),
    Cond("ema50_200_down", "50 EMA crosses below the 200 EMA", "crossunder(ema(close, 50), ema(close, 200))", "event"),
    Cond("breakout_20_up", "Close above the previous 20-bar high", "close > highest(high, 20)[1]", "event"),
    Cond("breakout_20_down", "Close below the previous 20-bar low", "close < lowest(low, 20)[1]", "event"),
    Cond("breakout_55_up", "Close above the previous 55-bar high", "close > highest(high, 55)[1]", "event"),
    Cond("breakout_55_down", "Close below the previous 55-bar low", "close < lowest(low, 55)[1]", "event"),
    Cond("rsi_up_30", "RSI(14) crosses back above 30", "crossover(rsi(close, 14), 30)", "event"),
    Cond("rsi_down_70", "RSI(14) crosses back below 70", "crossunder(rsi(close, 14), 70)", "event"),
    Cond("rsi_up_50", "RSI(14) crosses above 50", "crossover(rsi(close, 14), 50)", "event"),
    Cond("rsi_down_50", "RSI(14) crosses below 50", "crossunder(rsi(close, 14), 50)", "event"),
    Cond("macd_up", "MACD crosses above its signal line", "crossover(macd(close), macd_signal(close))", "event"),
    Cond("macd_down", "MACD crosses below its signal line", "crossunder(macd(close), macd_signal(close))", "event"),
    Cond("bb_back_in_up", "Close back inside the lower Bollinger Band", "crossover(close, bb_lower(close, 20, 2))", "event"),
    Cond("bb_back_in_down", "Close back inside the upper Bollinger Band", "crossunder(close, bb_upper(close, 20, 2))", "event"),
    Cond("supertrend_flip_up", "Supertrend turns up", "supertrend_dir(3, 10) < 0 and supertrend_dir(3, 10)[1] > 0", "event"),
    Cond("supertrend_flip_down", "Supertrend turns down", "supertrend_dir(3, 10) > 0 and supertrend_dir(3, 10)[1] < 0", "event"),
    # candles
    Cond("bull_bar", "Bullish candle (close above open)", "close > open"),
    Cond("bear_bar", "Bearish candle (close below open)", "close < open"),
    Cond("bull_engulf", "Bullish engulfing candle",
         "close > open and close[1] < open[1] and close >= open[1] and open <= close[1]", "event"),
    Cond("bear_engulf", "Bearish engulfing candle",
         "close < open and close[1] > open[1] and close <= open[1] and open >= close[1]", "event"),
    Cond("hammer", "Hammer (long lower wick)",
         "min(open, close) - low > 2 * abs(close - open) and high - max(open, close) < 0.5 * (min(open, close) - low)", "event"),
    Cond("shooting_star", "Shooting star (long upper wick)",
         "high - max(open, close) > 2 * abs(close - open) and min(open, close) - low < 0.5 * (high - max(open, close))", "event"),
    Cond("close_above_prev_high", "Close above the previous bar's high", "close > high[1]", "event"),
    Cond("close_below_prev_low", "Close below the previous bar's low", "close < low[1]", "event"),
    # sessions (New York clock, as in the Analysis tab)
    Cond("asia", "Asia session (18:00–03:00 New York)", SESSION.format(w="18:00-03:00"), intraday=True),
    Cond("london", "London session (03:00–08:00 New York)", SESSION.format(w="03:00-08:00"), intraday=True),
    Cond("new_york", "New York session (08:00–17:00 New York)", SESSION.format(w="08:00-17:00"), intraday=True),
    Cond("asia_break_up", "Close above the Asian range high",
         'close > session_high("18:00-03:00", "America/New_York")', "event", intraday=True),
    Cond("asia_break_down", "Close below the Asian range low",
         'close < session_low("18:00-03:00", "America/New_York")', "event", intraday=True),
]
BY_KEY = {c.key: c for c in CONDITIONS}


def _bool(v, n) -> np.ndarray:
    if np.isscalar(v):
        return np.full(n, bool(v))
    s = pd.Series(np.asarray(v)) if not isinstance(v, pd.Series) else v.reset_index(drop=True)
    return s.astype("float64").fillna(0).to_numpy() > 0 if s.dtype != bool else s.to_numpy()


def _edges(m: np.ndarray) -> np.ndarray:
    prev = np.concatenate([[False], m[:-1]])
    return m & ~prev


def _score(signals: np.ndarray, entries: np.ndarray) -> tuple[float, int, int, int]:
    """F1 of signal bars vs your entry bars, with timing tolerance. Returns (f1, matched entries, matched signals, signals)."""
    sig = np.flatnonzero(signals)
    if not len(sig) or not len(entries):
        return 0.0, 0, 0, len(sig)
    # entry e is reproduced if a signal lies in [e - TOLERANCE, e + 1]
    lo = np.searchsorted(sig, entries - TOLERANCE, side="left")
    hi = np.searchsorted(sig, entries + 1, side="right")
    m_e = int(np.sum(hi > lo))
    # signal s is useful if an entry lies in [s - 1, s + TOLERANCE]
    lo2 = np.searchsorted(entries, sig - 1, side="left")
    hi2 = np.searchsorted(entries, sig + TOLERANCE, side="right")
    m_s = int(np.sum(hi2 > lo2))
    recall, precision = m_e / len(entries), m_s / len(sig)
    f1 = 0.0 if recall + precision == 0 else 2 * recall * precision / (recall + precision)
    return f1, m_e, m_s, len(sig)


def _round_to(x: float, step: float, lo: float, hi: float) -> float:
    return float(min(hi, max(lo, round(x / step) * step)))


def learn(df: pd.DataFrame, trades: list[dict], seen: list[tuple[int, int]], timeframe: str,
          name: str | None = None) -> dict:
    """Find the conditions behind your entries and write them up as a strategy card.

    df: bars for the timeframe (UTC index). trades: cleaned manual trades (see goldlab.manual).
    seen: (start, end) unix-second ranges of bars you stepped through in replay.
    """
    n = len(df)
    secs = df.index.as_unit("s").asi8
    pos_of = {int(s): i for i, s in enumerate(secs)}
    trades = [t for t in trades if int(t["entry_time"]) in pos_of]
    if not trades:
        raise ValueError("None of these trades fall on bars of this timeframe")

    ctx = Context(df, {}, {})
    intraday = timeframe not in ("4h", "1d")
    feats: dict[str, np.ndarray] = {}
    for c in CONDITIONS:
        if c.intraday and not intraday:
            continue
        feats[c.key] = _bool(ctx.eval_static(c.expr), n)

    seen_mask = np.zeros(n, dtype=bool)
    for a, b in seen:
        lo, hi = np.searchsorted(secs, int(a)), np.searchsorted(secs, int(b), side="right")
        seen_mask[lo:hi] = True
    in_trade = np.zeros(n, dtype=bool)
    for t in trades:
        i = pos_of[int(t["entry_time"])]
        seen_mask[i] = True
        j = pos_of.get(int(t["exit_time"])) if t.get("exit_time") else None
        in_trade[i + 1:(j if j is not None else n)] = True   # flat again from the exit bar's close
    eligible = seen_mask & ~in_trade   # bars where you were flat and could have entered

    atr = ta.atr(df["high"], df["low"], df["close"], 14).to_numpy()
    result = {"timeframe": timeframe, "trades": len(trades), "sides": {}, "notes": []}
    card_vars, sides = {}, {}
    plots: dict[str, str] = {}

    for side in ("long", "short"):
        ts = [t for t in trades if t["side"] == side]
        info = {"trades": len(ts), "found": False, "conditions": []}
        result["sides"][side] = info
        if len(ts) < MIN_TRADES:
            if ts:
                result["notes"].append(f"Only {len(ts)} {side} trade{'s' if len(ts) != 1 else ''}: "
                                       f"take at least {MIN_TRADES} to learn a {side} rule.")
            continue
        entries = np.array(sorted(pos_of[int(t["entry_time"])] for t in ts))
        chosen: list[str] = []
        mask = np.ones(n, dtype=bool)
        best = (0.0, 0, 0, 0)
        for _ in range(MAX_CONDITIONS):
            pick = None
            for key, f in feats.items():
                if key in chosen:
                    continue
                m = mask & f
                sc = _score(_edges(m) & eligible, entries)
                if sc[0] > best[0] + 0.005 and (pick is None or sc[0] > pick[1][0]):
                    pick = (key, sc)
            if pick is None:
                break
            chosen.append(pick[0])
            mask &= feats[pick[0]]
            best = pick[1]
        # drop conditions that add nothing (e.g. "above the 20 EMA" once "crosses above the 20 EMA" is in)
        for key in list(reversed(chosen)):
            if len(chosen) == 1:
                break
            rest = [k for k in chosen if k != key]
            m = np.ones(n, dtype=bool)
            for k in rest:
                m &= feats[k]
            sc = _score(_edges(m) & eligible, entries)
            if sc[0] >= best[0] - 0.005:
                chosen, best = rest, sc
        if not chosen or best[0] < 0.12:
            result["notes"].append(f"Your {side} entries don't share a clear pattern among the "
                                   f"{len(feats)} conditions checked. Add notes on why you entered, or take more trades.")
            continue
        # describe each condition: how often it held at your entries vs on all bars
        for key in chosen:
            f = feats[key]
            c = BY_KEY[key]
            if c.kind == "event":
                win = np.zeros(n, dtype=bool)
                for k in range(TOLERANCE + 1):
                    win[k:] |= f[:n - k] if k else f
                at_entries = float(win[entries].mean())
            else:
                at_entries = float(f[entries].mean())
            info["conditions"].append({"key": key, "label": c.label, "expr": c.expr, "kind": c.kind,
                                       "at_your_entries": round(at_entries, 3), "on_all_bars": round(float(f.mean()), 3)})
        info["found"] = True
        info["f1"] = round(best[0], 3)
        info["reproduced"] = best[1]
        info["signals_in_seen_bars"] = best[3]

        # stop: median distance in ATRs; target: median R
        k_atr = [abs(t["entry_price"] - t["sl"]) / atr[pos_of[int(t["entry_time"])]]
                 for t in ts if t.get("sl") and t.get("entry_price") and atr[pos_of[int(t["entry_time"])]] > 0]
        r_mult = [abs(t["tp"] - t["entry_price"]) / abs(t["entry_price"] - t["sl"])
                  for t in ts if t.get("sl") and t.get("tp") and t.get("entry_price") and t["entry_price"] != t["sl"]]
        held = [pos_of[int(t["exit_time"])] - pos_of[int(t["entry_time"])] for t in ts
                if t.get("exit_time") and int(t["exit_time"]) in pos_of and (t.get("exit_by") or "").lower() in ("close", "manual")]
        sl_atr = _round_to(float(np.median(k_atr)), 0.25, 0.25, 10.0) if k_atr else 1.5
        info["stop"] = {"atr_multiple": sl_atr, "from_trades": len(k_atr)}
        if not k_atr:
            result["notes"].append(f"You didn't set stops on your {side} trades, so the card uses 1.5 × ATR(14). Edit sl_atr to change it.")
        spec = {"when": f"{side}_setup and not {side}_setup[1]", "sl_dist": f"{side}_sl_atr * atr(14)"}
        params = {f"{side}_sl_atr": sl_atr}
        if r_mult and len(r_mult) * 2 >= len(ts):
            tp_r = _round_to(float(np.median(r_mult)), 0.25, 0.25, 20.0)
            params[f"{side}_tp_r"] = tp_r
            spec["tp_r"] = f"{side}_tp_r"
            info["target"] = {"r_multiple": tp_r, "from_trades": len(r_mult)}
        if held and len(held) * 2 >= len(ts):
            info["max_bars"] = int(max(1, round(float(np.median(held)))))
        info["params"] = params
        card_vars[f"{side}_setup"] = " and ".join(f"({BY_KEY[k].expr})" if " and " in BY_KEY[k].expr else BY_KEY[k].expr
                                                  for k in chosen)
        sides[side] = spec
        for k in chosen:
            for m in re.finditer(r"(ema|sma)\(close, (\d+)\)", BY_KEY[k].expr):
                plots.setdefault(f"{m.group(1).upper()} {m.group(2)}", m.group(0))

    if not sides:
        result["card"] = None
        return result

    lots = [float(t["lots"]) for t in trades]
    held_all = [s.get("max_bars") for s in result["sides"].values() if s.get("max_bars")]
    period = f"{pd.Timestamp(min(t['entry_time'] for t in trades), unit='s'):%d %b %Y} to " \
             f"{pd.Timestamp(max(t['entry_time'] for t in trades), unit='s'):%d %b %Y}"
    title = name or f"My replay trades ({timeframe})"
    notes = [t["note"] for t in trades if t.get("note")]
    params, labels = {}, {}
    for side in sides:
        for k, v in result["sides"][side]["params"].items():
            params[k] = v
            labels[k] = (f"{side.title()} stop distance (× ATR 14)" if k.endswith("sl_atr")
                         else f"{side.title()} target (multiple of risk)")
    card = {
        "name": title,
        "description": (f"Learned from {len(trades)} trades you placed in bar replay on {timeframe}, {period}. "
                        + " ".join(f"{s.title()}: " + "; ".join(c["label"] for c in result["sides"][s]["conditions"]) + "."
                                   for s in sides)),
        "timeframe": timeframe,
        "evidence": "Your idea: learned from your own replay trades. Check it on data you didn't trade on.",
        "tags": ["learned", "replay"],
        "params": params,
        "labels": labels,
        "vars": card_vars,
        **{s: sides[s] for s in sides},
        "settings": {"qty_type": "lots", "qty_value": round(float(np.median(lots)), 2)},
    }
    if held_all:
        card["exit"] = {"max_bars": int(max(held_all))}
    if plots:
        card["plots"] = dict(list(plots.items())[:6])
    if notes:
        card["notes"] = "Your notes while trading: " + " | ".join(notes[:20])
    header = ("# Learned from your replay trades by goldlab. Each line under vars: is a condition that was true\n"
              "# at most of your entries. Edit freely: it is a normal strategy card.\n")
    result["card"] = header + yaml.safe_dump(card, sort_keys=False, allow_unicode=True, width=110)
    result["name"] = title
    return result


def reproduction(df: pd.DataFrame, card_text: str, trades: list[dict], seen: list[tuple[int, int]]) -> dict:
    """Run the learned card over the bars you replayed and count how many of your entries it repeats."""
    from .engine import Settings, run
    from .rules import RuleStrategy

    card = yaml.safe_load(card_text)
    secs = df.index.as_unit("s").asi8
    a = min(int(s) for s, _ in seen)
    b = max(int(e) for _, e in seen)
    lo = max(0, int(np.searchsorted(secs, a)) - 300)       # warm-up for the indicators
    hi = int(np.searchsorted(secs, b, side="right"))
    sub = df.iloc[lo:hi]
    sub.attrs = dict(df.attrs)
    res = run(RuleStrategy(card), sub, Settings.realistic(**card.get("settings", {})))
    sub_secs = sub.index.as_unit("s").asi8
    start = int(np.searchsorted(sub_secs, a))
    card_entries = {"long": [], "short": []}
    if len(res.trades):
        for row in res.trades.itertuples(index=False):
            if int(row.entry_bar) >= start:
                card_entries[row.side].append(int(row.entry_bar) - 1)   # signal bar: entries fill on the next bar
    for t in res.open_trades:
        bar = int(np.searchsorted(sub_secs, int(pd.Timestamp(t["entry_time"]).timestamp())))
        if bar >= start:
            card_entries["long" if t["side"] in ("long", 1) else "short"].append(bar - 1)
    pos = {int(s): i for i, s in enumerate(sub_secs)}
    matched, total = 0, 0
    for side in ("long", "short"):
        mine = sorted(pos[int(t["entry_time"])] for t in trades if t["side"] == side and int(t["entry_time"]) in pos)
        theirs = np.array(sorted(card_entries[side]))
        total += len(mine)
        for e in mine:
            if len(theirs) and np.any((theirs >= e - TOLERANCE) & (theirs <= e + 1)):
                matched += 1
    n_card = len(card_entries["long"]) + len(card_entries["short"])
    return {"your_entries": total, "reproduced": matched, "card_entries": n_card}


def summary_line(m: dict) -> str:
    pf = m.get("profit_factor")
    return (f"{m.get('total_trades', 0)} trades, net {'+' if (m.get('net_profit') or 0) >= 0 else '-'}"
            f"${abs(m.get('net_profit') or 0):,.0f}, profit factor {'n/a' if pf is None or not math.isfinite(pf) else f'{pf:.2f}'}")
