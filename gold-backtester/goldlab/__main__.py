"""Command line: python -m goldlab <command> ...

  backtest  <strategy> [--tf 4h] [--preset realistic|tradingview] [--start 2022-01-01] [--report]
  validate  <strategy> [--grid fast=20,50,100 slow=100,200]
  sweep     <strategy> --grid fast=20,50 slow=100,200
  pine      <strategy> [--out file.pine]
  journal   [strategy-slug]
  import-tv <trades.csv> --name "My TradingView strategy"
  new       "My strategy name" [--tf 15m]
  data      [--tf 1h] [--start 2024-01-01]          download/refresh Dukascopy data
  paper     <strategy> [--tf 15m] [--once]          run the live loop against the paper broker
  webhook   [--port 8080]                           receive TradingView alerts
  site      [--out public] [--quick]                build the static website (deployed to Vercel)
  serve     [--port 8000]                           preview the website and its backtester API locally
  list                                              list strategy files

<strategy> is a .yaml card or a .py file (path, or a name inside strategies/ or strategies/examples/).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .api import ROOT, backtest, get_data, load_strategy, make_settings


def _grid(items):
    out = {}
    for it in items or []:
        k, _, vals = it.partition("=")
        conv = []
        for v in vals.split(","):
            try:
                conv.append(int(v))
            except ValueError:
                conv.append(float(v))
        out[k] = conv
    return out


def cmd_backtest(a):
    from .journal import Journal
    from .report import save
    j = None if a.no_journal else Journal()
    res = backtest(a.strategy, a.tf, a.source, a.start, a.end, a.preset, journal=j, notes=a.notes or "",
                   magnifier=a.magnifier)
    print(res.summary())
    if res.run_id:
        print(f"\nRecorded in journal as run {res.run_id}")
    if a.report or a.out:
        out = Path(a.out or (ROOT / "journal" / "runs" / (res.run_id or "latest") / "report.html"))
        save(res, out)
        print(f"Report: {out}")


def cmd_validate(a):
    from .journal import Journal
    from .report import save
    from .validate import format_checks, validate
    s = load_strategy(a.strategy)
    tf = a.tf or s.timeframe or "1h"
    data = get_data(tf, a.source, a.start, a.end)
    st = make_settings(s, a.preset)
    v = validate(s, data, st, journal=None if a.no_journal else Journal(), grid=_grid(a.grid) or None,
                 quick=a.quick)
    print(format_checks(v))
    out = Path(a.out or (ROOT / "journal" / "reports" / f"{Path(str(a.strategy)).stem}-validation.html"))
    save(v["result"], out, validation=v)
    print(f"\nReport: {out}")


def cmd_sweep(a):
    from .journal import Journal
    from .validate import sweep
    s = load_strategy(a.strategy)
    tf = a.tf or s.timeframe or "1h"
    data = get_data(tf, a.source, a.start, a.end)
    table = sweep(s, data, _grid(a.grid), make_settings(s, a.preset), journal=Journal())
    print(table.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    print(f"\n{len(table)} trials recorded in the journal (they count toward the Deflated Sharpe check).")


def cmd_pine(a):
    from .pine import to_pine
    s = load_strategy(a.strategy)
    code = to_pine(s)
    if a.out:
        Path(a.out).write_text(code)
        print(f"Wrote {a.out}")
    else:
        print(code)


def cmd_journal(a):
    from .journal import Journal
    j = Journal()
    if a.slug:
        r = j.runs(a.slug)
        cols = [c for c in ("run_id", "kind", "timeframe", "start", "end", "net_profit", "profit_factor",
                            "total_trades", "max_drawdown_pct", "notes") if c in r]
        print(r[cols].tail(40).to_string(index=False))
        print(f"\nTrials recorded: {j.trial_count(a.slug)}")
    else:
        print(j.strategies().to_string(index=False))


def cmd_import_tv(a):
    from .journal import Journal
    out = Journal().import_tradingview(a.csv, a.name, notes=a.notes or "")
    print(json.dumps(out, indent=2, default=str))


TEMPLATE = """name: {name}
description: >
  Describe the idea in plain words: what you look for, when you enter,
  where the stop goes, when you take profit.
timeframe: {tf}
symbol: XAUUSD
tags: []
evidence: "my own idea"
params:
  fast: 20
  slow: 50
  atr_mult: 2.0
  target_r: 2.0
vars:
  fast_ma: ema(close, fast)
  slow_ma: ema(close, slow)
long:
  when: crossover(fast_ma, slow_ma)
  sl_dist: atr_mult * atr(14)
  tp_r: target_r
short:
  when: crossunder(fast_ma, slow_ma)
  sl_dist: atr_mult * atr(14)
  tp_r: target_r
plots:
  Fast MA: fast_ma
  Slow MA: slow_ma
settings:
  qty_type: risk_percent
  qty_value: 0.5
"""


def cmd_new(a):
    from .journal import slugify
    path = ROOT / "strategies" / f"{slugify(a.name).replace('-', '_')}.yaml"
    if path.exists():
        sys.exit(f"{path} already exists")
    path.write_text(TEMPLATE.format(name=a.name, tf=a.tf))
    print(f"Created {path}\nEdit it, then: python -m goldlab backtest {path.name} --report")


def cmd_list(a):
    for p in sorted((ROOT / "strategies").rglob("*")):
        if p.suffix in (".yaml", ".yml", ".py"):
            print(p.relative_to(ROOT))


def cmd_data(a):
    from .data import dukascopy
    df = dukascopy.load("XAUUSD", a.tf, start=a.start, end=a.end)
    print(df.tail())
    print(f"{len(df):,} bars cached under data/cache/dukascopy")


def cmd_paper(a):
    from .live.runner import main as live_main
    live_main(a.strategy, a.tf, broker=a.broker, once=a.once, config=a.config)


def cmd_site(a):
    from .site import build
    rows = build(Path(a.out), quick=a.quick)
    print(f"Built {len(rows)} strategy pages into {a.out}")


def cmd_serve(a):
    """Local preview of the website with a working /api/lab, like Vercel."""
    import json as _json
    from functools import partial
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import parse_qs, urlparse
    from .webapi import handle

    class H(SimpleHTTPRequestHandler):
        def _api(self, body):
            u = urlparse(self.path)
            op = (parse_qs(u.query).get("op") or [""])[0]
            code, out = handle(op, body)
            data = _json.dumps(out).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path.startswith("/api/lab"):
                return self._api(None)
            return super().do_GET()

        def do_POST(self):
            if not self.path.startswith("/api/lab"):
                self.send_error(404)
                return
            n = int(self.headers.get("Content-Length") or 0)
            self._api(_json.loads(self.rfile.read(n) or b"{}"))

        def log_message(self, *args):
            pass

    print(f"Serving {a.dir} with the backtester API on http://localhost:{a.port}")
    ThreadingHTTPServer(("127.0.0.1", a.port), partial(H, directory=a.dir)).serve_forever()


def cmd_webhook(a):
    from .live.webhook import serve
    serve(port=a.port, config=a.config)


def main(argv=None):
    p = argparse.ArgumentParser(prog="goldlab", description="TradingView-style gold backtester")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("strategy")
        sp.add_argument("--tf", help="timeframe: 1m 5m 15m 30m 1h 4h 1d (default: the card's)")
        sp.add_argument("--source", default="auto", help="auto | dukascopy | yahoo | csv")
        sp.add_argument("--start")
        sp.add_argument("--end")
        sp.add_argument("--preset", default="realistic", choices=["realistic", "tradingview", "custom"])
        sp.add_argument("--no-journal", action="store_true")
        sp.add_argument("--out")

    sp = sub.add_parser("backtest"); common(sp)
    sp.add_argument("--report", action="store_true"); sp.add_argument("--notes")
    sp.add_argument("--magnifier", action="store_true", help="resolve fills on lower-timeframe bars")
    sp.set_defaults(fn=cmd_backtest)
    sp = sub.add_parser("validate"); common(sp)
    sp.add_argument("--grid", nargs="*"); sp.add_argument("--quick", action="store_true")
    sp.set_defaults(fn=cmd_validate)
    sp = sub.add_parser("sweep"); common(sp); sp.add_argument("--grid", nargs="+", required=True)
    sp.set_defaults(fn=cmd_sweep)
    sp = sub.add_parser("pine"); sp.add_argument("strategy"); sp.add_argument("--out"); sp.set_defaults(fn=cmd_pine)
    sp = sub.add_parser("journal"); sp.add_argument("slug", nargs="?"); sp.set_defaults(fn=cmd_journal)
    sp = sub.add_parser("import-tv"); sp.add_argument("csv"); sp.add_argument("--name", required=True)
    sp.add_argument("--notes"); sp.set_defaults(fn=cmd_import_tv)
    sp = sub.add_parser("new"); sp.add_argument("name"); sp.add_argument("--tf", default="1h"); sp.set_defaults(fn=cmd_new)
    sp = sub.add_parser("list"); sp.set_defaults(fn=cmd_list)
    sp = sub.add_parser("data"); sp.add_argument("--tf", default="1h"); sp.add_argument("--start", default="2024-01-01")
    sp.add_argument("--end"); sp.set_defaults(fn=cmd_data)
    sp = sub.add_parser("paper"); sp.add_argument("strategy"); sp.add_argument("--tf")
    sp.add_argument("--broker", default="paper", choices=["paper", "oanda", "mt5"])
    sp.add_argument("--once", action="store_true"); sp.add_argument("--config", default=str(ROOT / "live.yaml"))
    sp.set_defaults(fn=cmd_paper)
    sp = sub.add_parser("site", help="build the static website")
    sp.add_argument("--out", default=str(ROOT / "public")); sp.add_argument("--quick", action="store_true")
    sp.set_defaults(fn=cmd_site)
    sp = sub.add_parser("serve", help="preview the website locally with the backtester API")
    sp.add_argument("--port", type=int, default=8000); sp.add_argument("--dir", default=str(ROOT / "public"))
    sp.set_defaults(fn=cmd_serve)
    sp = sub.add_parser("webhook"); sp.add_argument("--port", type=int, default=8080)
    sp.add_argument("--config", default=str(ROOT / "live.yaml")); sp.set_defaults(fn=cmd_webhook)
    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
