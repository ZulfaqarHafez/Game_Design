"""Strategy cards: describe a strategy in YAML instead of Python.

A card is a plain-text record of a strategy idea that the engine can run,
the journal can version, and goldlab.pine can turn into Pine Script.

    name: EMA trend with ATR stop
    timeframe: 4h
    params: {fast: 50, slow: 200, atr_mult: 3}
    vars:
      trend_up: ema(close, fast) > ema(close, slow)
    long:
      when: crossover(ema(close, fast), ema(close, slow))
      sl_dist: atr_mult * atr(14)
    short:
      when: crossunder(ema(close, fast), ema(close, slow))
      sl_dist: atr_mult * atr(14)

Expressions use Python syntax restricted to a safe whitelist (no imports,
attributes or arbitrary calls): arithmetic, comparisons, and/or/not,
`a if cond else b`, `x[1]` for the previous bar, and the functions in FUNCS.

Live state names (evaluated bar by bar): position (+1 long, -1 short, 0 flat),
is_long, is_short, is_flat, bars_in_trade, entry_price, trades_today, open_profit.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
import yaml

from . import indicators as ta
from .data.resample import MINUTES, resample
from .strategy import Strategy

DYNAMIC = {"position", "is_long", "is_short", "is_flat", "bars_in_trade", "entry_price",
           "trades_today", "open_profit"}


class RuleError(ValueError):
    pass


def _ser(x, index) -> pd.Series:
    if isinstance(x, pd.Series):
        return x
    if np.isscalar(x):
        return pd.Series(np.full(len(index), x, dtype=float if not isinstance(x, bool) else bool), index=index)
    return pd.Series(np.asarray(x), index=index)


def _security(ctx: "Context", tf: str, expr: str):
    """Value of `expr` on a higher timeframe, from the last COMPLETED higher-timeframe bar.

    Equivalent to request.security(..., expr[1], lookahead=barmerge.lookahead_on): no repainting.
    """
    if tf not in MINUTES:
        raise RuleError(f"security(): unknown timeframe {tf!r}")
    df = ctx.df
    htf = resample(df[[c for c in ("open", "high", "low", "close", "volume", "spread") if c in df]], tf)
    sub = Context(htf, ctx.params, {})
    val = _ser(sub.eval_static(expr), htf.index)
    if tf in ("1d", "1w"):
        # daily bars are labelled by session date; they end at 17:00 New York that date
        ends = (htf.index.tz_convert(None) + pd.Timedelta(hours=17)).tz_localize("America/New_York").tz_convert("UTC")
        if tf == "1w":
            ends = ends + pd.Timedelta(days=6)
    else:
        ends = htf.index + pd.Timedelta(minutes=MINUTES[tf])
    s = pd.Series(val.to_numpy(), index=ends)
    s = s[~s.index.duplicated(keep="last")].sort_index()
    pos = np.searchsorted(s.index.values, df.index.values, side="right") - 1
    out = np.where(pos >= 0, s.to_numpy(dtype=float)[np.clip(pos, 0, None)], np.nan)
    return pd.Series(out, index=df.index)


def _funcs(ctx: "Context") -> dict[str, Callable]:
    d = ctx.df
    o, h, l, c = d["open"], d["high"], d["low"], d["close"]
    v = d["volume"] if "volume" in d else pd.Series(1.0, index=d.index)
    idx = d.index
    S = lambda x: _ser(x, idx)
    return {
        # moving averages and oscillators
        "sma": lambda src, n: ta.sma(S(src), n), "ema": lambda src, n: ta.ema(S(src), n),
        "rma": lambda src, n: ta.rma(S(src), n), "wma": lambda src, n: ta.wma(S(src), n),
        "hma": lambda src, n: ta.hma(S(src), n), "vwma": lambda src, n: ta.vwma(S(src), v, n),
        "rsi": lambda src, n=14: ta.rsi(S(src), n), "stdev": lambda src, n: ta.stdev(S(src), n),
        "atr": lambda n=14: ta.atr(h, l, c, n), "tr": lambda: ta.tr(h, l, c),
        "highest": lambda src, n: ta.highest(S(src), n), "lowest": lambda src, n: ta.lowest(S(src), n),
        "change": lambda src, n=1: ta.change(S(src), n), "roc": lambda src, n: ta.roc(S(src), n),
        "mom": lambda src, n: ta.change(S(src), n), "cci": lambda n=20: ta.cci((h + l + c) / 3, n),
        "stoch": lambda n=14, smooth=1: ta.sma(ta.stoch(c, h, l, n), smooth),
        "bb_mid": lambda src, n=20, mult=2.0: ta.bb(S(src), n, mult)[0],
        "bb_upper": lambda src, n=20, mult=2.0: ta.bb(S(src), n, mult)[1],
        "bb_lower": lambda src, n=20, mult=2.0: ta.bb(S(src), n, mult)[2],
        "kc_upper": lambda n=20, mult=1.5: ta.keltner(h, l, c, n, mult)[1],
        "kc_lower": lambda n=20, mult=1.5: ta.keltner(h, l, c, n, mult)[2],
        "macd": lambda src, f=12, s=26, sig=9: ta.macd(S(src), f, s, sig)[0],
        "macd_signal": lambda src, f=12, s=26, sig=9: ta.macd(S(src), f, s, sig)[1],
        "macd_hist": lambda src, f=12, s=26, sig=9: ta.macd(S(src), f, s, sig)[2],
        "adx": lambda n=14: ta.adx(h, l, c, n), "plus_di": lambda n=14: ta.dmi(h, l, c, n, n)[0],
        "minus_di": lambda n=14: ta.dmi(h, l, c, n, n)[1],
        "supertrend": lambda factor=3.0, n=10: ta.supertrend(h, l, c, factor, n)[0],
        "supertrend_dir": lambda factor=3.0, n=10: ta.supertrend(h, l, c, factor, n)[1],
        "vwap": lambda: ta.vwap(h, l, c, v),
        # signals
        "crossover": lambda a, b: ta.crossover(S(a), b), "crossunder": lambda a, b: ta.crossunder(S(a), b),
        "cross": lambda a, b: ta.crossover(S(a), b) | ta.crossunder(S(a), b),
        "barssince": lambda cond: ta.barssince(S(cond).astype(bool)),
        "valuewhen": lambda cond, src, k=0: ta.valuewhen(S(cond).astype(bool), S(src), k),
        # time and sessions (times are bar OPEN times)
        "in_session": lambda window, tz="UTC": ta.in_session(idx, window, tz),
        "session_high": lambda window, tz="UTC": ta.session_range(d, window, tz)[0],
        "session_low": lambda window, tz="UTC": ta.session_range(d, window, tz)[1],
        "hour": lambda tz="UTC": ta.hour(idx, tz), "minute": lambda tz="UTC": ta.minute(idx, tz),
        "weekday": lambda tz="UTC": ta.weekday(idx, tz), "new_day": lambda: ta.new_day(idx),
        "security": lambda tf, expr: _security(ctx, tf, expr),
        # maths
        "abs": lambda x: np.abs(x), "min": lambda a, b: np.minimum(a, b), "max": lambda a, b: np.maximum(a, b),
        "nz": lambda x, val=0.0: S(x).fillna(val), "na": lambda x: S(x).isna(),
        "round": lambda x, nd=0: np.round(x, int(nd)), "sqrt": lambda x: np.sqrt(x), "log": lambda x: np.log(x),
    }


class Context:
    """Evaluates expressions against one DataFrame. Static parts are vectorised once."""

    def __init__(self, df: pd.DataFrame, params: dict, var_exprs: dict[str, str]):
        self.df = df
        self.params = dict(params)
        self.var_exprs = var_exprs
        self.cache: dict[str, Any] = {}
        self.funcs = _funcs(self)
        d = df
        self.base = {
            "open": d["open"], "high": d["high"], "low": d["low"], "close": d["close"],
            "volume": d["volume"] if "volume" in d else pd.Series(0.0, index=d.index),
            "spread": d["spread"] if "spread" in d else pd.Series(0.0, index=d.index),
            "hl2": (d["high"] + d["low"]) / 2, "hlc3": (d["high"] + d["low"] + d["close"]) / 3,
            "ohlc4": (d["open"] + d["high"] + d["low"] + d["close"]) / 4,
            "true": True, "false": False, "True": True, "False": False,
        }
        self.dyn: dict[str, Any] = {}

    # -- parsing -------------------------------------------------------
    ALLOWED = (ast.Expression, ast.BoolOp, ast.BinOp, ast.UnaryOp, ast.Compare, ast.Call, ast.Name,
               ast.Load, ast.Constant, ast.Subscript, ast.IfExp, ast.And, ast.Or, ast.Not, ast.Add, ast.Sub,
               ast.Mult, ast.Div, ast.Mod, ast.Pow, ast.USub, ast.UAdd, ast.Gt, ast.GtE, ast.Lt, ast.LtE,
               ast.Eq, ast.NotEq, ast.keyword)

    MAX_EXPR = 600          # characters per expression
    MAX_CONST = 1e9         # largest numeric literal
    MAX_LOOKBACK = 5000     # largest length / offset an indicator may use
    MATHS = {"abs", "min", "max", "nz", "na", "round", "sqrt", "log"}

    def parse(self, expr) -> ast.AST:
        if isinstance(expr, (int, float, bool)):
            expr = repr(expr)
        text = str(expr)
        if len(text) > self.MAX_EXPR:
            raise RuleError(f"Expression is too long (max {self.MAX_EXPR} characters)")
        try:
            tree = ast.parse(text, mode="eval")
        except SyntaxError as e:
            raise RuleError(f"Cannot parse expression {expr!r}: {e.msg}") from None
        for node in ast.walk(tree):
            if not isinstance(node, self.ALLOWED):
                raise RuleError(f"Not allowed in expressions: {type(node).__name__} in {expr!r}")
            if isinstance(node, ast.Call) and not isinstance(node.func, ast.Name):
                raise RuleError(f"Only plain function calls are allowed: {expr!r}")
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                if abs(node.value) > self.MAX_CONST:
                    raise RuleError(f"Number too large in {expr!r}")
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
                if not (isinstance(node.right, ast.Constant) and isinstance(node.right.value, (int, float))
                        and abs(node.right.value) <= 10):
                    raise RuleError("Powers need a fixed exponent between -10 and 10")
        return tree.body

    def is_dynamic(self, node) -> bool:
        for n in ast.walk(node):
            if isinstance(n, ast.Name):
                if n.id in DYNAMIC:
                    return True
                if n.id in self.var_exprs and self.is_dynamic(self.parse(self.var_exprs[n.id])):
                    return True
        return False

    # -- static (vectorised) evaluation ---------------------------------
    def eval_static(self, expr):
        key = expr if isinstance(expr, str) else None
        if key is not None and key in self.cache:
            return self.cache[key]
        node = self.parse(expr) if not isinstance(expr, ast.AST) else expr
        val = self._ev(node)
        if key is not None:
            self.cache[key] = val
        return val

    def _name(self, name: str):
        if name in self.params:
            return self.params[name]
        if name in self.base:
            return self.base[name]
        if name in self.var_exprs:
            if name not in self.cache:
                self.cache[name] = self.eval_static(self.var_exprs[name])
            return self.cache[name]
        if name in DYNAMIC:
            raise RuleError(f"'{name}' is live state; it can't be used inside an indicator")
        raise RuleError(f"Unknown name '{name}'. Define it under vars: or params:")

    def _ev(self, node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return self._name(node.id)
        if isinstance(node, ast.BinOp):
            a, b = self._ev(node.left), self._ev(node.right)
            op = type(node.op)
            if op is ast.Add: return a + b
            if op is ast.Sub: return a - b
            if op is ast.Mult: return a * b
            if op is ast.Div: return a / b
            if op is ast.Mod: return a % b
            if op is ast.Pow: return a ** b
        if isinstance(node, ast.UnaryOp):
            v = self._ev(node.operand)
            if isinstance(node.op, ast.Not):
                return ~_ser(v, self.df.index).fillna(False).astype(bool) if not np.isscalar(v) else (not v)
            return -v if isinstance(node.op, ast.USub) else v
        if isinstance(node, ast.BoolOp):
            vals = [self._ev(v) for v in node.values]
            out = _ser(vals[0], self.df.index).fillna(False).astype(bool)
            for v in vals[1:]:
                vv = _ser(v, self.df.index).fillna(False).astype(bool)
                out = (out & vv) if isinstance(node.op, ast.And) else (out | vv)
            return out
        if isinstance(node, ast.Compare):
            left = self._ev(node.left)
            out = None
            for op, comp in zip(node.ops, node.comparators):
                right = self._ev(comp)
                t = type(op)
                r = (left > right if t is ast.Gt else left >= right if t is ast.GtE else
                     left < right if t is ast.Lt else left <= right if t is ast.LtE else
                     left == right if t is ast.Eq else left != right)
                out = r if out is None else (out & r)
                left = right
            return out
        if isinstance(node, ast.IfExp):
            cond = _ser(self._ev(node.test), self.df.index).fillna(False).astype(bool)
            a = _ser(self._ev(node.body), self.df.index)
            b = _ser(self._ev(node.orelse), self.df.index)
            return a.where(cond, b)
        if isinstance(node, ast.Subscript):
            base = _ser(self._ev(node.value), self.df.index)
            k = self._ev(node.slice)
            if not np.isscalar(k) or int(k) < 0:
                raise RuleError("x[n] needs a fixed n >= 0 (negative n would look into the future)")
            if int(k) > self.MAX_LOOKBACK:
                raise RuleError(f"x[n]: n must be at most {self.MAX_LOOKBACK}")
            return base.shift(int(k))
        if isinstance(node, ast.Call):
            fname = node.func.id
            if fname not in self.funcs:
                raise RuleError(f"Unknown function {fname}(). Available: {', '.join(sorted(self.funcs))}")
            args = [self._ev(a) if not (fname in ("security",) and i == 1) else
                    (a.value if isinstance(a, ast.Constant) else self._ev(a)) for i, a in enumerate(node.args)]
            kwargs = {k.arg: self._ev(k.value) for k in node.keywords}
            if fname not in self.MATHS:
                for v in list(args) + list(kwargs.values()):
                    if isinstance(v, (int, float)) and not isinstance(v, bool) and (
                            not np.isfinite(v) or abs(v) > self.MAX_LOOKBACK):
                        raise RuleError(f"{fname}(): numbers must be at most {self.MAX_LOOKBACK}")
            try:
                return self.funcs[fname](*args, **kwargs)
            except TypeError as e:
                raise RuleError(f"Bad arguments to {fname}(): {e}") from None
        raise RuleError(f"Unsupported expression element {type(node).__name__}")

    # -- dynamic (per bar) evaluation -----------------------------------
    def compile(self, expr) -> Callable[[int], Any]:
        """Return f(i) -> value at bar i. Static subtrees are precomputed arrays."""
        if expr is None:
            return lambda i: None
        node = self.parse(expr)
        return self._compile(node)

    def _compile(self, node) -> Callable[[int], Any]:
        if not self.is_dynamic(node):
            v = self._ev(node)
            if np.isscalar(v) or v is None:
                return lambda i, v=v: v
            arr = _ser(v, self.df.index).to_numpy()
            return lambda i, arr=arr: arr[i]
        if isinstance(node, ast.Name):
            if node.id in DYNAMIC:
                return lambda i, k=node.id: self.dyn[k]
            return self._compile(self.parse(self.var_exprs[node.id]))
        if isinstance(node, ast.BoolOp):
            parts = [self._compile(v) for v in node.values]
            if isinstance(node.op, ast.And):
                return lambda i: all(_truth(p(i)) for p in parts)
            return lambda i: any(_truth(p(i)) for p in parts)
        if isinstance(node, ast.UnaryOp):
            f = self._compile(node.operand)
            if isinstance(node.op, ast.Not):
                return lambda i: not _truth(f(i))
            return (lambda i: -f(i)) if isinstance(node.op, ast.USub) else f
        if isinstance(node, ast.BinOp):
            a, b = self._compile(node.left), self._compile(node.right)
            ops = {ast.Add: lambda x, y: x + y, ast.Sub: lambda x, y: x - y, ast.Mult: lambda x, y: x * y,
                   ast.Div: lambda x, y: x / y if y else float("nan"), ast.Mod: lambda x, y: x % y,
                   ast.Pow: lambda x, y: x ** y}
            fn = ops[type(node.op)]
            return lambda i: fn(a(i), b(i))
        if isinstance(node, ast.Compare):
            fs = [self._compile(node.left)] + [self._compile(c) for c in node.comparators]
            cmp = {ast.Gt: lambda x, y: x > y, ast.GtE: lambda x, y: x >= y, ast.Lt: lambda x, y: x < y,
                   ast.LtE: lambda x, y: x <= y, ast.Eq: lambda x, y: x == y, ast.NotEq: lambda x, y: x != y}
            ops = [cmp[type(o)] for o in node.ops]

            def f(i):
                vals = [g(i) for g in fs]
                return all(op(vals[k], vals[k + 1]) for k, op in enumerate(ops))
            return f
        if isinstance(node, ast.IfExp):
            t, a, b = self._compile(node.test), self._compile(node.body), self._compile(node.orelse)
            return lambda i: a(i) if _truth(t(i)) else b(i)
        if isinstance(node, ast.Call) and node.func.id in ("abs", "min", "max"):
            parts = [self._compile(a) for a in node.args]
            fn = {"abs": abs, "min": min, "max": max}[node.func.id]
            return lambda i: fn(*[p(i) for p in parts])
        raise RuleError("Live state (position, trades_today, ...) can only be combined with "
                        "comparisons, and/or/not, arithmetic, abs/min/max")


def _truth(v) -> bool:
    if v is None:
        return False
    try:
        if isinstance(v, float) and np.isnan(v):
            return False
    except TypeError:
        pass
    return bool(v)


def _finite(v) -> float | None:
    if v is None:
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if np.isfinite(v) else None


class RuleStrategy(Strategy):
    """Runs a strategy card."""

    SIDE_KEYS = {"when", "order", "price", "limit_price", "sl", "tp", "sl_dist", "tp_dist", "tp_r",
                 "trail_dist", "trail_trigger", "lots", "qty", "comment", "keep_pending"}
    CARD_KEYS = {"name", "description", "timeframe", "symbol", "author", "tags", "evidence", "notes",
                 "params", "vars", "long", "short", "exit", "cancel_when", "settings", "plots", "created",
                 "source", "version", "warmup", "pine", "oca_entries"}

    def __init__(self, card: dict, **overrides):
        if not isinstance(card, dict):
            raise RuleError("A strategy card must be a mapping")
        if len(card.get("vars") or {}) > 60 or len(card.get("plots") or {}) > 10 or len(card.get("params") or {}) > 30:
            raise RuleError("Too many vars (max 60), plots (max 10) or params (max 30)")
        unknown = set(card) - self.CARD_KEYS
        if unknown:
            raise RuleError(f"Unknown card keys: {sorted(unknown)}")
        self.card = card
        self.name = card.get("name", "Unnamed card")
        self.description = (card.get("description") or "").strip()
        self.timeframe = card.get("timeframe")
        self.params = dict(card.get("params") or {})
        for side in ("long", "short"):
            extra = set(card.get(side) or {}) - self.SIDE_KEYS
            if extra:
                raise RuleError(f"Unknown keys under {side}: {sorted(extra)}")
        super().__init__(**overrides)

    @classmethod
    def from_file(cls, path: str | Path, **overrides) -> "RuleStrategy":
        path = Path(path)
        card = yaml.safe_load(path.read_text())
        s = cls(card, **overrides)
        s.path = str(path)
        return s

    def source(self) -> str:
        return yaml.safe_dump(self.card, sort_keys=False)

    def fingerprint(self) -> str:
        logic = {k: self.card.get(k) for k in ("vars", "long", "short", "exit", "cancel_when", "timeframe")}
        return hashlib.sha256(yaml.safe_dump(logic, sort_keys=True).encode()).hexdigest()[:12]

    def spec(self) -> dict:
        return {"name": self.name, "kind": "card", "params": vars(self.p), "description": self.description,
                "timeframe": self.timeframe, "tags": self.card.get("tags", []),
                "evidence": self.card.get("evidence")}

    # ------------------------------------------------------------------
    def init(self):
        self.ctx = Context(self.data, vars(self.p), dict(self.card.get("vars") or {}))
        ctx = self.ctx
        self.sides = {}
        for side in ("long", "short"):
            spec = self.card.get(side)
            if not spec:
                continue
            f = {k: ctx.compile(spec.get(k)) for k in ("when", "price", "limit_price", "sl", "tp", "sl_dist",
                                                      "tp_dist", "trail_dist", "trail_trigger")}
            f["order"] = spec.get("order", "market")
            if f["order"] not in ("market", "stop", "limit", "stop_limit"):
                raise RuleError(f"{side}.order must be market, stop, limit or stop_limit")
            for k in ("tp_r", "lots", "qty"):   # numbers, param names or expressions
                f[k] = ctx.compile(spec.get(k)) if spec.get(k) is not None else (lambda i: None)
            f["comment"] = spec.get("comment", "")
            f["keep_pending"] = spec.get("keep_pending", False)
            self.sides[side] = f
        ex = self.card.get("exit") or {}
        self.exit_long = ctx.compile(ex.get("long_when"))
        self.exit_short = ctx.compile(ex.get("short_when"))
        self.exit_all = ctx.compile(ex.get("when"))
        mb = ex.get("max_bars")
        self.max_bars = getattr(self.p, mb) if isinstance(mb, str) else mb
        self.cancel_when = ctx.compile(self.card.get("cancel_when"))
        self.day_key = pd.Series((self.data.index.tz_convert("America/New_York") + pd.Timedelta(hours=7)).date,
                                 index=self.data.index).to_numpy()
        self.entries_by_day: dict = {}
        self._seen_tids: set = set()
        for name, expr in (self.card.get("plots") or {}).items():
            self.plot(name, _ser(ctx.eval_static(expr), self.data.index).astype(float))

    def _update_dyn(self, i: int):
        b = self.broker
        pos = b.position
        for t in b.trades:
            if t.tid not in self._seen_tids:
                self._seen_tids.add(t.tid)
                d = self.day_key[t.entry_bar]
                self.entries_by_day[d] = self.entries_by_day.get(d, 0) + 1
        for row in b.closed[-5:]:
            if row["trade"] not in self._seen_tids:
                self._seen_tids.add(row["trade"])
                d = self.day_key[row["entry_bar"]]
                self.entries_by_day[d] = self.entries_by_day.get(d, 0) + 1
        first = min(b.trades, key=lambda t: t.entry_bar) if b.trades else None
        self.ctx.dyn = {
            "position": 1 if pos > 0 else (-1 if pos < 0 else 0),
            "is_long": pos > 0, "is_short": pos < 0, "is_flat": pos == 0,
            "bars_in_trade": (i - first.entry_bar) if first else 0,
            "entry_price": first.entry_price if first else float("nan"),
            "trades_today": self.entries_by_day.get(self.day_key[i], 0),
            "open_profit": b.open_profit(self.close[i], b.spread[i]),
        }

    def next(self, i: int):
        self._update_dyn(i)
        pos = self.broker.position
        # exits first (they act on the current position)
        if pos > 0 and _truth(self.exit_long(i)):
            self.close_position(None, "exit rule")
        elif pos < 0 and _truth(self.exit_short(i)):
            self.close_position(None, "exit rule")
        if pos != 0 and _truth(self.exit_all(i)):
            self.close_position(None, "exit rule")
        if pos != 0 and self.max_bars and self.ctx.dyn["bars_in_trade"] >= int(self.max_bars):
            self.close_position(None, "time stop")
        if _truth(self.cancel_when(i)):
            for side in ("long", "short"):
                self.cancel(side.upper())

        for side, f in self.sides.items():
            oid = side.upper()
            if not _truth(f["when"](i)):
                if not f["keep_pending"]:
                    self.broker.entries.pop(oid, None)
                continue
            if (side == "long" and pos > 0) or (side == "short" and pos < 0):
                if self.broker.s.pyramiding <= 1:
                    continue
            direction = 1 if side == "long" else -1
            price = _finite(f["price"](i))
            stop = limit = None
            if f["order"] == "stop":
                stop = price
            elif f["order"] == "limit":
                limit = price
            elif f["order"] == "stop_limit":
                stop, limit = price, _finite(f["limit_price"](i))
            if f["order"] != "market" and price is None:
                continue
            sl, tp = _finite(f["sl"](i)), _finite(f["tp"](i))
            sl_dist, tp_dist = _finite(f["sl_dist"](i)), _finite(f["tp_dist"](i))
            ref = price if price is not None else self.close[i]
            risk = sl_dist if sl_dist is not None else (abs(ref - sl) if sl is not None else None)
            tp_r = _finite(f["tp_r"](i))
            if tp_r is not None and risk:
                tp_dist = tp_r * risk
            if (sl is not None and direction * (ref - sl) <= 0) or (risk is not None and risk <= 0):
                continue  # stop on the wrong side of the entry: skip, like a broker would reject it
            if (risk is None and self.broker.s.qty_type == "risk_percent"
                    and f["lots"](i) is None and f["qty"](i) is None):
                continue  # stop distance not known yet (indicator still warming up)
            trail = _finite(f["trail_dist"](i))
            trig = _finite(f["trail_trigger"](i))
            self.entry(oid, direction, qty=_finite(f["qty"](i)), lots=_finite(f["lots"](i)), stop=stop, limit=limit,
                       sl=sl, tp=tp, sl_dist=sl_dist, tp_dist=tp_dist, trail_offset=trail,
                       trail_trigger_dist=trig, comment=f["comment"],
                       oca="entries" if self.card.get("oca_entries") and f["order"] != "market" else None)


def load_card(path: str | Path, **overrides) -> RuleStrategy:
    return RuleStrategy.from_file(path, **overrides)
