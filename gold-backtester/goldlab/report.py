"""Self-contained HTML backtest report in the spirit of TradingView's strategy report.

Charts use TradingView's open-source Lightweight Charts (Apache-2.0, loaded
from a pinned CDN build; the library shows its required TradingView
attribution in the chart corner).
"""
from __future__ import annotations

import html
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

LWC = "https://cdn.jsdelivr.net/npm/lightweight-charts@5.2.0/dist/lightweight-charts.standalone.production.js"
MAX_CANDLES = 20000


def _num(v, kind="money"):
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return "n/a" if not (isinstance(v, float) and math.isinf(v)) else "∞"
    if kind == "money":
        return f"{'-' if v < 0 else ''}${abs(v):,.2f}"
    if kind == "pct":
        return f"{v:,.2f}%"
    if kind == "ratio":
        return f"{0.0 if abs(v) < 5e-4 else v:,.3f}"  # avoid "-0.000"
    if kind == "int":
        return f"{int(v):,}"
    return f"{v:,.2f}"


def _side_metrics(trades: pd.DataFrame) -> dict:
    out = {}
    for label, t in (("All", trades), ("Long", trades[trades["side"] == "long"]),
                     ("Short", trades[trades["side"] == "short"])):
        p = t["pnl"].to_numpy(float) if len(t) else np.array([])
        w, l = p[p > 0], p[p < 0]
        out[label] = {
            "Net profit": _num(p.sum()), "Gross profit": _num(w.sum()), "Gross loss": _num(-l.sum()),
            "Profit factor": _num(w.sum() / -l.sum(), "ratio") if len(l) else "n/a",
            "Total closed trades": _num(len(p), "int"),
            "Percent profitable": _num((p > 0).mean() * 100, "pct") if len(p) else "n/a",
            "Avg trade": _num(p.mean()) if len(p) else "n/a",
            "Avg winning trade": _num(w.mean()) if len(w) else "n/a",
            "Avg losing trade": _num(-l.mean()) if len(l) else "n/a",
            "Ratio avg win / avg loss": _num(w.mean() / -l.mean(), "ratio") if len(w) and len(l) else "n/a",
            "Largest winning trade": _num(w.max()) if len(w) else "n/a",
            "Largest losing trade": _num(-l.min()) if len(l) else "n/a",
            "Avg # bars in trades": _num(t["bars"].mean(), "float") if len(t) else "n/a",
            "Commission": _num(t["commission"].sum()) if len(t) else "n/a",
        }
    return out


def _monthly_table(equity: pd.Series, initial: float) -> str:
    idx = equity.index.tz_convert(None) if equity.index.tz is not None else equity.index
    m = pd.Series(equity.to_numpy(), index=idx).groupby(idx.to_period("M")).last()
    m = pd.concat([pd.Series([initial], index=[m.index[0] - 1]), m])
    r = (m.pct_change().dropna() * 100)
    if r.empty:
        return ""
    years = sorted({p.year for p in r.index})
    head = "".join(f"<th>{pd.Timestamp(2000, k, 1):%b}</th>" for k in range(1, 13))
    rows = []
    for y in years:
        cells = []
        for k in range(1, 13):
            p = pd.Period(year=y, month=k, freq="M")
            if p in r.index:
                v = r[p]
                cls = "pos" if v > 0 else ("neg" if v < 0 else "")
                a = min(abs(v) / 8, 1)
                cells.append(f'<td class="{cls}" style="--a:{a:.2f}">{v:+.1f}</td>')
            else:
                cells.append("<td></td>")
        ye = m[[p for p in m.index if p.year == y]]
        prev = m[[p for p in m.index if p.year < y]]
        start = prev.iloc[-1] if len(prev) else initial
        yr = (ye.iloc[-1] / start - 1) * 100 if len(ye) else float("nan")
        cls = "pos" if yr > 0 else "neg"
        rows.append(f"<tr><th>{y}</th>{''.join(cells)}<td class=\"yr {cls}\">{yr:+.1f}</td></tr>")
    return (f'<div class="scroll" tabindex="0" role="region" aria-label="Monthly returns"><table class="months"><thead><tr><th>Year</th>{head}<th>Full year</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def _validation_html(v: dict | None) -> str:
    if not v:
        return ('<p class="muted">Not run yet. Run <code>python -m goldlab validate &lt;strategy&gt;</code> '
                'to add walk-forward, Monte Carlo, cost-stress and overfitting checks here.</p>')
    rows = []
    for c in v.get("checks", []):
        state = c["status"]
        rows.append(f'<tr><td><span class="chip {state}">{state.upper()}</span></td><td>{html.escape(c["name"])}</td>'
                    f'<td class="num">{html.escape(str(c.get("value", "")))}</td>'
                    f'<td class="muted">{html.escape(c.get("rule", ""))}</td></tr>')
    verdict = v.get("verdict", "")
    return (f'<p class="verdict {verdict.lower()}">{html.escape(v.get("headline", ""))}</p>'
            f'<div class="scroll" tabindex="0" role="region" aria-label="Readiness checks"><table class="checks"><thead><tr><th>Result</th><th>Check</th><th>Value</th>'
            f'<th>Rule</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


def render(result, validation: dict | None = None, fragment: bool = False, title: str | None = None,
           max_candles: int = MAX_CANDLES, back_href: str | None = None) -> str:
    s = result.strategy
    d = result.data
    m = result.metrics
    st = result.settings
    a = d.attrs
    trades = result.trades

    shown = d.iloc[-max_candles:]
    t0 = shown.index[0]
    to_ts = lambda ts: int(pd.Timestamp(ts).timestamp())
    candles = [[to_ts(t), round(o, 3), round(h, 3), round(l, 3), round(c, 3)]
               for t, o, h, l, c in zip(shown.index, shown["open"], shown["high"], shown["low"], shown["close"])]
    markers = []
    if len(trades):
        for _, t in trades.iterrows():
            if t["entry_time"] >= t0:
                markers.append([to_ts(t["entry_time"]), "entry", t["side"], round(float(t["entry_price"]), 2),
                                f'{t["side"]} {t["lots"]:.2f}'])
            if t["exit_time"] >= t0:
                markers.append([to_ts(t["exit_time"]), "exit", t["side"], round(float(t["exit_price"]), 2),
                                f'{float(t["pnl"]):+,.0f}'])
    markers.sort(key=lambda x: x[0])
    plots = {}
    for name, ser in (getattr(s, "plots", None) or {}).items():
        ser = ser.reindex(shown.index)
        plots[name] = [[to_ts(t), round(float(v), 3)] for t, v in ser.items() if pd.notna(v)]
    eq = result.equity
    step = max(1, len(eq) // 1500)
    eq_pts = [[to_ts(t), round(float(v), 2)] for t, v in eq.iloc[::step].items() if pd.notna(v)]
    peak = np.maximum.accumulate(eq.to_numpy(float))
    dd = pd.Series((eq.to_numpy(float) - peak) / peak * 100, index=eq.index)
    dd_pts = [[to_ts(t), round(float(v), 3)] for t, v in dd.iloc[::step].items() if pd.notna(v)]
    payload = json.dumps({"candles": candles, "markers": markers, "plots": plots, "equity": eq_pts,
                          "dd": dd_pts, "initial": st.initial_capital})

    side = _side_metrics(trades) if len(trades) else {}
    perf_rows = ""
    if side:
        for k in side["All"]:
            perf_rows += (f"<tr><th>{k}</th><td>{side['All'][k]}</td><td>{side['Long'][k]}</td>"
                          f"<td>{side['Short'][k]}</td></tr>")
    risk_rows = "".join(
        f"<tr><th>{label}</th><td>{val}</td></tr>" for label, val in [
            ("Max equity drawdown (TradingView definition)", f'{_num(m.get("max_drawdown"))} · {_num(m.get("max_drawdown_pct"), "pct")}'),
            ("Max drawdown incl. open profit given back", f'{_num(m.get("max_drawdown_mtm"))} · {_num(m.get("max_drawdown_mtm_pct"), "pct")}'),
            ("Max equity run-up", _num(m.get("max_runup"))),
            ("Sharpe ratio (monthly, TradingView method)", _num(m.get("sharpe"), "ratio")),
            ("Sortino ratio (monthly)", _num(m.get("sortino"), "ratio")),
            ("CAGR", _num(m.get("cagr_pct"), "pct")),
            ("Calmar ratio", _num(m.get("calmar"), "ratio")),
            ("Buy & hold return", f'{_num(m.get("buy_hold_return"))} · {_num(m.get("buy_hold_return_pct"), "pct")}'),
            ("Commission paid", _num(m.get("commission_paid"))),
            ("Overnight swap paid", _num(m.get("swap_paid"))),
            ("Time in market", _num(m.get("exposure_pct"), "pct")),
            ("Trades per month", _num(m.get("trades_per_month"), "float")),
            ("Open P&L at end", _num(m.get("open_pnl"))),
            ("Orders skipped (size below 0.01 lot or no margin)", _num(m.get("rejected_orders", 0), "int")),
        ])
    tlist = ""
    if len(trades):
        for _, t in trades.iloc[::-1].head(500).iterrows():
            cls = "pos" if t["pnl"] > 0 else "neg"
            tlist += (f'<tr><td class="num">{int(t["trade"])}</td><td><span class="side {t["side"]}">{t["side"]}</span></td>'
                      f'<td>{pd.Timestamp(t["entry_time"]):%Y-%m-%d %H:%M}</td><td class="num">{t["entry_price"]:,.2f}</td>'
                      f'<td>{pd.Timestamp(t["exit_time"]):%Y-%m-%d %H:%M}</td><td class="num">{t["exit_price"]:,.2f}</td>'
                      f'<td>{html.escape(str(t["exit_id"]))}</td><td class="num">{t["lots"]:.2f}</td>'
                      f'<td class="num {cls}">{t["pnl"]:+,.2f}</td><td class="num">{int(t["bars"])}</td></tr>')
    cost = (f'Spread: {"real bid/ask from data" if st.spread_mode == "data" else ("$%.2f fixed" % st.spread_fixed if st.spread_mode == "fixed" else "none (TradingView default)")}'
            f' · Commission: {st.commission_value:g} ({st.commission_type.replace("_", " ")}) per fill'
            f' · Slippage: {st.slippage_ticks} ticks · Swap: long {st.swap_long:g}, short {st.swap_short:g} USD/lot/night'
            f' · Sizing: {st.qty_type.replace("_", " ")} {st.qty_value:g}'
            f' · Margin: {st.margin_percent if st.margin_percent else "off"}% · In-bar path: {st.intrabar}')
    net = m.get("net_profit", 0) or 0
    kpis = [
        ("Net profit", _num(net), f'{_num(m.get("net_profit_pct"), "pct")} on {_num(st.initial_capital)}', "pos" if net > 0 else "neg"),
        ("Max drawdown", _num(m.get("max_drawdown")), _num(m.get("max_drawdown_pct"), "pct"), ""),
        ("Profit factor", _num(m.get("profit_factor"), "ratio"), "gross profit ÷ gross loss", ""),
        ("Win rate", _num(m.get("percent_profitable"), "pct"), f'{_num(m.get("total_trades"), "int")} closed trades', ""),
        ("Avg trade", _num(m.get("avg_trade")), f'win/loss ratio {_num(m.get("win_loss_ratio"), "ratio")}', ""),
        ("Sharpe", _num(m.get("sharpe"), "ratio"), "monthly, rf 2%", ""),
    ]
    kpi_html = "".join(f'<div class="kpi"><span class="lbl">{k}</span><span class="val {c}">{v}</span>'
                       f'<span class="sub">{sub}</span></div>' for k, v, sub, c in kpis)
    evidence = getattr(s, "card", {}).get("evidence") if hasattr(s, "card") else None
    desc = html.escape(getattr(s, "description", "") or "")
    page_title = title or f"{s.name} backtest"
    params = ", ".join(f"{k}={v}" for k, v in vars(s.p).items())
    note = f'Chart shows the last {len(shown):,} of {len(d):,} bars.' if len(shown) < len(d) else ""

    body = TEMPLATE.format(
        title=html.escape(page_title), name=html.escape(s.name), desc=desc,
        symbol=html.escape(str(a.get("symbol", "XAUUSD"))), tf=html.escape(str(a.get("timeframe", ""))),
        start=f"{d.index[0]:%d %b %Y}", end=f"{d.index[-1]:%d %b %Y}", bars=f"{len(d):,}",
        source=html.escape(str(a.get("source", ""))), params=html.escape(params),
        evidence=f'<p class="evidence"><b>Evidence:</b> {html.escape(evidence)}</p>' if evidence else "",
        kpis=kpi_html, perf=perf_rows, risk=risk_rows, trades=tlist, months=_monthly_table(result.equity, st.initial_capital),
        validation=_validation_html(validation), cost=html.escape(cost), note=note,
        ntrades=f"{len(trades):,}", lwc=LWC, payload=payload,
        back=f'<a class="back" href="{html.escape(back_href)}">← All strategies</a>' if back_href else "",
    )
    if fragment:
        return body
    return ("<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">"
            "</head><body>\n" + body + "\n</body></html>\n")


def save(result, path: str | Path, validation: dict | None = None, fragment: bool = False) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(result, validation, fragment=fragment))
    return path


TEMPLATE = r"""<title>{title}</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@75..100,400..800&family=JetBrains+Mono:wght@400;600&display=swap">
<style>
/* Layout: a trading-desk report. Summary strip, then the chart, then the evidence tables. */
:root {{
  --bg: #f4f5f2; --panel: #ffffff; --ink: #1b1f24; --muted: #5d6670; --line: #dcdfd8;
  --gold: #805608; --gold-soft: #f1e3c2; --up: #1a6c48; --down: #a12e28; --up-soft: rgba(31,122,82,.14); --down-soft: rgba(178,58,50,.14);
  --display: "Archivo", "Helvetica Neue", Arial, sans-serif; --body: "Archivo", "Helvetica Neue", Arial, sans-serif;
  --mono: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg: #11151b; --panel: #171c24; --ink: #e7e9ec; --muted: #98a1ab; --line: #2a313b;
  --gold: #e0b252; --gold-soft: #3a3020; --up: #3fb984; --down: #f0675d; --up-soft: rgba(63,185,132,.18); --down-soft: rgba(240,103,93,.18);
  color-scheme: dark; }} }}
:root[data-theme="dark"] {{
  --bg: #11151b; --panel: #171c24; --ink: #e7e9ec; --muted: #98a1ab; --line: #2a313b;
  --gold: #e0b252; --gold-soft: #3a3020; --up: #3fb984; --down: #f0675d; --up-soft: rgba(63,185,132,.18); --down-soft: rgba(240,103,93,.18);
  color-scheme: dark; }}
body {{ background: var(--bg); color: var(--ink); font-family: var(--body); font-size: 15px; line-height: 1.5; }}
.wrap {{ max-width: 1180px; margin: 0 auto; padding-block: 28px 56px; padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); display: grid; gap: 28px; }}
header {{ display: grid; gap: 10px; }}
.eyebrow {{ font-family: var(--mono); font-size: 12px; letter-spacing: .08em; text-transform: uppercase; color: var(--gold); display: flex; flex-wrap: wrap; gap: 6px 14px; }}
h1 {{ font-family: var(--display); font-stretch: 82%; font-weight: 750; font-size: clamp(26px, 4vw, 40px); line-height: 1.08; margin: 0; text-wrap: balance; }}
h2 {{ font-family: var(--display); font-stretch: 88%; font-weight: 700; font-size: 19px; margin: 0 0 12px; }}
p {{ margin: 0; max-width: 72ch; }}
.muted, .sub {{ color: var(--muted); }}
.evidence {{ font-size: 14px; color: var(--muted); border-left: 3px solid var(--gold); padding-left: 10px; }}
code {{ font-family: var(--mono); font-size: 13px; background: var(--gold-soft); padding: 1px 5px; border-radius: 4px; }}
.kpis {{ display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); border: 1px solid var(--line); background: var(--panel); border-radius: 10px; }}
.kpi {{ display: grid; gap: 2px; padding: 14px 16px; border-right: 1px solid var(--line); min-width: 0; }}
.kpi:last-child {{ border-right: 0; }}
.kpi .lbl {{ font-size: 12px; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); }}
.kpi .val {{ font-family: var(--mono); font-size: 21px; font-weight: 600; font-variant-numeric: tabular-nums; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.kpi .sub {{ font-size: 12.5px; }}
.pos {{ color: var(--up); }} .neg {{ color: var(--down); }}
section {{ display: grid; gap: 10px; min-width: 0; }}
.chart-box {{ background: var(--panel); border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }}
#price {{ height: 460px; }} #equity {{ height: 220px; border-top: 1px solid var(--line); }}
.legend {{ display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: 13px; color: var(--muted); padding: 10px 14px; border-bottom: 1px solid var(--line); }}
.legend i {{ display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 6px; vertical-align: -1px; }}
.cols {{ display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 2fr); gap: 28px; }}
.scroll:focus-visible {{ outline: 2px solid var(--gold); outline-offset: 2px; }}
.scroll {{ overflow-x: auto; background: var(--panel); border: 1px solid var(--line); border-radius: 10px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 13.5px; }}
th, td {{ text-align: left; padding: 7px 12px; border-bottom: 1px solid var(--line); white-space: nowrap; }}
thead th {{ font-size: 12px; letter-spacing: .05em; text-transform: uppercase; color: var(--muted); font-weight: 600; position: sticky; top: 0; background: var(--panel); }}
tbody th {{ font-weight: 500; color: var(--muted); }}
td {{ font-family: var(--mono); font-variant-numeric: tabular-nums; }}
td.num {{ text-align: right; }}
tr:last-child th, tr:last-child td {{ border-bottom: 0; }}
.trades {{ max-height: 460px; overflow: auto; }}
table.kv tbody th {{ white-space: normal; min-width: 14ch; }}
.side {{ font-family: var(--body); font-size: 12px; font-weight: 600; padding: 1px 7px; border-radius: 99px; }}
.side.long {{ background: var(--up-soft); color: var(--up); }} .side.short {{ background: var(--down-soft); color: var(--down); }}
table.months td {{ text-align: right; font-size: 12.5px; }}
table.months td.pos {{ background: rgba(63,185,132, calc(var(--a) * .35)); color: var(--ink); }}
table.months td.neg {{ background: rgba(240,103,93, calc(var(--a) * .35)); color: var(--ink); }}
table.months td.yr {{ font-weight: 600; background: transparent; }}
table.months td.yr.pos {{ color: var(--up); }} table.months td.yr.neg {{ color: var(--down); }}
.chip {{ font-family: var(--body); font-size: 11.5px; font-weight: 700; letter-spacing: .05em; padding: 2px 8px; border-radius: 99px; }}
.chip.pass {{ background: var(--up-soft); color: var(--up); }} .chip.fail {{ background: var(--down-soft); color: var(--down); }}
.chip.warn {{ background: var(--gold-soft); color: var(--gold); }} .chip.info {{ background: var(--bg); color: var(--muted); box-shadow: inset 0 0 0 1px var(--line); }}
.verdict {{ font-weight: 600; }} .verdict.ready {{ color: var(--up); }} .verdict.not-ready {{ color: var(--down); }} .verdict.caution {{ color: var(--gold); }}
.settings {{ font-family: var(--mono); font-size: 12.5px; color: var(--muted); }}
footer {{ font-size: 12.5px; color: var(--muted); display: grid; gap: 4px; }}
footer a {{ color: var(--gold); }}
a.back {{ color: var(--gold); text-decoration: none; font-size: 14px; font-weight: 600; }}
a.back:hover, a.back:focus-visible {{ text-decoration: underline; }}
@media (max-width: 860px) {{ .kpis {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }} .kpi:nth-child(3n) {{ border-right: 0; }} .kpi:nth-child(-n+3) {{ border-bottom: 1px solid var(--line); }} .cols {{ grid-template-columns: minmax(0, 1fr); }} #price {{ height: 360px; }} }}
@media (max-width: 480px) {{ .kpis {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} .kpi {{ border-right: 0; border-bottom: 1px solid var(--line); }} .kpi:nth-child(odd) {{ border-right: 1px solid var(--line); }} .kpi:nth-last-child(-n+2) {{ border-bottom: 0; }} .kpi .val {{ font-size: 18px; }} }}
</style>
<div class="wrap">
  <header>
    {back}
    <div class="eyebrow"><span>{symbol} · {tf}</span><span>{start} → {end}</span><span>{bars} bars</span><span>data: {source}</span></div>
    <h1>{name}</h1>
    <p>{desc}</p>
    {evidence}
  </header>
  <main>
  <div class="kpis">{kpis}</div>
  <section>
    <div class="chart-box">
      <div class="legend" id="legend"><span><i style="background:var(--up)"></i>long entry / exit</span><span><i style="background:var(--down)"></i>short entry / exit</span><span class="muted">{note}</span></div>
      <div id="price"></div>
      <div id="equity"></div>
    </div>
  </section>
  <div class="cols">
    <section><h2>Performance</h2><div class="scroll" tabindex="0" role="region" aria-label="Performance"><table><thead><tr><th>Measure</th><th>All</th><th>Long</th><th>Short</th></tr></thead><tbody>{perf}</tbody></table></div></section>
    <section><h2>Risk and returns</h2><div class="scroll" tabindex="0" role="region" aria-label="Risk and returns"><table class="kv"><thead><tr><th>Measure</th><th>Value</th></tr></thead><tbody>{risk}</tbody></table></div></section>
  </div>
  <section><h2>Monthly returns (%)</h2>{months}</section>
  <section><h2>Is it ready to automate?</h2>{validation}</section>
  <section><h2>List of trades</h2><p class="muted">{ntrades} closed trades, newest first (up to 500 shown).</p>
    <div class="scroll trades" tabindex="0" role="region" aria-label="List of trades"><table><thead><tr><th>#</th><th>Side</th><th>Entry time (UTC)</th><th class="num">Entry</th><th>Exit time (UTC)</th><th class="num">Exit</th><th>Exit by</th><th class="num">Lots</th><th class="num">P&amp;L $</th><th class="num">Bars</th></tr></thead><tbody>{trades}</tbody></table></div></section>
  <section><h2>Assumptions</h2><p class="settings">{cost}</p><p class="muted">Parameters: {params}</p>
    <p class="muted">Fills follow TradingView's broker emulator: orders fill on the next bar, stops and targets are resolved along the open→nearest extreme→other extreme→close path. Past results don't guarantee future results.</p></section>
  </main>
  <footer><span>Generated by goldlab. Charts: <a href="https://www.tradingview.com/lightweight-charts/" target="_blank" rel="noopener">TradingView Lightweight Charts</a> (Apache-2.0).</span></footer>
</div>
<script src="{lwc}"></script>
<script>
(function () {{
  var D = {payload};
  if (!window.LightweightCharts) {{ document.getElementById('price').textContent = 'Chart library could not load (offline?). Tables below are complete.'; return; }}
  var L = window.LightweightCharts;
  function tok(n) {{ return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }}
  var palette = ['#3d7bd9', '#c46bd1', '#d98c3d', '#4bb3b3', '#8a8f3d'];
  function opts() {{
    return {{ autoSize: true, layout: {{ background: {{ color: tok('--panel') }}, textColor: tok('--muted'), fontFamily: 'JetBrains Mono, monospace', fontSize: 11 }},
      grid: {{ vertLines: {{ color: tok('--line') }}, horzLines: {{ color: tok('--line') }} }},
      rightPriceScale: {{ borderColor: tok('--line') }}, timeScale: {{ borderColor: tok('--line'), timeVisible: true, secondsVisible: false }},
      crosshair: {{ mode: 0 }} }};
  }}
  var price = L.createChart(document.getElementById('price'), opts());
  var candles = price.addSeries(L.CandlestickSeries, {{ upColor: tok('--up'), downColor: tok('--down'), borderVisible: false, wickUpColor: tok('--up'), wickDownColor: tok('--down') }});
  candles.setData(D.candles.map(function (c) {{ return {{ time: c[0], open: c[1], high: c[2], low: c[3], close: c[4] }}; }}));
  var legend = document.getElementById('legend'), k = 0;
  Object.keys(D.plots).forEach(function (name) {{
    var col = palette[k++ % palette.length];
    var s = price.addSeries(L.LineSeries, {{ color: col, lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false }});
    s.setData(D.plots[name].map(function (p) {{ return {{ time: p[0], value: p[1] }}; }}));
    var span = document.createElement('span'); span.innerHTML = '<i style="background:' + col + '"></i>'; span.appendChild(document.createTextNode(name)); legend.insertBefore(span, legend.lastElementChild);
  }});
  var mk = D.markers.map(function (m) {{
    var long = m[2] === 'long', entry = m[1] === 'entry';
    var up = entry ? long : !long;
    return {{ time: m[0], position: up ? 'belowBar' : 'aboveBar', shape: entry ? (long ? 'arrowUp' : 'arrowDown') : 'circle',
      color: long ? tok('--up') : tok('--down'), text: m[4], size: entry ? 1 : 0.6 }};
  }});
  L.createSeriesMarkers(candles, mk);
  var n = D.candles.length;
  if (n > 400) price.timeScale().setVisibleLogicalRange({{ from: n - 400, to: n }}); else price.timeScale().fitContent();

  var eqc = L.createChart(document.getElementById('equity'), opts());
  eqc.applyOptions({{ timeScale: {{ minBarSpacing: 0.001 }} }});
  var area = eqc.addSeries(L.AreaSeries, {{ lineColor: tok('--gold'), topColor: tok('--gold-soft'), bottomColor: 'rgba(0,0,0,0)', lineWidth: 2, priceLineVisible: false }});
  area.setData(D.equity.map(function (p) {{ return {{ time: p[0], value: p[1] }}; }}));
  var dd = eqc.addSeries(L.HistogramSeries, {{ color: tok('--down-soft'), priceScaleId: 'dd', priceLineVisible: false, lastValueVisible: false }});
  eqc.priceScale('dd').applyOptions({{ scaleMargins: {{ top: 0.75, bottom: 0 }} }});
  dd.setData(D.dd.map(function (p) {{ return {{ time: p[0], value: p[1], color: tok('--down-soft') }}; }}));
  area.createPriceLine({{ price: D.initial, color: tok('--muted'), lineStyle: 2, lineWidth: 1, title: 'start' }});
  eqc.timeScale().fitContent();

  function retheme() {{ [price, eqc].forEach(function (c) {{ c.applyOptions(opts()); }});
    candles.applyOptions({{ upColor: tok('--up'), downColor: tok('--down'), wickUpColor: tok('--up'), wickDownColor: tok('--down') }});
    area.applyOptions({{ lineColor: tok('--gold'), topColor: tok('--gold-soft') }}); }}
  try {{ window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', retheme); }} catch (e) {{}}
  new MutationObserver(retheme).observe(document.documentElement, {{ attributes: true, attributeFilter: ['data-theme'] }});
}})();
</script>"""
