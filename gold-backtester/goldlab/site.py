"""Build the static website: an index of every strategy, a full report per strategy,
and the research report. Deployed to Vercel (see ../vercel.json).

    python -m goldlab site --out public [--quick]

Every card in strategies/ and strategies/examples/ is backtested with realistic
costs and validated, so pushing a new card to the repo adds it to the site.
"""
from __future__ import annotations

import html
import math
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from .api import ROOT, get_data, load_strategy, make_settings
from .journal import slugify
from .report import render
from .validate import validate

REPO = ROOT.parent
RESEARCH = REPO / "reports" / "TradingView gold backtest and automation.md"

CSS = """
:root {
  --bg: #f4f5f2; --panel: #ffffff; --ink: #1b1f24; --muted: #5d6670; --line: #dcdfd8;
  --gold: #9a6b12; --gold-soft: #f1e3c2; --up: #1f7a52; --down: #b23a32; --up-soft: rgba(31,122,82,.14); --down-soft: rgba(178,58,50,.14);
  --display: "Archivo", "Helvetica Neue", Arial, sans-serif; --body: "Archivo", "Helvetica Neue", Arial, sans-serif;
  --mono: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #11151b; --panel: #171c24; --ink: #e7e9ec; --muted: #98a1ab; --line: #2a313b;
  --gold: #e0b252; --gold-soft: #3a3020; --up: #3fb984; --down: #f0675d; --up-soft: rgba(63,185,132,.18); --down-soft: rgba(240,103,93,.18);
  color-scheme: dark; } }
:root[data-theme="dark"] {
  --bg: #11151b; --panel: #171c24; --ink: #e7e9ec; --muted: #98a1ab; --line: #2a313b;
  --gold: #e0b252; --gold-soft: #3a3020; --up: #3fb984; --down: #f0675d; --up-soft: rgba(63,185,132,.18); --down-soft: rgba(240,103,93,.18);
  color-scheme: dark; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink); font-family: var(--body); font-size: 16px; line-height: 1.55; }
.wrap { max-width: 1100px; margin: 0 auto; padding-block: 36px 64px; padding-left: max(16px, env(safe-area-inset-left, 0px));
  padding-right: max(16px, env(safe-area-inset-right, 0px)); display: grid; gap: 36px; }
.eyebrow { font-family: var(--mono); font-size: 12px; letter-spacing: .08em; text-transform: uppercase; color: var(--gold); }
h1 { font-family: var(--display); font-stretch: 80%; font-weight: 780; font-size: clamp(34px, 6vw, 60px); line-height: 1.02; margin: 6px 0 12px; text-wrap: balance; }
h2 { font-family: var(--display); font-stretch: 88%; font-weight: 700; font-size: 22px; margin: 0 0 12px; text-wrap: balance; }
h3 { font-family: var(--display); font-stretch: 90%; font-weight: 700; font-size: 18px; margin: 24px 0 8px; }
p, li { max-width: 70ch; }
p { margin: 0 0 12px; }
.lead { font-size: 18px; color: var(--muted); }
a { color: var(--gold); }
a:focus-visible { outline: 2px solid var(--gold); outline-offset: 2px; }
.facts { display: flex; flex-wrap: wrap; gap: 6px 22px; overflow-wrap: anywhere; font-family: var(--mono); font-size: 13px; color: var(--muted); }
.scroll { overflow-x: auto; background: var(--panel); border: 1px solid var(--line); border-radius: 10px; }
table { border-collapse: collapse; width: 100%; font-size: 14px; }
th, td { text-align: left; padding: 10px 14px; border-bottom: 1px solid var(--line); white-space: nowrap; }
thead th { font-size: 12px; letter-spacing: .05em; text-transform: uppercase; color: var(--muted); font-weight: 600; }
tr:last-child td { border-bottom: 0; }
td.num { font-family: var(--mono); font-variant-numeric: tabular-nums; text-align: right; }
th.num { text-align: right; }
.wrap > *, section { min-width: 0; }
td.name a { font-weight: 650; text-decoration: none; color: var(--ink); }
td.name a:hover { color: var(--gold); text-decoration: underline; }
td.name small { display: block; color: var(--muted); font-size: 12.5px; white-space: normal; max-width: 34ch; }
.pos { color: var(--up); } .neg { color: var(--down); }
.chip { display: inline-block; font-size: 11.5px; font-weight: 700; letter-spacing: .04em; padding: 2px 9px; border-radius: 99px; white-space: nowrap; }
.chip.ready { background: var(--up-soft); color: var(--up); } .chip.not-ready { background: var(--down-soft); color: var(--down); }
.chip.caution { background: var(--gold-soft); color: var(--gold); } .chip.level { background: var(--line); color: var(--muted); }
.grid2 { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 28px; }
.card { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 20px 22px; min-width: 0; }
.card ol, .card ul { margin: 0; padding-left: 20px; display: grid; gap: 6px; }
code { font-family: var(--mono); font-size: 13.5px; background: var(--gold-soft); padding: 1px 5px; border-radius: 4px; }
pre { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 12px 14px; overflow-x: auto; }
pre code { background: none; padding: 0; }
footer { font-size: 13px; color: var(--muted); display: grid; gap: 4px; border-top: 1px solid var(--line); padding-top: 18px; }
.doc { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: clamp(18px, 4vw, 44px); min-width: 0; }
.doc table { display: block; overflow-x: auto; font-size: 13.5px; }
.doc th, .doc td { white-space: normal; min-width: 12ch; vertical-align: top; }
.doc h1 { font-size: clamp(28px, 5vw, 44px); }
.doc h2 { margin-top: 36px; padding-top: 16px; border-top: 1px solid var(--line); }
.doc blockquote { margin: 0 0 12px; padding-left: 14px; border-left: 3px solid var(--gold); color: var(--muted); }
.back { font-weight: 600; text-decoration: none; font-size: 14px; }
@media (max-width: 760px) { .grid2 { grid-template-columns: minmax(0, 1fr); } }
@media (max-width: 640px) {
  table.list thead { display: none; }
  table.list, table.list tbody { display: block; }
  table.list tr { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px 12px; padding: 14px 16px;
    border-bottom: 1px solid var(--line); }
  table.list tr:last-child { border-bottom: 0; }
  table.list td { padding: 0; border: 0; white-space: normal; text-align: left; }
  table.list td.name { grid-column: 1 / -1; }
  table.list td[data-label]::before { content: attr(data-label); display: block; font-family: var(--body);
    font-size: 11px; letter-spacing: .05em; text-transform: uppercase; color: var(--muted); }
  table.list td.verdict { grid-column: 1 / -1; }
}
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
"""

HEAD = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@75..100,400..800&family=JetBrains+Mono:wght@400;600&display=swap">
<style>{css}</style></head><body>
"""


def _evidence_level(text: str | None) -> str:
    t = (text or "").strip()
    if t.lower().startswith("peer-reviewed"):
        return "Peer-reviewed"
    if t.lower().startswith("folklore"):
        return "Folklore"
    if "peer-reviewed" in t.lower():
        return "Partly supported"
    return "Weak or indirect" if t else "Your idea"


def _money(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "n/a"
    return f"{'-' if v < 0 else ''}${abs(v):,.0f}"


def _cards() -> list[Path]:
    mine = sorted((ROOT / "strategies").glob("*.yaml"))
    examples = sorted((ROOT / "strategies" / "examples").glob("*.yaml"))
    return mine + examples


def build(out: Path, quick: bool = False, max_candles: int = 8000) -> list[dict]:
    out = Path(out)
    tmp = out.with_name(out.name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    (tmp / "strategies").mkdir(parents=True)
    rows = []
    for path in _cards():
        t0 = time.time()
        s = load_strategy(path)
        tf = s.timeframe or "1h"
        data = get_data(tf)
        v = validate(s, data, make_settings(s, "realistic"), journal=None, quick=quick)
        slug = slugify(s.name)
        (tmp / "strategies" / f"{slug}.html").write_text(
            render(v["result"], v, title=f"{s.name} · Gold Strategy Lab", max_candles=max_candles,
                   back_href="../library.html"))
        m = v["metrics"]
        rows.append({"slug": slug, "name": s.name, "tf": tf, "mine": path.parent.name == "strategies",
                     "evidence": _evidence_level(s.card.get("evidence")), "desc": s.description,
                     "net": m["net_profit"], "pf": m.get("profit_factor"), "dd": m.get("max_drawdown_pct"),
                     "trades": m["total_trades"], "verdict": v["verdict"],
                     "start": data.index[0], "end": data.index[-1]})
        print(f"  {s.name}: {v['verdict']} ({time.time() - t0:.0f}s)", flush=True)
    (tmp / "library.html").write_text(_index(rows))
    web = ROOT / "web"
    for f in web.glob("*"):          # the interactive backtester is the home page
        if f.is_file():
            shutil.copy(f, tmp / f.name)
    if RESEARCH.exists():
        (tmp / "research.html").write_text(_research(RESEARCH.read_text()))
    shutil.rmtree(out, ignore_errors=True)
    tmp.rename(out)
    return rows


def _index(rows: list[dict]) -> str:
    label = {"ready": "Ready to paper trade", "caution": "Caution", "not-ready": "Not ready"}
    order = {"ready": 0, "caution": 1, "not-ready": 2}
    rows = sorted(rows, key=lambda r: (not r["mine"], order[r["verdict"]], -(r["net"] or 0)))
    trs = []
    for r in rows:
        pf = "n/a" if r["pf"] is None or (isinstance(r["pf"], float) and math.isnan(r["pf"])) else f"{r['pf']:.2f}"
        cls = "pos" if r["net"] > 0 else "neg"
        trs.append(
            f'<tr><td class="name"><a href="strategies/{r["slug"]}.html">{html.escape(r["name"])}</a>'
            f'<small>{"Your strategy · " if r["mine"] else ""}{html.escape(r["evidence"])}</small></td>'
            f'<td data-label="Timeframe">{r["tf"]}</td><td class="num {cls}" data-label="Net profit">{_money(r["net"])}</td>'
            f'<td class="num" data-label="Profit factor">{pf}</td>'
            f'<td class="num" data-label="Max DD">{r["dd"]:.1f}%</td><td class="num" data-label="Trades">{r["trades"]:,}</td>'
            f'<td class="verdict"><span class="chip {r["verdict"]}">{label[r["verdict"]]}</span></td></tr>')
    first = min(r["start"] for r in rows)
    last = max(r["end"] for r in rows)
    built = datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC")
    research_link = '<p><a href="research.html">Read the full research report →</a></p>' if RESEARCH.exists() else ""
    body = f"""<div class="wrap">
<header>
  <a class="back" href="./">← Open the backtester</a>
  <div class="eyebrow">XAUUSD · spot gold · strategy library</div>
  <h1>Gold Strategy Lab</h1>
  <p class="lead">Gold trading strategies backtested with TradingView's Strategy Tester rules, real bid/ask spreads,
  commission, slippage and overnight swap, then checked for whether the result can be trusted before automating.</p>
  <div class="facts"><span>Data: Dukascopy {first:%b %Y} – {last:%b %Y}</span><span>Account: $10,000</span>
  <span>Costs: spread + $7/lot + $0.05 slippage + swap</span><span>Built {built}</span></div>
</header>
<section>
  <h2>Strategies</h2>
  <div class="scroll"><table class="list">
    <thead><tr><th>Strategy</th><th>TF</th><th class="num">Net profit</th><th class="num">Profit factor</th>
    <th class="num">Max DD</th><th class="num">Trades</th><th>Verdict</th></tr></thead>
    <tbody>{''.join(trs)}</tbody></table></div>
  <p class="lead" style="font-size:15px;margin-top:12px">Each strategy page has the chart with every trade, the equity curve,
  monthly returns, the full trade list and the readiness checklist. "Ready" never means ready for real money:
  it means ready for a paper account.</p>
</section>
<div class="grid2">
  <section class="card">
    <h2>What the research found</h2>
    <ul>
      <li>TradingView licenses its data for display only and bans accounts that scrape it, so this lab copies TradingView's
      published fill rules and metric formulas and uses Dukascopy's free bid/ask history instead.</li>
      <li>Trend-following has peer-reviewed support for gold as part of diversified portfolios. Session breakouts and RSI
      mean reversion on gold are mostly folklore.</li>
      <li>Costs decide most intraday results. Overnight swap decides many swing results.</li>
      <li>Count every variant you try. The Deflated Sharpe check uses that count to separate an edge from luck.</li>
    </ul>
    {research_link}
  </section>
  <section class="card">
    <h2>Add your own strategy</h2>
    <ol>
      <li><code>python -m goldlab new "My idea" --tf 15m</code> creates a strategy card.</li>
      <li>Write the rules in plain expressions: <code>crossover(ema(close, 20), ema(close, 50))</code>.</li>
      <li><code>python -m goldlab validate my_idea</code> runs the checklist locally.</li>
      <li>Or open the <a href="./">backtester</a>, edit the rules in Settings → Rules, and save them in your browser.</li>
      <li>Commit the card to <code>strategies/</code> and the site lists it here permanently.</li>
    </ol>
  </section>
</div>
<footer>
  <span>Backtests describe the past and are not financial advice. Leveraged gold CFDs can lose more than you expect.</span>
  <span>Charts: <a href="https://www.tradingview.com/lightweight-charts/" target="_blank" rel="noopener">TradingView Lightweight Charts</a> (Apache-2.0).
  Price data: Dukascopy.</span>
</footer>
</div></body></html>"""
    return HEAD.format(title="Gold Strategy Lab", desc="Backtests of gold (XAUUSD) strategies with TradingView rules and realistic costs.",
                       css=CSS) + body


def _research(md_text: str) -> str:
    try:
        import markdown
        body = markdown.markdown(md_text, extensions=["tables", "fenced_code", "sane_lists"])
    except ImportError:
        body = f"<pre>{html.escape(md_text)}</pre>"
    return (HEAD.format(title="Gold research report · Gold Strategy Lab",
                        desc="How TradingView works, what can be reused, gold data, costs, validation and automation.", css=CSS)
            + f'<div class="wrap"><a class="back" href="./">← Backtester</a> · <a class="back" href="library.html">Library</a><article class="doc">{body}</article>'
            + '<footer><span>Not financial or legal advice.</span></footer></div></body></html>')
