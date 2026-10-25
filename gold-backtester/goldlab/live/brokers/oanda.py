"""OANDA v20 REST adapter (practice or live), instrument XAU_USD (1 unit = 1 oz).

Needs: an OANDA account (a free practice/demo account works), an API token
(set the env var named in live.yaml, never commit it) and the account id.
Check that your OANDA entity (e.g. OANDA Asia Pacific for Singapore) gives
v20 API access and offers XAU_USD before going live.
"""
from __future__ import annotations

import os

import pandas as pd
import requests

from .base import BrokerAdapter, PendingOrder, Position

HOSTS = {"practice": "https://api-fxpractice.oanda.com", "live": "https://api-fxtrade.oanda.com"}
GRAN = {"1m": "M1", "5m": "M5", "15m": "M15", "30m": "M30", "1h": "H1", "2h": "H2", "4h": "H4", "1d": "D", "1w": "W"}


class OandaBroker(BrokerAdapter):
    name = "oanda"

    def __init__(self, account_id: str, token_env: str = "OANDA_TOKEN", environment: str = "practice",
                 instrument: str = "XAU_USD", tag: str = "goldlab"):
        token = os.environ.get(token_env)
        if not token:
            raise RuntimeError(f"Set the {token_env} environment variable to your OANDA API token")
        if environment not in HOSTS:
            raise ValueError("environment must be 'practice' or 'live'")
        self.base = HOSTS[environment]
        self.acct = account_id
        self.inst = instrument
        self.tag = tag
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                               "Accept-Datetime-Format": "RFC3339"})

    def _req(self, method, path, **kw):
        r = self.s.request(method, f"{self.base}{path}", timeout=15, **kw)
        if r.status_code >= 400:
            raise RuntimeError(f"OANDA {method} {path} -> {r.status_code}: {r.text[:300]}")
        return r.json()

    @staticmethod
    def _px(x):
        return f"{x:.3f}"

    # -- data ---------------------------------------------------------------
    def candles(self, timeframe, count=1500):
        js = self._req("GET", f"/v3/instruments/{self.inst}/candles",
                       params={"granularity": GRAN[timeframe], "count": min(count, 5000), "price": "BA"})
        rows = []
        for c in js["candles"]:
            b, a = c["bid"], c["ask"]
            rows.append({"time": pd.Timestamp(c["time"]), "open": float(b["o"]), "high": float(b["h"]),
                         "low": float(b["l"]), "close": float(b["c"]), "volume": float(c["volume"]),
                         "spread": (float(a["o"]) - float(b["o"]) + float(a["c"]) - float(b["c"])) / 2,
                         "complete": c["complete"]})
        df = pd.DataFrame(rows).set_index("time")
        df.index = pd.DatetimeIndex(df.index).tz_convert("UTC")
        df.attrs.update(symbol="XAUUSD", timeframe=timeframe, source="oanda")
        return df

    def quote(self):
        js = self._req("GET", f"/v3/accounts/{self.acct}/pricing", params={"instruments": self.inst})
        p = js["prices"][0]
        return float(p["bids"][0]["price"]), float(p["asks"][0]["price"])

    # -- account ------------------------------------------------------------
    def equity(self):
        return float(self._req("GET", f"/v3/accounts/{self.acct}/summary")["account"]["NAV"])

    def _trades(self):
        js = self._req("GET", f"/v3/accounts/{self.acct}/openTrades")
        return [t for t in js["trades"] if t["instrument"] == self.inst]

    def position(self):
        trades = self._trades()
        if not trades:
            return Position(0, 0.0, 0.0)
        units = sum(float(t["currentUnits"]) for t in trades)
        qty = abs(units)
        avg = sum(float(t["price"]) * abs(float(t["currentUnits"])) for t in trades) / qty if qty else 0.0
        t0 = trades[0]
        stop = float(t0["stopLossOrder"]["price"]) if t0.get("stopLossOrder") else None
        tp = float(t0["takeProfitOrder"]["price"]) if t0.get("takeProfitOrder") else None
        return Position(1 if units > 0 else -1, qty, avg, stop, tp, [t["id"] for t in trades])

    def pending_orders(self):
        js = self._req("GET", f"/v3/accounts/{self.acct}/pendingOrders")
        out = []
        for o in js["orders"]:
            if o.get("instrument") != self.inst or o["type"] not in ("STOP", "LIMIT"):
                continue
            u = float(o["units"])
            out.append(PendingOrder(o["id"], (o.get("clientExtensions") or {}).get("id", ""), 1 if u > 0 else -1,
                                    o["type"].lower(), abs(u), float(o["price"]),
                                    float(o["stopLossOnFill"]["price"]) if o.get("stopLossOnFill") else None,
                                    float(o["takeProfitOnFill"]["price"]) if o.get("takeProfitOnFill") else None))
        return out

    # -- orders ---------------------------------------------------------------
    def _order(self, body):
        return self._req("POST", f"/v3/accounts/{self.acct}/orders", json={"order": body})

    def _common(self, side, qty, client_id, stop, take_profit):
        body = {"instrument": self.inst, "units": str(int(round(side * qty))), "positionFill": "DEFAULT",
                "clientExtensions": {"id": client_id[:120], "tag": self.tag}}
        if stop is not None:
            body["stopLossOnFill"] = {"price": self._px(stop), "timeInForce": "GTC"}
        if take_profit is not None:
            body["takeProfitOnFill"] = {"price": self._px(take_profit), "timeInForce": "GTC"}
        return body

    def market_order(self, side, qty, client_id, stop=None, take_profit=None):
        if self.find_client_order(client_id):
            return {"status": "duplicate", "client_id": client_id}
        body = self._common(side, qty, client_id, stop, take_profit)
        body.update(type="MARKET", timeInForce="FOK")
        return self._order(body)

    def pending_order(self, side, qty, type, price, client_id, stop=None, take_profit=None):
        if self.find_client_order(client_id):
            return {"status": "duplicate", "client_id": client_id}
        body = self._common(side, qty, client_id, stop, take_profit)
        body.update(type=type.upper(), price=self._px(price), timeInForce="GTC")
        return self._order(body)

    def cancel(self, order):
        self._req("PUT", f"/v3/accounts/{self.acct}/orders/{order.id}/cancel")

    def set_protection(self, stop, take_profit):
        for tid in self.position().trade_ids:
            body = {}
            if stop is not None:
                body["stopLoss"] = {"price": self._px(stop), "timeInForce": "GTC"}
            if take_profit is not None:
                body["takeProfit"] = {"price": self._px(take_profit), "timeInForce": "GTC"}
            if body:
                self._req("PUT", f"/v3/accounts/{self.acct}/trades/{tid}/orders", json=body)

    def close_position(self, client_id):
        pos = self.position()
        if pos.side == 0:
            return {"status": "flat"}
        body = {"longUnits": "ALL"} if pos.side > 0 else {"shortUnits": "ALL"}
        return self._req("PUT", f"/v3/accounts/{self.acct}/positions/{self.inst}/close", json=body)

    def find_client_order(self, client_id):
        try:
            return self._req("GET", f"/v3/accounts/{self.acct}/orders/@{client_id[:120]}")
        except RuntimeError:
            return None
