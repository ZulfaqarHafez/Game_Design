"""The interface every live broker adapter implements.

Units: quantities are OUNCES (1 lot = 100 oz), prices are USD per ounce,
side is +1 buy / -1 sell. Adapters convert to their own units (MT5 lots,
OANDA units) internally.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class Position:
    side: int          # +1 long, -1 short, 0 flat
    qty: float         # ounces, always >= 0
    avg_price: float
    stop: float | None = None
    take_profit: float | None = None
    trade_ids: list = field(default_factory=list)


@dataclass
class PendingOrder:
    id: str            # broker's id
    client_id: str     # our deterministic id
    side: int
    type: str          # stop | limit
    qty: float
    price: float
    stop: float | None = None
    take_profit: float | None = None


class BrokerAdapter:
    name = "base"
    symbol = "XAUUSD"

    # market data -------------------------------------------------------
    def candles(self, timeframe: str, count: int = 1500) -> pd.DataFrame:
        """Most recent bars (bid OHLC, UTC index, optional 'spread'), including the forming bar."""
        raise NotImplementedError

    def quote(self) -> tuple[float, float]:
        """(bid, ask)"""
        raise NotImplementedError

    # account -----------------------------------------------------------
    def equity(self) -> float:
        raise NotImplementedError

    def position(self) -> Position:
        raise NotImplementedError

    def pending_orders(self) -> list[PendingOrder]:
        raise NotImplementedError

    # orders ------------------------------------------------------------
    def market_order(self, side: int, qty: float, client_id: str, stop: float | None = None,
                     take_profit: float | None = None) -> dict:
        raise NotImplementedError

    def pending_order(self, side: int, qty: float, type: str, price: float, client_id: str,
                      stop: float | None = None, take_profit: float | None = None) -> dict:
        raise NotImplementedError

    def cancel(self, order: PendingOrder) -> None:
        raise NotImplementedError

    def set_protection(self, stop: float | None, take_profit: float | None) -> None:
        """Move the stop loss / take profit on the open position (used for trailing stops)."""
        raise NotImplementedError

    def close_position(self, client_id: str) -> dict:
        raise NotImplementedError

    def find_client_order(self, client_id: str) -> dict | None:
        """Look up an order we may already have sent (so a retry never doubles a trade)."""
        return None
