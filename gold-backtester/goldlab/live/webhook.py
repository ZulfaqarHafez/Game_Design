"""Receive TradingView strategy alerts and execute them through a broker.

Keep TradingView as the signal source if you prefer: put this JSON in the
alert's "Message" box (strategy alerts fill in the {{...}} placeholders):

    {"secret": "<your secret>", "strategy": "london-breakout",
     "action": "{{strategy.order.action}}", "target_position": {{strategy.position_size}},
     "price": {{strategy.order.price}}, "id": "{{strategy.order.id}}-{{time}}", "time": "{{timenow}}"}

target_position is in TradingView units (ounces for most XAUUSD CFD symbols).
Sending the target (not just "buy"/"sell") means one lost alert fixes itself on
the next one. TradingView requires 2FA and a paid plan for webhooks, only
calls ports 80/443, and gives the server 3 seconds to answer, so this server
answers immediately and does the work on a background thread.

Run behind HTTPS (e.g. Caddy or nginx on 443 forwarding to this port).
"""
from __future__ import annotations

import hmac
import json
import os
import queue
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pandas as pd

from ..api import ROOT
from .risk import RiskConfig, RiskGuard
from .runner import load_config, make_broker

TRADINGVIEW_IPS = ["52.89.214.238", "34.212.75.30", "54.218.53.128", "52.32.178.7"]


class AlertProcessor:
    def __init__(self, broker, risk: RiskGuard, cfg: dict, state_dir: Path):
        self.b = broker
        self.risk = risk
        self.cfg = cfg
        self.dir = state_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self.seen_path = self.dir / "seen_alerts.json"
        self.seen = set(json.loads(self.seen_path.read_text())) if self.seen_path.exists() else set()
        self.audit = self.dir / "audit.jsonl"
        self.q: queue.Queue = queue.Queue()
        threading.Thread(target=self._worker, daemon=True).start()

    def log(self, event, **kw):
        row = {"time": datetime.now(timezone.utc).isoformat(), "event": event, **kw}
        with self.audit.open("a") as f:
            f.write(json.dumps(row, default=str) + "\n")
        print(json.dumps(row, default=str)[:400], flush=True)

    def validate(self, msg: dict, ip: str) -> str | None:
        wc = self.cfg
        secret = os.environ.get(wc.get("secret_env", "GOLDLAB_WEBHOOK_SECRET"), "")
        if not secret:
            return "server has no secret configured"
        if not hmac.compare_digest(str(msg.get("secret", "")), secret):
            return "bad secret"
        allowed = wc.get("allowed_ips", TRADINGVIEW_IPS)
        if allowed and ip not in allowed:
            return f"ip {ip} not allowed"
        if "id" not in msg or ("target_position" not in msg and msg.get("action") not in ("close", "flat")):
            return "message needs id and target_position (or action close)"
        if msg["id"] in self.seen:
            return "duplicate"
        if msg.get("time"):
            age = (pd.Timestamp.now(tz="UTC") - pd.Timestamp(msg["time"])).total_seconds()
            if age > wc.get("max_age_seconds", 60):
                return f"stale alert ({age:.0f}s old)"
        return None

    def submit(self, msg: dict):
        self.seen.add(msg["id"])
        self.seen_path.write_text(json.dumps(sorted(self.seen)[-2000:]))
        self.q.put(msg)

    def _worker(self):
        while True:
            msg = self.q.get()
            try:
                self.execute(msg)
            except Exception as e:
                self.log("error", id=msg.get("id"), error=repr(e))

    def execute(self, msg: dict):
        pos = self.b.position()
        cur = pos.side * pos.qty
        scale = float(self.cfg.get("units_per_tradingview_unit", 1.0))
        target = 0.0 if msg.get("action") in ("close", "flat") else float(msg["target_position"]) * scale
        cid = f"tv-{msg['id']}"[:120]
        if abs(target - cur) < 1e-9:
            self.log("noop", id=msg["id"], position=cur)
            return
        if cur != 0 and (target == 0 or (target > 0) != (cur > 0)):
            self.log("close", id=msg["id"], result=self.b.close_position(cid + "-c"))
            cur = 0.0
        delta = target - cur
        if abs(delta) < 1e-9:
            return
        side = 1 if delta > 0 else -1
        bid, ask = self.b.quote()
        px = ask if side > 0 else bid
        dist = float(self.cfg.get("emergency_stop_dist", 15.0))  # broker-side stop every position must carry
        stop = msg.get("sl") or (px - side * dist)
        blocked = self.risk.check(side=side, qty=abs(delta), price=px, stop=stop, equity=self.b.equity(),
                                  position_qty=abs(cur), spread=ask - bid, market=bid)
        if blocked:
            self.log("blocked", id=msg["id"], reasons=blocked)
            return
        r = self.b.market_order(side, abs(delta), cid, stop, msg.get("tp"))
        self.risk.record_order()
        self.log("order", id=msg["id"], side=side, qty=abs(delta), stop=stop, result=r)


def serve(port: int = 8080, config: str | Path = ROOT / "live.yaml"):
    cfg = load_config(config)
    wc = cfg.get("webhook", {})
    broker_name = wc.get("broker", "paper")
    state_dir = ROOT / "journal" / "live" / f"webhook-{broker_name}"
    names = set(RiskConfig.__dataclass_fields__)
    risk = RiskGuard(RiskConfig(**{k: v for k, v in (cfg.get("risk") or {}).items() if k in names}),
                     state_dir / "risk_state.json", ROOT)
    proc = AlertProcessor(make_broker(broker_name, cfg, state_dir), risk, wc, state_dir)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0) or 0)
            body = self.rfile.read(min(n, 10_000))
            ip = self.headers.get("X-Forwarded-For", self.client_address[0]).split(",")[0].strip()
            try:
                msg = json.loads(body)
            except ValueError:
                msg = None
            err = "body is not JSON" if msg is None else proc.validate(msg, ip)
            if err:
                proc.log("rejected", ip=ip, reason=err)
                self.send_response(200 if err == "duplicate" else 400)
            else:
                proc.submit(msg)
                self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok" if not err else err.encode())

        def log_message(self, *a):
            pass

    print(f"Listening for TradingView alerts on :{port} (broker: {broker_name})")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
