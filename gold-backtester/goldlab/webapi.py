"""JSON API behind the website's backtester (Vercel function api/lab.py and `goldlab serve`).

Operations (POST JSON, or GET for `strategies`):
  strategies  list the strategy cards in strategies/ and strategies/examples/
  backtest    run a card (by id or pasted YAML) with parameter and cost overrides
  validate    the readiness checklist for the same request
  pine        Pine Script v6 for a card
  bars        raw bars (with spread and swap rollovers) for bar replay
  manual      re-run trades placed by hand in replay through the engine
  learn       turn those trades into a strategy card

Only YAML strategy cards are accepted from the web (parsed with yaml.safe_load and a
whitelisted expression language). Requests are size- and range-limited so a public
page cannot run arbitrary code or tie the server up.
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, fields
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .api import FROM_SAMPLE, ROOT, get_data
from .engine import Settings, run
from .journal import slugify
from .rules import RuleError, RuleStrategy

MAX_YAML = 20_000
MAX_BODY = 200_000
MAX_BARS = 150_000
MAX_CANDLES = 30_000
MAX_TRADES = 3_000
MAX_EQUITY_POINTS = 2_000
TIMEFRAMES = ["5m", "15m", "30m", "1h", "4h", "1d"]
DEFAULT_LOOKBACK_DAYS = {"5m": 90, "15m": 180, "30m": 365, "1h": 730, "4h": None, "1d": None}
SETTING_KEYS = {"initial_capital", "qty_type", "qty_value", "commission_type", "commission_value", "slippage_ticks",
                "spread_mode", "spread_fixed", "swap_long", "swap_short", "margin_percent", "pyramiding",
                "intrabar", "process_orders_on_close"}

_DATA_CACHE: dict = {}


class ApiError(ValueError):
    pass


# --------------------------------------------------------------------------- helpers

def _num(v):
    if v is None:
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        v = float(v)
        return None if (math.isnan(v) or math.isinf(v)) else round(v, 6)
    return v


def _ts(t) -> int:
    return int(pd.Timestamp(t).timestamp())


def _card_files() -> list[Path]:
    mine = sorted((ROOT / "strategies").glob("*.yaml"))
    return mine + sorted((ROOT / "strategies" / "examples").glob("*.yaml"))


def _data(tf: str) -> pd.DataFrame:
    if tf not in _DATA_CACHE:
        _DATA_CACHE[tf] = get_data(tf)
    return _DATA_CACHE[tf]


def _evidence_level(text: str | None) -> str:
    t = (text or "").strip().lower()
    if t.startswith("peer-reviewed"):
        return "Peer-reviewed"
    if t.startswith("folklore"):
        return "Folklore"
    if "peer-reviewed" in t:
        return "Partly supported"
    return "Weak or indirect" if t else "Your idea"


def _strategy_from(req: dict) -> RuleStrategy:
    params = req.get("params") or {}
    if not isinstance(params, dict):
        raise ApiError("params must be an object")
    if req.get("card"):
        text = str(req["card"])
        if len(text) > MAX_YAML:
            raise ApiError(f"Strategy card is too long (max {MAX_YAML:,} characters)")
        try:
            card = yaml.safe_load(text)
        except yaml.YAMLError as e:
            raise ApiError(f"YAML error: {e}") from None
        if not isinstance(card, dict):
            raise ApiError("A strategy card must be a YAML mapping (name:, long:, ...)")
    else:
        sid = str(req.get("strategy", ""))
        files = {p.stem: p for p in _card_files()}
        if sid not in files:
            raise ApiError(f"Unknown strategy '{sid}'")
        card = yaml.safe_load(files[sid].read_text())
    known = set((card.get("params") or {}))
    clean = {}
    for k, v in params.items():
        if k not in known:
            raise ApiError(f"Unknown parameter '{k}'")
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v):
            raise ApiError(f"Parameter '{k}' must be a number")
        base = card["params"][k]
        clean[k] = int(round(v)) if isinstance(base, int) and not isinstance(base, bool) else float(v)
    try:
        return RuleStrategy(card, **clean)
    except (RuleError, TypeError, ValueError) as e:
        raise ApiError(str(e)) from None


def _settings(s: RuleStrategy, req: dict) -> Settings:
    preset = req.get("preset", "realistic")
    over = dict(req.get("settings") or {})
    bad = set(over) - SETTING_KEYS
    if bad:
        raise ApiError(f"Unknown settings: {sorted(bad)}")
    card = {k: v for k, v in (s.card.get("settings") or {}).items() if k in {f.name for f in fields(Settings)}}
    base = {**card, **{k: v for k, v in over.items() if v is not None}}
    if preset == "tradingview":
        keep = {k: v for k, v in base.items() if k.startswith("qty") or k in ("initial_capital", "pyramiding")}
        st = Settings.tradingview(**keep)
    elif preset == "realistic":
        st = Settings.realistic(**base)
    else:
        raise ApiError("preset must be realistic or tradingview")
    if not (100 <= st.initial_capital <= 100_000_000):
        raise ApiError("Account size must be between $100 and $100,000,000")
    if st.qty_type not in ("lots", "units", "cash", "percent_of_equity", "risk_percent"):
        raise ApiError("Unknown sizing type")
    if st.qty_value <= 0 or (st.qty_type == "risk_percent" and st.qty_value > 20):
        raise ApiError("Size must be positive (risk % at most 20)")
    if st.intrabar not in ("tv", "pessimistic"):
        raise ApiError("intrabar must be tv or pessimistic")
    return st


def _window(req: dict, s: RuleStrategy):
    tf = req.get("timeframe") or s.timeframe or "1h"
    if tf not in TIMEFRAMES or tf not in FROM_SAMPLE:
        raise ApiError(f"Timeframe must be one of {TIMEFRAMES}")
    df = _data(tf)
    start, end = req.get("start"), req.get("end")
    if start:
        df = df[df.index >= pd.Timestamp(start, tz="UTC")]
    elif DEFAULT_LOOKBACK_DAYS.get(tf):
        df = df[df.index >= df.index[-1] - pd.Timedelta(days=DEFAULT_LOOKBACK_DAYS[tf])]
    if end:
        df = df[df.index < pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)]
    if len(df) < 50:
        raise ApiError("Not enough bars in that date range (need at least 50)")
    if len(df) > MAX_BARS:
        raise ApiError(f"Too many bars ({len(df):,}); pick a shorter range or a higher timeframe")
    full = _data(tf)
    df.attrs = dict(full.attrs, timeframe=tf)
    return tf, df


def _side_stats(trades: pd.DataFrame) -> dict:
    out = {}
    for label, t in (("all", trades), ("long", trades[trades["side"] == "long"] if len(trades) else trades),
                     ("short", trades[trades["side"] == "short"] if len(trades) else trades)):
        p = t["pnl"].to_numpy(float) if len(t) else np.array([])
        w, l = p[p > 0], p[p < 0]
        out[label] = {k: _num(v) for k, v in {
            "net_profit": p.sum(), "gross_profit": w.sum(), "gross_loss": -l.sum(),
            "profit_factor": (w.sum() / -l.sum()) if len(l) else None, "trades": len(p),
            "win_rate": (p > 0).mean() * 100 if len(p) else None, "avg_trade": p.mean() if len(p) else None,
            "avg_win": w.mean() if len(w) else None, "avg_loss": -l.mean() if len(l) else None,
            "largest_win": w.max() if len(w) else None, "largest_loss": -l.min() if len(l) else None,
            "avg_bars": t["bars"].mean() if len(t) else None,
            "commission": t["commission"].sum() if len(t) else 0.0}.items()}
    return out


def _monthly(equity: pd.Series, initial: float) -> list:
    idx = equity.index.tz_convert(None)
    m = pd.Series(equity.to_numpy(), index=idx).groupby(idx.to_period("M")).last()
    m = pd.concat([pd.Series([initial], index=[m.index[0] - 1]), m])
    r = m.pct_change().dropna() * 100
    return [{"month": str(k), "ret": _num(v)} for k, v in r.items()]


# --------------------------------------------------------------------------- operations

def op_strategies(_req: dict | None = None) -> dict:
    items = []
    for p in _card_files():
        card = yaml.safe_load(p.read_text())
        items.append({
            "id": p.stem, "name": card.get("name", p.stem), "timeframe": card.get("timeframe", "1h"),
            "description": (card.get("description") or "").strip(), "evidence": card.get("evidence"),
            "evidence_level": _evidence_level(card.get("evidence")), "tags": card.get("tags", []),
            "params": card.get("params") or {}, "labels": card.get("labels") or {}, "settings": card.get("settings") or {},
            "mine": p.parent.name == "strategies", "yaml": p.read_text(),
            "report": f"/strategies/{slugify(card.get('name', p.stem))}.html",
        })
    ranges = {}
    for tf in TIMEFRAMES:
        try:
            d = _data(tf)
            ranges[tf] = {"start": str(d.index[0].date()), "end": str(d.index[-1].date()), "bars": len(d),
                          "default_days": DEFAULT_LOOKBACK_DAYS.get(tf)}
        except Exception:
            pass
    return {"strategies": items, "timeframes": TIMEFRAMES, "data": ranges,
            "defaults": {"realistic": asdict(Settings.realistic()), "tradingview": asdict(Settings.tradingview())}}


def _trade_rows(trades: pd.DataFrame) -> list:
    tr = []
    for row in trades.iloc[-MAX_TRADES:].itertuples(index=False):
        tr.append({"n": int(row.trade), "side": row.side, "entry_time": _ts(row.entry_time),
                   "entry_price": _num(row.entry_price), "exit_time": _ts(row.exit_time),
                   "exit_price": _num(row.exit_price), "exit_id": str(row.exit_id),
                   "exit_kind": str(getattr(row, "exit_kind", "") or ""), "lots": _num(row.lots),
                   "pnl": _num(row.pnl), "pnl_pct": _num(row.pnl_pct), "runup": _num(row.runup),
                   "drawdown": _num(row.drawdown), "bars": int(row.bars), "cum_pnl": _num(row.cum_pnl),
                   "commission": _num(row.commission), "r": _num(getattr(row, "r", None)),
                   "risk": _num(getattr(row, "risk", None)), "comment": str(getattr(row, "comment", "") or "")})
    return tr


def _payload(s, st: Settings, tf: str, df: pd.DataFrame, res, t0: float, req: dict, strategy: dict) -> dict:
    """The JSON the website draws: metrics, trades, candles, equity, monthly returns."""
    from .validate import return_stats
    res.metrics.update(return_stats(res))
    trades = res.trades
    n = len(trades)
    max_c = int(min(req.get("max_candles") or MAX_CANDLES, MAX_CANDLES))
    shown = df.iloc[-max_c:]
    secs = shown.index.as_unit("s").asi8  # unit-safe: indexes may be stored in ns or us
    vol = shown["volume"].round(3) if "volume" in shown else pd.Series(0.0, index=shown.index)
    candles = np.column_stack([secs, shown["open"].round(2), shown["high"].round(2),
                               shown["low"].round(2), shown["close"].round(2), vol]).tolist()
    candles = [[int(c[0])] + c[1:] for c in candles]
    plots = {}
    for name, ser in (res.strategy.plots or {}).items():
        ser = ser.reindex(shown.index)
        ok = ser.notna().to_numpy()
        plots[name] = [[int(t), round(float(v), 3)] for t, v in zip(secs[ok], ser.to_numpy()[ok])]
    eq = res.equity
    step = max(1, len(eq) // MAX_EQUITY_POINTS)
    e = eq.iloc[::step]
    if e.index[-1] != eq.index[-1]:
        e = pd.concat([e, eq.iloc[-1:]])
    peak = np.maximum.accumulate(eq.to_numpy(float))
    dd = (eq.to_numpy(float) - peak) / peak * 100
    dd_s = pd.Series(dd, index=eq.index).loc[e.index]
    first_close = float(df["close"].iloc[0])
    bh = st.initial_capital * df["close"].loc[e.index] / first_close
    a = df.attrs
    return {
        "strategy": strategy,
        "data": {"symbol": "XAUUSD", "timeframe": tf, "source": a.get("source"), "start": str(df.index[0]),
                 "end": str(df.index[-1]), "bars": len(df), "candles_shown": len(shown)},
        "settings": {k: _num(v) for k, v in asdict(st).items()},
        "metrics": {k: _num(v) for k, v in res.metrics.items()},
        "sides": _side_stats(trades) if n else {},
        "trades": _trade_rows(trades) if n else [], "trades_total": n, "trades_truncated": n > MAX_TRADES,
        "open_trades": [{**t, "entry_time": _ts(t["entry_time"]), "entry_price": _num(t["entry_price"])}
                        for t in res.open_trades],
        "candles": candles, "plots": plots,
        "equity": [[_ts(t), _num(v)] for t, v in e.items()],
        "drawdown": [[_ts(t), _num(v)] for t, v in dd_s.items()],
        "buyhold": [[_ts(t), _num(v)] for t, v in bh.items()],
        "monthly": _monthly(eq, st.initial_capital),
        "elapsed_ms": int((time.time() - t0) * 1000),
    }


def op_backtest(req: dict) -> dict:
    t0 = time.time()
    s = _strategy_from(req)
    st = _settings(s, req)
    tf, df = _window(req, s)
    res = run(s, df, st)
    info = {"name": s.name, "description": s.description, "timeframe": tf, "params": vars(s.p),
            "labels": dict(s.card.get("labels") or {}),
            "evidence": s.card.get("evidence"), "evidence_level": _evidence_level(s.card.get("evidence")),
            "fingerprint": s.fingerprint()}
    return _payload(s, st, tf, df, res, t0, req, info)


def op_validate(req: dict) -> dict:
    t0 = time.time()
    s = _strategy_from(req)
    st = _settings(s, req)
    tf, df = _window(req, s)
    from .validate import validate
    v = validate(s, df, st, journal=None, quick=len(df) > 40_000, mc_runs=2000)
    return {"verdict": v["verdict"], "headline": v["headline"],
            "checks": [{k: (str(x) if k == "value" else x) for k, x in c.items()} for c in v["checks"]],
            "monte_carlo": {k: _num(x) for k, x in (v.get("monte_carlo") or {}).items()},
            "deflated_sharpe": _num(v.get("deflated_sharpe")), "quick": len(df) > 40_000,
            "elapsed_ms": int((time.time() - t0) * 1000)}


def op_pine(req: dict) -> dict:
    from .pine import to_pine
    s = _strategy_from(req)
    try:
        return {"pine": to_pine(s)}
    except RuleError as e:
        raise ApiError(str(e)) from None


def _tf(req: dict) -> str:
    tf = req.get("timeframe")
    if tf not in TIMEFRAMES or tf not in FROM_SAMPLE:
        raise ApiError(f"Timeframe must be one of {TIMEFRAMES}")
    return tf


def _unix(v, what: str) -> int:
    if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v):
        return int(v)
    if isinstance(v, str) and v:
        try:
            return int(pd.Timestamp(v, tz="UTC").timestamp())
        except ValueError:
            pass
    raise ApiError(f"{what} must be a date (YYYY-MM-DD) or a unix time")


_ROLL_CACHE: dict = {}


def _rollovers(tf: str) -> np.ndarray:
    """Swap rollovers per bar for the whole timeframe, computed exactly as the broker does."""
    if tf not in _ROLL_CACHE:
        from .engine.broker import Broker
        _ROLL_CACHE[tf] = Broker(_data(tf), Settings()).rollovers
    return _ROLL_CACHE[tf]


def op_bars(req: dict) -> dict:
    """Bars for bar replay, at full precision so the browser fills trades exactly like the engine."""
    tf = _tf(req)
    df = _data(tf)
    secs = df.index.as_unit("s").asi8
    at = _unix(req.get("at"), "at")
    before = int(min(max(int(req.get("before", 300)), 0), 2000))
    after = int(min(max(int(req.get("after", 3000)), 1), 8000))
    i0 = int(np.searchsorted(secs, at))
    if i0 >= len(df):
        raise ApiError("There are no bars after that time on this timeframe")
    lo, hi = max(0, i0 - before), min(len(df), i0 + after)
    sub = df.iloc[lo:hi]
    vol = sub["volume"] if "volume" in sub else pd.Series(0.0, index=sub.index)
    spread = sub["spread"].fillna(0) if "spread" in sub else pd.Series(0.0, index=sub.index)
    return {"timeframe": tf, "index": i0 - lo, "first": lo == 0, "last": hi == len(df),
            "t": [int(x) for x in secs[lo:hi]], "o": sub["open"].tolist(), "h": sub["high"].tolist(),
            "l": sub["low"].tolist(), "c": sub["close"].tolist(), "v": vol.round(3).tolist(),
            "sp": spread.tolist(), "roll": [int(x) for x in _rollovers(tf)[lo:hi]],
            "data": {"start": str(df.index[0].date()), "end": str(df.index[-1].date())}}


def _manual_window(req: dict, tf: str, trades: list[dict]):
    df = _data(tf)
    secs = df.index.as_unit("s").asi8
    start = _unix(req.get("start_time"), "start_time")
    end = _unix(req.get("end_time"), "end_time")
    if end < start:
        raise ApiError("end_time is before start_time")
    for t in trades:
        times = [t["entry_time"]] + ([t["exit_time"]] if t["exit_time"] else []) + [m["time"] for m in t["mods"]]
        if min(times) < start or max(times) > end:
            raise ApiError("Every trade must fall inside the session's start and end time")
    lo, hi = int(np.searchsorted(secs, start)), int(np.searchsorted(secs, end, side="right"))
    if hi - lo < 2:
        raise ApiError("The session is too short to review (need at least 2 bars)")
    if hi - lo > MAX_BARS:
        raise ApiError(f"The session covers too many bars ({hi - lo:,}); review a shorter stretch")
    sub = df.iloc[lo:hi]
    sub.attrs = dict(df.attrs, timeframe=tf)
    return sub


def op_manual(req: dict) -> dict:
    """Results for trades placed by hand in bar replay, with the same costs and rules as a backtest."""
    from .manual import ManualError, ManualStrategy, clean_trades
    t0 = time.time()
    tf = _tf(req)
    try:
        trades = clean_trades(req.get("trades") or [])
        if not trades:
            raise ApiError("There are no trades to review yet. Buy or sell in replay first.")
        df = _manual_window(req, tf, trades)
        s = ManualStrategy(trades, name=str(req.get("name") or "")[:80] or None)
        st = _settings(s, req)
        st.process_orders_on_close = True    # you decided at the bar's close, so that is where the order fills
        st.pyramiding = 1
        res = run(s, df, st)
    except ManualError as e:
        raise ApiError(str(e)) from None
    info = {"name": s.name, "description": f"{len(trades)} trades you placed by hand in bar replay.", "timeframe": tf,
            "params": {}, "labels": {}, "evidence": None, "evidence_level": "Your trades",
            "fingerprint": s.fingerprint(), "manual": True}
    return _payload(s, st, tf, df, res, t0, req, info)


def op_learn(req: dict) -> dict:
    """Find the chart conditions behind manual trades and write them up as a strategy card."""
    from .learn import learn, reproduction
    from .manual import ManualError, clean_trades
    t0 = time.time()
    tf = _tf(req)
    try:
        trades = clean_trades(req.get("trades") or [])
    except ManualError as e:
        raise ApiError(str(e)) from None
    if len(trades) < 3:
        raise ApiError("Take at least 3 trades in replay before building a strategy from them.")
    if any(t["entry_price"] is None for t in trades):
        raise ApiError("Each trade needs its entry_price")
    seen = req.get("seen") or []
    if not isinstance(seen, list) or len(seen) > 100:
        raise ApiError("seen must be a list of [start, end] time ranges")
    seen = [(_unix(a, "seen start"), _unix(b, "seen end")) for a, b in seen] or \
        [(min(t["entry_time"] for t in trades), max((t["exit_time"] or t["entry_time"]) for t in trades))]
    df = _data(tf)
    secs = df.index.as_unit("s").asi8
    lo = max(0, int(np.searchsorted(secs, min(a for a, _ in seen))) - 2500)   # warm-up and a base rate sample
    hi = int(np.searchsorted(secs, max(b for _, b in seen), side="right")) + 1
    if hi - lo > MAX_BARS:
        raise ApiError("These sessions span too many bars; learn from fewer sessions at a time")
    sub = df.iloc[lo:hi]
    sub.attrs = dict(df.attrs, timeframe=tf)
    try:
        out = learn(sub, trades, seen, tf, name=str(req.get("name") or "")[:80] or None)
    except ValueError as e:
        raise ApiError(str(e)) from None
    if out.get("card"):
        out["reproduction"] = reproduction(sub, out["card"], trades, seen)
        card = yaml.safe_load(out["card"])
        s = RuleStrategy(card)
        st = Settings.realistic(**(card.get("settings") or {}))
        _, dfw = _window({"timeframe": tf}, s)
        res = run(s, dfw, st)
        m = res.metrics
        out["backtest"] = {"start": str(dfw.index[0].date()), "end": str(dfw.index[-1].date()),
                           **{k: _num(m.get(k)) for k in ("net_profit", "total_trades", "profit_factor",
                                                         "max_drawdown_pct", "percent_profitable")}}
    out["elapsed_ms"] = int((time.time() - t0) * 1000)
    return out


OPS = {"strategies": op_strategies, "backtest": op_backtest, "validate": op_validate, "pine": op_pine,
       "bars": op_bars, "manual": op_manual, "learn": op_learn}


def handle(op: str, req: dict | None) -> tuple[int, dict]:
    """Returns (http_status, json_body)."""
    if op not in OPS:
        return 404, {"error": f"Unknown operation '{op}'"}
    try:
        return 200, OPS[op](req or {})
    except (ApiError, RuleError) as e:
        return 400, {"error": str(e)}
    except (KeyError, TypeError, ValueError, ZeroDivisionError, OverflowError) as e:
        return 400, {"error": f"Could not run this strategy: {e}"}
    except RecursionError:
        return 400, {"error": "Expression is too deeply nested"}


GET_OPS = {"strategies"}


def route(method: str, op: str, raw: bytes | None = None) -> tuple[int, dict]:
    """HTTP rules shared by the Vercel function and the local preview server."""
    if op not in OPS:
        return 404, {"error": f"Unknown operation '{op}'"}
    if method == "GET":
        if op not in GET_OPS:
            return 405, {"error": "Use POST for this operation"}
        return handle(op, None)
    if method != "POST":
        return 405, {"error": "Use GET or POST"}
    if raw and len(raw) > MAX_BODY:
        return 413, {"error": "Request too large"}
    try:
        req = json.loads(raw or b"{}")
    except ValueError:
        return 400, {"error": "Body must be JSON"}
    if not isinstance(req, dict):
        return 400, {"error": "Body must be a JSON object"}
    return handle(op, req)
