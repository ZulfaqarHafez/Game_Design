"""Translate a strategy card into TradingView Pine Script v6.

Paste the output into TradingView's Pine Editor, add it to an XAUUSD chart on
the card's timeframe, and compare its strategy report with goldlab's
TradingView-preset backtest. Expect close but not identical numbers: data
feeds differ (broker vs Dukascopy), and TradingView charts have no spread.
"""
from __future__ import annotations

import ast
import re

from .rules import DYNAMIC, Context, RuleError, RuleStrategy

TF = {"1m": "1", "3m": "3", "5m": "5", "15m": "15", "30m": "30", "1h": "60", "2h": "120", "4h": "240",
      "1d": "D", "1w": "W"}

SIMPLE = {"sma": "ta.sma", "ema": "ta.ema", "rma": "ta.rma", "wma": "ta.wma", "hma": "ta.hma", "vwma": "ta.vwma",
          "rsi": "ta.rsi", "stdev": "ta.stdev", "highest": "ta.highest", "lowest": "ta.lowest",
          "change": "ta.change", "roc": "ta.roc", "mom": "ta.mom", "crossover": "ta.crossover",
          "crossunder": "ta.crossunder", "cross": "ta.cross", "barssince": "ta.barssince",
          "valuewhen": "ta.valuewhen", "abs": "math.abs", "min": "math.min", "max": "math.max", "nz": "nz",
          "na": "na", "round": "math.round", "sqrt": "math.sqrt", "log": "math.log"}
BOOL_FUNCS = {"crossover", "crossunder", "cross", "in_session", "na", "new_day"}

HELPERS = {
    "session": '''// High/low of the most recent completed session window (held until the next window opens).
f_sess(string sess, string tz) =>
    inS = not na(time(timeframe.period, sess, tz))
    var float runHi = na
    var float runLo = na
    var float doneHi = na
    var float doneLo = na
    if inS and not inS[1]
        runHi := high
        runLo := low
        doneHi := na
        doneLo := na
    else if inS
        runHi := math.max(runHi, high)
        runLo := math.min(runLo, low)
    if not inS and inS[1]
        doneHi := runHi
        doneLo := runLo
    [inS ? na : doneHi, inS ? na : doneLo]
''',
    "dmi": '''f_dmi(int len) =>
    [p, m, a] = ta.dmi(len, len)
    [p, m, a]
''',
    "supertrend": '''f_st(float factor, int len) =>
    [st, dir] = ta.supertrend(factor, len)
    [st, dir]
''',
    "trades_today": '''// Entries filled since the 17:00 New York day roll
var int tradesToday = 0
if ta.change(time("D")) != 0
    tradesToday := 0
tradesToday += math.max(strategy.closedtrades + strategy.opentrades - (strategy.closedtrades[1] + strategy.opentrades[1]), 0)
''',
}


def _sess(window: str) -> str:
    a, b = window.replace(":", "").split("-")
    return f"{a}-{b}:1234567"


class PineWriter:
    def __init__(self, strategy: RuleStrategy):
        self.s = strategy
        self.card = strategy.card
        self.params = dict(strategy.card.get("params") or {})
        self.vars = dict(strategy.card.get("vars") or {})
        self.helpers: set[str] = set()
        self.pre: list[str] = []      # helper tuple assignments
        self.tmp = 0
        self.ctx = Context.__new__(Context)  # only for parse()
        self.ctx.var_exprs = self.vars

    def parse(self, expr):
        return Context.parse(self.ctx, expr)

    # -- expressions -----------------------------------------------------
    def is_bool(self, node) -> bool:
        if isinstance(node, (ast.Compare, ast.BoolOp)):
            return True
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return True
        if isinstance(node, ast.Call) and node.func.id in BOOL_FUNCS:
            return True
        if isinstance(node, ast.Name):
            if node.id in ("is_long", "is_short", "is_flat", "true", "false", "True", "False"):
                return True
            if node.id in self.vars:
                return self.is_bool(self.parse(self.vars[node.id]))
        if isinstance(node, ast.Constant) and isinstance(node.value, bool):
            return True
        if isinstance(node, ast.IfExp):
            return self.is_bool(node.body)
        return False

    def num(self, node) -> str:
        """Expression as a number (bools become 1/0, as in Python)."""
        e = self.ex(node)
        return f"({e} ? 1 : 0)" if self.is_bool(node) else e

    def _tuple(self, call: str, n: int, pick: int) -> str:
        self.tmp += 1
        names = [f"_t{self.tmp}_{k}" for k in range(n)]
        self.pre.append(f"[{', '.join(names)}] = {call}")
        return names[pick]

    def ex(self, node) -> str:
        if isinstance(node, ast.Constant):
            v = node.value
            if isinstance(v, bool):
                return "true" if v else "false"
            if isinstance(v, str):
                return f'"{v}"'
            return repr(v)
        if isinstance(node, ast.Name):
            n = node.id
            if n in ("true", "True"):
                return "true"
            if n in ("false", "False"):
                return "false"
            if n == "spread":
                raise RuleError("'spread' has no TradingView equivalent (TradingView charts carry no spread)")
            dyn = {"position": "math.sign(strategy.position_size)", "is_long": "strategy.position_size > 0",
                   "is_short": "strategy.position_size < 0", "is_flat": "strategy.position_size == 0",
                   "bars_in_trade": "(strategy.opentrades > 0 ? bar_index - strategy.opentrades.entry_bar_index(0) : 0)",
                   "entry_price": "strategy.opentrades.entry_price(0)", "open_profit": "strategy.openprofit"}
            if n == "trades_today":
                self.helpers.add("trades_today")
                return "tradesToday"
            if n in dyn:
                return f"({dyn[n]})"
            return n
        if isinstance(node, ast.BinOp):
            ops = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/", ast.Mod: "%"}
            if isinstance(node.op, ast.Pow):
                return f"math.pow({self.num(node.left)}, {self.num(node.right)})"
            return f"({self.num(node.left)} {ops[type(node.op)]} {self.num(node.right)})"
        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.Not):
                return f"(not {self.ex(node.operand)})"
            return f"(-{self.num(node.operand)})" if isinstance(node.op, ast.USub) else self.num(node.operand)
        if isinstance(node, ast.BoolOp):
            op = " and " if isinstance(node.op, ast.And) else " or "
            return "(" + op.join(self.ex(v) for v in node.values) + ")"
        if isinstance(node, ast.Compare):
            sym = {ast.Gt: ">", ast.GtE: ">=", ast.Lt: "<", ast.LtE: "<=", ast.Eq: "==", ast.NotEq: "!="}
            parts, left = [], node.left
            for op, right in zip(node.ops, node.comparators):
                parts.append(f"{self.num(left)} {sym[type(op)]} {self.num(right)}")
                left = right
            return "(" + " and ".join(parts) + ")"
        if isinstance(node, ast.IfExp):
            return f"({self.ex(node.test)} ? {self.ex(node.body)} : {self.ex(node.orelse)})"
        if isinstance(node, ast.Subscript):
            return f"({self.ex(node.value)})[{self.ex(node.slice)}]"
        if isinstance(node, ast.Call):
            return self.call(node)
        raise RuleError(f"Cannot translate {type(node).__name__} to Pine")

    def call(self, node) -> str:
        f = node.func.id
        a = [self.ex(x) for x in node.args]
        kw = {k.arg: self.ex(k.value) for k in node.keywords}
        lit = lambda i, default=None: (node.args[i].value if len(node.args) > i and isinstance(node.args[i], ast.Constant)
                                       else default)
        if f in SIMPLE:
            return f"{SIMPLE[f]}({', '.join(a + [f'{k}={v}' for k, v in kw.items()])})"
        if f == "atr":
            return f"ta.atr({a[0] if a else 14})"
        if f == "tr":
            return "ta.tr(true)"
        if f == "cci":
            return f"ta.cci(hlc3, {a[0] if a else 20})"
        if f == "stoch":
            n = a[0] if a else "14"
            sm = a[1] if len(a) > 1 else "1"
            return f"ta.sma(ta.stoch(close, high, low, {n}), {sm})"
        if f in ("bb_mid", "bb_upper", "bb_lower"):
            src, n, mult = (a + ["close", "20", "2.0"][len(a):])[:3] if a else ("close", "20", "2.0")
            mid = f"ta.sma({src}, {n})"
            return mid if f == "bb_mid" else f"({mid} {'+' if f == 'bb_upper' else '-'} {mult} * ta.stdev({src}, {n}))"
        if f in ("kc_upper", "kc_lower"):
            n, mult = (a + ["20", "1.5"][len(a):])[:2]
            return f"(ta.ema(close, {n}) {'+' if f == 'kc_upper' else '-'} {mult} * ta.atr({n}))"
        if f in ("macd", "macd_signal", "macd_hist"):
            src, fa, sl, sg = (a + ["close", "12", "26", "9"][len(a):])[:4]
            line = f"(ta.ema({src}, {fa}) - ta.ema({src}, {sl}))"
            sig = f"ta.ema({line}, {sg})"
            return line if f == "macd" else (sig if f == "macd_signal" else f"({line} - {sig})")
        if f in ("adx", "plus_di", "minus_di"):
            self.helpers.add("dmi")
            n = a[0] if a else "14"
            return self._tuple(f"f_dmi({n})", 3, {"plus_di": 0, "minus_di": 1, "adx": 2}[f])
        if f in ("supertrend", "supertrend_dir"):
            self.helpers.add("supertrend")
            fac, n = (a + ["3.0", "10"][len(a):])[:2]
            return self._tuple(f"f_st({fac}, {n})", 2, 0 if f == "supertrend" else 1)
        if f == "vwap":
            return "ta.vwap(hlc3)"
        if f == "in_session":
            tz = lit(1, "UTC")
            return f'(not na(time(timeframe.period, "{_sess(lit(0))}", "{tz}")))'
        if f in ("session_high", "session_low"):
            self.helpers.add("session")
            tz = lit(1, "UTC")
            return self._tuple(f'f_sess("{_sess(lit(0))}", "{tz}")', 2, 0 if f == "session_high" else 1)
        if f in ("hour", "minute"):
            return f'{f}(time, "{lit(0, "UTC")}")'
        if f == "weekday":
            return f'((dayofweek(time, "{lit(0, "UTC")}") + 5) % 7)'
        if f == "new_day":
            return '(ta.change(time("D")) != 0)'
        if f == "security":
            tf = lit(0)
            inner_node = self.parse(lit(1))
            inner = self.num(inner_node)
            return f'request.security(syminfo.tickerid, "{TF[tf]}", ({inner})[1], lookahead=barmerge.lookahead_on)'
        raise RuleError(f"No Pine translation for {f}()")

    # -- program -----------------------------------------------------------
    def _order_vars(self):
        names = list(self.vars)
        deps = {n: {x.id for x in ast.walk(self.parse(self.vars[n])) if isinstance(x, ast.Name) and x.id in self.vars}
                for n in names}
        done, out = set(), []
        def visit(n, stack=()):
            if n in done:
                return
            if n in stack:
                raise RuleError(f"Circular vars: {' -> '.join(stack + (n,))}")
            for d in deps[n]:
                visit(d, stack + (n,))
            done.add(n)
            out.append(n)
        for n in names:
            visit(n)
        return out

    def write(self, settings: dict | None = None) -> str:
        card = self.card
        st = {**(card.get("settings") or {}), **(settings or {})}
        body: list[str] = []
        for name in self._order_vars():
            self.pre = []
            e = self.ex(self.parse(self.vars[name]))
            body += self.pre + [f"{name} = {e}"]

        qty_type = st.get("qty_type", "lots")
        qv = st.get("qty_value", 0.1)
        cs = st.get("contract_size", 100)

        def qty_expr(spec, risk_e):
            if spec.get("lots") is not None:
                return f"{float(spec['lots']) * cs:g}"
            if spec.get("qty") is not None:
                return f"{spec['qty']:g}"
            if qty_type == "risk_percent":
                return f"f_riskQty({risk_e})"
            if qty_type == "lots":
                return f"{float(qv) * cs:g}"
            return None  # strategy() defaults handle units/cash/percent

        blocks = []
        for side in ("long", "short"):
            spec = card.get(side)
            if not spec:
                continue
            oid = side.upper()
            self.pre = []
            when = self.ex(self.parse(spec["when"]))
            pre_when = list(self.pre)
            lines = []
            # Every series is computed on every bar (outside the if-blocks), as Pine requires
            # for consistent ta.* results.
            top = []
            def val(key):
                if spec.get(key) is None:
                    return None
                e = self.num(self.parse(spec[key]))
                name = f"{side}{key.title().replace('_', '')}"
                top.append(f"{name} = {e}")
                return name
            price, sl, tp = val("price"), val("sl"), val("tp")
            sld, tpd, trail, trig = val("sl_dist"), val("tp_dist"), val("trail_dist"), val("trail_trigger")
            limit_px = val("limit_price")
            pre_rest = list(self.pre) + top
            ref = price or "close"
            risk = sld if sld else (f"math.abs({ref} - {sl})" if sl else None)
            if tpd is None and spec.get("tp_r") is not None and risk:
                tpd = f"{spec['tp_r']} * {risk}"
            order = spec.get("order", "market")
            args = [f'"{oid}"', f"strategy.{side}"]
            q = qty_expr(spec, risk or "na")
            if q:
                args.append(f"qty={q}")
            if order in ("stop", "stop_limit"):
                args.append(f"stop={price}")
            if order == "limit":
                args.append(f"limit={price}")
            if order == "stop_limit":
                args.append(f"limit={limit_px}")
            if card.get("oca_entries") and order != "market":
                args.append('oca_name="entries", oca_type=strategy.oca.cancel')
            lines.append(f"    strategy.entry({', '.join(args)})")
            ex = []
            if sl:
                ex.append(f"stop={sl}")
            if tp:
                ex.append(f"limit={tp}")
            if sld:
                ex.append(f"loss={sld} / syminfo.mintick")
            if tpd:
                ex.append(f"profit={tpd} / syminfo.mintick")
            if trail:
                ex.append(f"trail_points={(trig + ' / syminfo.mintick') if trig else '0'}, trail_offset={trail} / syminfo.mintick")
            if ex:
                lines.append(f'    strategy.exit("{oid} exit", "{oid}", {", ".join(ex)})')
            guard = "strategy.position_size <= 0" if side == "long" else "strategy.position_size >= 0"
            blk = pre_when + pre_rest + [f"{side}Signal = {when}", f"if {side}Signal and {guard}"] + lines
            if order != "market" and not spec.get("keep_pending"):
                blk += [f"if not {side}Signal", f'    strategy.cancel("{oid}")']
            blocks.append("\n".join(blk))

        exits = []
        exspec = card.get("exit") or {}
        for key, cond in (("long_when", "strategy.position_size > 0"), ("short_when", "strategy.position_size < 0"),
                          ("when", "strategy.position_size != 0")):
            if exspec.get(key):
                self.pre = []
                e = self.ex(self.parse(exspec[key]))
                exits += self.pre + [f"if {cond} and {e}", '    strategy.close_all("exit rule")']
        if exspec.get("max_bars"):
            mb = exspec["max_bars"]
            exits += [f"if strategy.opentrades > 0 and bar_index - strategy.opentrades.entry_bar_index(0) >= {mb}",
                      '    strategy.close_all("time stop")']
        if card.get("cancel_when"):
            self.pre = []
            e = self.ex(self.parse(card["cancel_when"]))
            exits += self.pre + [f"if {e}", '    strategy.cancel("LONG")', '    strategy.cancel("SHORT")']

        plots = []
        colors = ["color.blue", "color.purple", "color.orange", "color.teal"]
        for k, (name, expr) in enumerate((card.get("plots") or {}).items()):
            self.pre = []
            e = self.num(self.parse(expr))
            plots += self.pre + [f'plot({e}, "{name}", {colors[k % 4]})']

        # header
        comm = st.get("commission_value", 0)
        ctype = st.get("commission_type", "cash_per_lot")
        if ctype == "cash_per_lot":
            ctype, comm = "cash_per_contract", comm / cs
        sargs = [f'"{self.s.name}"', "overlay=true", f"initial_capital={st.get('initial_capital', 10000)}",
                 f"pyramiding={st.get('pyramiding', 1)}", f"commission_type=strategy.commission.{ctype}",
                 f"commission_value={comm:g}", f"slippage={st.get('slippage_ticks', 0)}",
                 f"process_orders_on_close={'true' if st.get('process_orders_on_close') else 'false'}"]
        if qty_type == "percent_of_equity":
            sargs += ["default_qty_type=strategy.percent_of_equity", f"default_qty_value={qv}"]
        elif qty_type == "cash":
            sargs += ["default_qty_type=strategy.cash", f"default_qty_value={qv}"]
        elif qty_type == "units":
            sargs += ["default_qty_type=strategy.fixed", f"default_qty_value={qv}"]
        mp = st.get("margin_percent", 5.0)
        if mp:
            sargs += [f"margin_long={mp}", f"margin_short={mp}"]
        inputs = []
        for k, v in self.params.items():
            if isinstance(v, bool):
                inputs.append(f'{k} = input.bool({"true" if v else "false"}, "{k}")')
            elif isinstance(v, int):
                inputs.append(f'{k} = input.int({v}, "{k}")')
            elif isinstance(v, float):
                inputs.append(f'{k} = input.float({v}, "{k}")')
            else:
                inputs.append(f'{k} = input.string("{v}", "{k}")')
        if qty_type == "risk_percent":
            inputs.append(f'risk_pct = input.float({qv}, "Risk % of equity per trade")')
            self.helpers.add("risk")
        helpers = [HELPERS[h] for h in ("session", "dmi", "supertrend") if h in self.helpers]
        if "risk" in self.helpers:
            helpers.append("f_riskQty(float dist) =>\n    nz(dist) > 0 ? math.max(math.floor(strategy.equity * risk_pct / 100 / dist), 1) : 1\n")
        tt = [HELPERS["trades_today"]] if "trades_today" in self.helpers else []
        desc = (self.s.description or "").strip()
        out = ["// Generated by goldlab from the strategy card \"" + self.s.name + "\"",
               "// " + "\n// ".join(re.findall(r".{1,90}(?:\s|$)", desc)) if desc else "//",
               "// Check syminfo.mintick for your gold symbol: slippage is in ticks. TradingView charts have no",
               "// spread, so compare against goldlab's --preset tradingview run, not the realistic one.",
               "//@version=6", f"strategy({', '.join(sargs)})", "", *inputs, "", *helpers, *tt,
               "// --- variables", *body, "", "// --- exits", *exits, "", "// --- entries", *blocks, "",
               "// --- plots", *plots]
        return "\n".join(out).replace("\n\n\n", "\n\n") + "\n"


def to_pine(strategy: RuleStrategy, settings: dict | None = None) -> str:
    if not isinstance(strategy, RuleStrategy):
        raise RuleError("Pine export works for strategy cards (.yaml). Python strategies need hand porting.")
    return PineWriter(strategy).write(settings)
