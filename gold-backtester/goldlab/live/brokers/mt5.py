"""MetaTrader 5 adapter via the official `MetaTrader5` Python package.

Windows only, and the MT5 terminal must be installed, logged in to your
broker and running (typically on a Windows VPS). Volumes are lots; this
adapter converts from ounces using the symbol's contract size. Orders carry
a magic number so the bot only touches its own positions.
"""
from __future__ import annotations

import hashlib
import os

import pandas as pd

from .base import BrokerAdapter, PendingOrder, Position

TF = {"1m": "TIMEFRAME_M1", "5m": "TIMEFRAME_M5", "15m": "TIMEFRAME_M15", "30m": "TIMEFRAME_M30",
      "1h": "TIMEFRAME_H1", "2h": "TIMEFRAME_H2", "4h": "TIMEFRAME_H4", "1d": "TIMEFRAME_D1", "1w": "TIMEFRAME_W1"}


class MT5Broker(BrokerAdapter):
    name = "mt5"

    def __init__(self, symbol: str = "XAUUSD", magic: int = 20261025, login: int | None = None,
                 server: str | None = None, password_env: str = "MT5_PASSWORD", terminal_path: str | None = None,
                 server_utc_offset_hours: float = 0.0, deviation_points: int = 20,
                 id_map_file: str = "journal/live/mt5_client_ids.json"):
        try:
            import MetaTrader5 as mt5
        except ImportError as e:
            raise RuntimeError("pip install MetaTrader5 (Windows only, with the MT5 terminal running)") from e
        self.mt5 = mt5
        kw = {}
        if terminal_path:
            kw["path"] = terminal_path
        if login:
            kw.update(login=int(login), server=server, password=os.environ.get(password_env, ""))
        if not mt5.initialize(**kw):
            raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(f"Symbol {symbol} not available (check your broker's exact name, e.g. XAUUSD.m)")
        self.symbol = symbol
        self.magic = magic
        self.info = mt5.symbol_info(symbol)
        self.contract = float(self.info.trade_contract_size or 100)
        self.offset = pd.Timedelta(hours=server_utc_offset_hours)
        self.deviation = deviation_points
        from pathlib import Path
        import json as _json
        self._map_path = Path(__file__).resolve().parents[3] / id_map_file
        self._map = _json.loads(self._map_path.read_text()) if self._map_path.exists() else {}
        self._json = _json
        fm = self.info.filling_mode
        self.filling = mt5.ORDER_FILLING_FOK if fm & 1 else (mt5.ORDER_FILLING_IOC if fm & 2 else mt5.ORDER_FILLING_RETURN)

    def _lots(self, qty_oz: float) -> float:
        step = self.info.volume_step or 0.01
        lots = round(round(qty_oz / self.contract / step) * step, 2)
        return max(lots, self.info.volume_min or 0.01)

    def _cid(self, client_id: str) -> str:
        tag = "gl" + hashlib.sha1(client_id.encode()).hexdigest()[:20]  # MT5 comments max 31 chars
        if self._map.get(tag) != client_id:
            self._map[tag] = client_id
            self._map_path.parent.mkdir(parents=True, exist_ok=True)
            self._map_path.write_text(self._json.dumps(self._map))
        return tag

    def _send(self, req: dict) -> dict:
        req.setdefault("magic", self.magic)
        req.setdefault("deviation", self.deviation)
        req.setdefault("type_time", self.mt5.ORDER_TIME_GTC)
        req.setdefault("type_filling", self.filling)
        chk = self.mt5.order_check(req)
        if chk is None or chk.retcode not in (0, self.mt5.TRADE_RETCODE_DONE):
            raise RuntimeError(f"MT5 order_check failed: {chk.comment if chk else self.mt5.last_error()}")
        res = self.mt5.order_send(req)
        if res is None or res.retcode not in (self.mt5.TRADE_RETCODE_DONE, self.mt5.TRADE_RETCODE_PLACED):
            raise RuntimeError(f"MT5 order_send failed: {res.retcode if res else ''} {res.comment if res else self.mt5.last_error()}")
        return res._asdict()

    # -- data ---------------------------------------------------------------
    def candles(self, timeframe, count=1500):
        rates = self.mt5.copy_rates_from_pos(self.symbol, getattr(self.mt5, TF[timeframe]), 0, count)
        df = pd.DataFrame(rates)
        df.index = pd.to_datetime(df["time"], unit="s", utc=True) - self.offset
        df.index.name = "time"
        df["spread"] = df["spread"] * self.info.point
        df = df.rename(columns={"tick_volume": "volume"})[["open", "high", "low", "close", "volume", "spread"]]
        df.attrs.update(symbol="XAUUSD", timeframe=timeframe, source="mt5")
        return df

    def quote(self):
        t = self.mt5.symbol_info_tick(self.symbol)
        return float(t.bid), float(t.ask)

    # -- account ------------------------------------------------------------
    def equity(self):
        return float(self.mt5.account_info().equity)

    def _positions(self):
        return [p for p in (self.mt5.positions_get(symbol=self.symbol) or []) if p.magic == self.magic]

    def position(self):
        ps = self._positions()
        if not ps:
            return Position(0, 0.0, 0.0)
        signed = sum((1 if p.type == self.mt5.POSITION_TYPE_BUY else -1) * p.volume for p in ps) * self.contract
        qty = abs(signed)
        avg = sum(p.price_open * p.volume for p in ps) / sum(p.volume for p in ps)
        return Position(1 if signed > 0 else -1, qty, avg, ps[0].sl or None, ps[0].tp or None, [p.ticket for p in ps])

    def pending_orders(self):
        m = self.mt5
        kinds = {m.ORDER_TYPE_BUY_STOP: (1, "stop"), m.ORDER_TYPE_SELL_STOP: (-1, "stop"),
                 m.ORDER_TYPE_BUY_LIMIT: (1, "limit"), m.ORDER_TYPE_SELL_LIMIT: (-1, "limit")}
        out = []
        for o in m.orders_get(symbol=self.symbol) or []:
            if o.magic != self.magic or o.type not in kinds:
                continue
            side, typ = kinds[o.type]
            out.append(PendingOrder(str(o.ticket), self._map.get(o.comment, o.comment), side, typ, o.volume_current * self.contract,
                                    o.price_open, o.sl or None, o.tp or None))
        return out

    # -- orders ---------------------------------------------------------------
    def market_order(self, side, qty, client_id, stop=None, take_profit=None):
        if self.find_client_order(client_id):
            return {"status": "duplicate"}
        bid, ask = self.quote()
        m = self.mt5
        req = {"action": m.TRADE_ACTION_DEAL, "symbol": self.symbol, "volume": self._lots(qty),
               "type": m.ORDER_TYPE_BUY if side > 0 else m.ORDER_TYPE_SELL, "price": ask if side > 0 else bid,
               "comment": self._cid(client_id)}
        if stop is not None:
            req["sl"] = float(stop)
        if take_profit is not None:
            req["tp"] = float(take_profit)
        return self._send(req)

    def pending_order(self, side, qty, type, price, client_id, stop=None, take_profit=None):
        m = self.mt5
        t = {(1, "stop"): m.ORDER_TYPE_BUY_STOP, (-1, "stop"): m.ORDER_TYPE_SELL_STOP,
             (1, "limit"): m.ORDER_TYPE_BUY_LIMIT, (-1, "limit"): m.ORDER_TYPE_SELL_LIMIT}[(side, type)]
        req = {"action": m.TRADE_ACTION_PENDING, "symbol": self.symbol, "volume": self._lots(qty), "type": t,
               "price": float(price), "comment": self._cid(client_id)}
        if stop is not None:
            req["sl"] = float(stop)
        if take_profit is not None:
            req["tp"] = float(take_profit)
        return self._send(req)

    def cancel(self, order):
        self._send({"action": self.mt5.TRADE_ACTION_REMOVE, "order": int(order.id)})

    def set_protection(self, stop, take_profit):
        for p in self._positions():
            self._send({"action": self.mt5.TRADE_ACTION_SLTP, "symbol": self.symbol, "position": p.ticket,
                        "sl": float(stop or 0.0), "tp": float(take_profit or 0.0)})

    def close_position(self, client_id):
        m = self.mt5
        bid, ask = self.quote()
        out = []
        for p in self._positions():
            buy = p.type == m.POSITION_TYPE_BUY
            out.append(self._send({"action": m.TRADE_ACTION_DEAL, "symbol": self.symbol, "volume": p.volume,
                                   "type": m.ORDER_TYPE_SELL if buy else m.ORDER_TYPE_BUY, "position": p.ticket,
                                   "price": bid if buy else ask, "comment": self._cid(client_id)}))
        return {"status": "closed" if out else "flat", "results": out}

    def find_client_order(self, client_id):
        tag = self._cid(client_id)
        now = pd.Timestamp.now(tz="UTC")
        deals = self.mt5.history_deals_get((now - pd.Timedelta(days=3)).to_pydatetime(), now.to_pydatetime()) or []
        if any(d.comment == tag for d in deals):
            return {"comment": tag}
        if any(o.comment == tag for o in (self.mt5.orders_get(symbol=self.symbol) or [])):
            return {"comment": tag}
        return None
