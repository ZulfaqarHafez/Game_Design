"""JSON API behind the website's backtester (Vercel function api/lab.py and `goldlab serve`).

Operations (POST JSON, or GET for `strategies`):
  strategies  list the strategy cards in strategies/ and strategies/examples/
  backtest    run a card (by id or pasted YAML) with parameter and cost overrides
  validate    the readiness checklist for the same request
  pine        Pine Script v6 for a card

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
MAX_BODY = 64_000
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


def op_backtest(req: dict) -> dict:
    t0 = time.time()
    s = _strategy_from(req)
    st = _settings(s, req)
    tf, df = _window(req, s)
    res = run(s, df, st)
    from .validate import return_stats
    res.metrics.update(return_stats(res))
    trades = res.trades
    n = len(trades)
    tr = []
    if n:
        sub = trades.iloc[-MAX_TRADES:]
        for row in sub.itertuples(index=False):
            tr.append({"n": int(row.trade), "side": row.side, "entry_time": _ts(row.entry_time),
                       "entry_price": _num(row.entry_price), "exit_time": _ts(row.exit_time),
                       "exit_price": _num(row.exit_price), "exit_id": str(row.exit_id), "lots": _num(row.lots),
                       "pnl": _num(row.pnl), "pnl_pct": _num(row.pnl_pct), "runup": _num(row.runup),
                       "drawdown": _num(row.drawdown), "bars": int(row.bars), "cum_pnl": _num(row.cum_pnl),
                       "commission": _num(row.commission), "r": _num(getattr(row, "r", None)),
                       "risk": _num(getattr(row, "risk", None))})
    max_c = int(min(req.get("max_candles") or MAX_CANDLES, MAX_CANDLES))
    shown = df.iloc[-max_c:]
    secs = shown.index.as_unit("s").asi8  # unit-safe: indexes may be stored in ns or us
    candles = np.column_stack([secs, shown["open"].round(2), shown["high"].round(2),
                               shown["low"].round(2), shown["close"].round(2)]).tolist()
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
        "strategy": {"name": s.name, "description": s.description, "timeframe": tf, "params": vars(s.p),
                     "labels": dict(s.card.get("labels") or {}),
                     "evidence": s.card.get("evidence"), "evidence_level": _evidence_level(s.card.get("evidence")),
                     "fingerprint": s.fingerprint()},
        "data": {"symbol": "XAUUSD", "timeframe": tf, "source": a.get("source"), "start": str(df.index[0]),
                 "end": str(df.index[-1]), "bars": len(df), "candles_shown": len(shown)},
        "settings": {k: _num(v) for k, v in asdict(st).items()},
        "metrics": {k: _num(v) for k, v in res.metrics.items()},
        "sides": _side_stats(trades) if n else {},
        "trades": tr, "trades_total": n, "trades_truncated": n > MAX_TRADES,
        "open_trades": [{**t, "entry_time": _ts(t["entry_time"]), "entry_price": _num(t["entry_price"])}
                        for t in res.open_trades],
        "candles": candles, "plots": plots,
        "equity": [[_ts(t), _num(v)] for t, v in e.items()],
        "drawdown": [[_ts(t), _num(v)] for t, v in dd_s.items()],
        "buyhold": [[_ts(t), _num(v)] for t, v in bh.items()],
        "monthly": _monthly(eq, st.initial_capital),
        "elapsed_ms": int((time.time() - t0) * 1000),
    }


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


OPS = {"strategies": op_strategies, "backtest": op_backtest, "validate": op_validate, "pine": op_pine}


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
