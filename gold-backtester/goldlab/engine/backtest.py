"""Run a strategy over bars and collect a Strategy-Tester-style result."""
from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from . import metrics as M
from .broker import Broker, Settings


@dataclass
class Result:
    strategy: object
    settings: Settings
    data: pd.DataFrame
    trades: pd.DataFrame
    equity: pd.Series
    equity_low: pd.Series
    equity_high: pd.Series
    position: pd.Series
    metrics: dict
    events: list = field(default_factory=list)
    open_trades: list = field(default_factory=list)

    def summary(self) -> str:
        a = self.data.attrs
        head = (f"{self.strategy.name} | {a.get('symbol', '?')} {a.get('timeframe', '')} "
                f"| {self.data.index[0]:%Y-%m-%d} -> {self.data.index[-1]:%Y-%m-%d} | {len(self.data):,} bars")
        return head + "\n" + M.format_summary(self.metrics)

    def bar_returns(self) -> pd.Series:
        return self.equity.pct_change().fillna(0.0)

    def daily_returns(self) -> pd.Series:
        eq = self.equity
        idx = eq.index.tz_convert(None) if eq.index.tz is not None else eq.index
        d = pd.Series(eq.to_numpy(), index=idx).resample("1D").last().dropna()
        d = pd.concat([pd.Series([self.settings.initial_capital], index=[d.index[0] - pd.Timedelta(days=1)]), d])
        return d.pct_change().dropna()

    def settings_dict(self) -> dict:
        return asdict(self.settings)


def run(strategy, data: pd.DataFrame, settings: Settings | None = None,
        magnifier: pd.DataFrame | None = None, warmup: int = 0) -> Result:
    """Backtest `strategy` on `data` (OHLC DataFrame indexed by UTC time).

    warmup: skip calling next() on the first N bars (indicators still forming).
    magnifier: optional lower-timeframe bars for TradingView's "Bar Magnifier" behaviour.
    """
    settings = settings or Settings()
    strat = copy.copy(strategy)
    strat.plots = {}
    broker = Broker(data, settings, magnifier=magnifier)
    strat._bind(data, broker)
    strat.init()
    n = len(data)
    for i in range(n):
        broker.process_bar(i)
        if i >= warmup:
            strat.next(i)
    broker.finish()

    trades = pd.DataFrame(broker.closed)
    if trades.empty:
        trades = pd.DataFrame(columns=["trade", "side", "entry_id", "entry_time", "entry_price", "entry_bar",
                                       "exit_id", "exit_time", "exit_price", "exit_bar", "qty", "lots",
                                       "pnl", "pnl_pct", "commission", "runup", "drawdown", "bars", "comment"])
    else:
        trades["cum_pnl"] = trades["pnl"].cumsum()
    idx = data.index
    equity = pd.Series(broker.equity_close, index=idx, name="equity")
    eq_lo = pd.Series(broker.equity_low, index=idx)
    eq_hi = pd.Series(broker.equity_high, index=idx)
    pos = pd.Series(broker.pos_size, index=idx, name="position")
    last = n - 1
    open_pnl = broker.open_profit(broker.c[last], broker.spread[last]) if broker.trades else 0.0
    realized = pd.Series(broker.realized, index=idx)
    mets = M.compute(trades, equity, eq_lo, eq_hi, data, settings.initial_capital, open_pnl,
                     broker.total_commission, pos / settings.contract_size, realized=realized)
    mets["swap_paid"] = (-broker.total_swap) or 0.0
    mets["rejected_orders"] = sum(1 for e in broker.events if e["kind"] == "rejected")
    open_trades = [{"entry_id": t.entry_id, "side": "long" if t.side > 0 else "short", "qty": t.qty,
                    "entry_price": t.entry_price, "entry_time": t.entry_time} for t in broker.trades]
    strat.broker = broker
    return Result(strat, settings, data, trades, equity, eq_lo, eq_hi, pos, mets, broker.events, open_trades)
