"""Strategy Tester style performance metrics.

Names mirror TradingView's Strategy Report so numbers can be compared
side by side. A few extras (CAGR, Calmar, expectancy, exposure) are
added because they matter when deciding whether to automate.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


def _max_drawdown(curve: np.ndarray, low: np.ndarray | None = None):
    """Largest peak-to-trough fall. With `low`, troughs use intrabar worst equity."""
    if len(curve) == 0:
        return 0.0, 0.0
    trough = low if low is not None else curve
    peak = np.maximum.accumulate(np.concatenate([[curve[0]], curve]))[1:]
    peak = np.maximum(peak, curve)
    dd = peak - np.minimum(trough, curve)
    k = int(np.argmax(dd))
    return float(dd[k]), float(dd[k] / peak[k] * 100) if peak[k] else 0.0


def _max_runup(curve: np.ndarray, high: np.ndarray | None = None):
    if len(curve) == 0:
        return 0.0, 0.0
    top = high if high is not None else curve
    trough = np.minimum.accumulate(curve)
    ru = np.maximum(top, curve) - trough
    k = int(np.argmax(ru))
    return float(ru[k]), float(ru[k] / trough[k] * 100) if trough[k] else 0.0


def _streak(wins: np.ndarray, value: bool) -> int:
    best = cur = 0
    for w in wins:
        cur = cur + 1 if w == value else 0
        best = max(best, cur)
    return best


def monthly_returns(equity: pd.Series) -> pd.Series:
    """Month-over-month % change of month-end equity (first month vs initial capital)."""
    if equity.empty:
        return pd.Series(dtype=float)
    idx = equity.index.tz_convert(None) if equity.index.tz is not None else equity.index
    eq = pd.Series(equity.to_numpy(), index=idx)
    m = eq.groupby(eq.index.to_period("M")).last()
    return m.pct_change().dropna() * 100


def sharpe_sortino(equity: pd.Series, initial: float, rfr_annual: float = 2.0):
    """TradingView-style ratios from monthly returns: (mean - rfr/12) / std (or downside dev)."""
    if equity.empty:
        return float("nan"), float("nan")
    idx = equity.index.tz_convert(None) if equity.index.tz is not None else equity.index
    eq = pd.Series(equity.to_numpy(), index=idx).groupby(idx.to_period("M")).last()
    eq = pd.concat([pd.Series([initial]), eq.reset_index(drop=True)])
    r = eq.pct_change().dropna().to_numpy() * 100
    if len(r) < 2:
        return float("nan"), float("nan")
    rf = rfr_annual / 12
    ex = r - rf
    sd = r.std(ddof=0)  # TradingView divides by N (population standard deviation)
    sharpe = float(ex.mean() / sd) if sd > 0 else float("nan")
    downside = np.sqrt(np.mean(np.minimum(ex, 0) ** 2))
    sortino = float(ex.mean() / downside) if downside > 0 else float("nan")
    return sharpe, sortino


def compute(trades: pd.DataFrame, equity: pd.Series, equity_low: pd.Series, equity_high: pd.Series,
            data: pd.DataFrame, initial: float, open_pnl: float = 0.0, commission: float = 0.0,
            pos_size: pd.Series | None = None, rfr_annual: float = 2.0,
            realized: pd.Series | None = None) -> dict:
    m: dict = {}
    n = len(trades)
    pnl = trades["pnl"].to_numpy(float) if n else np.array([])
    wins = pnl > 0
    losses = pnl < 0
    gp = float(pnl[wins].sum()) if n else 0.0
    gl = float(-pnl[losses].sum()) if n else 0.0
    net = gp - gl

    m["net_profit"] = net
    m["net_profit_pct"] = net / initial * 100
    m["gross_profit"] = gp
    m["gross_loss"] = gl
    m["profit_factor"] = gp / gl if gl > 0 else (float("inf") if gp > 0 else float("nan"))
    m["commission_paid"] = commission
    m["open_pnl"] = open_pnl
    m["total_trades"] = n
    m["winning_trades"] = int(wins.sum())
    m["losing_trades"] = int(losses.sum())
    m["even_trades"] = int(n - wins.sum() - losses.sum())
    m["percent_profitable"] = wins.mean() * 100 if n else float("nan")
    m["avg_trade"] = net / n if n else float("nan")
    m["avg_trade_pct"] = trades["pnl_pct"].mean() if n else float("nan")
    m["avg_win"] = pnl[wins].mean() if wins.any() else float("nan")
    m["avg_loss"] = -pnl[losses].mean() if losses.any() else float("nan")
    m["win_loss_ratio"] = m["avg_win"] / m["avg_loss"] if wins.any() and losses.any() else float("nan")
    m["largest_win"] = pnl.max() if wins.any() else 0.0
    m["largest_loss"] = -pnl.min() if losses.any() else 0.0
    m["max_consecutive_wins"] = _streak(wins, True)
    m["max_consecutive_losses"] = _streak(losses, True)
    bars = trades["bars"].to_numpy() if n else np.array([])
    m["avg_bars_in_trade"] = bars.mean() if n else float("nan")
    m["avg_bars_in_wins"] = bars[wins].mean() if wins.any() else float("nan")
    m["avg_bars_in_losses"] = bars[losses].mean() if losses.any() else float("nan")
    m["expectancy_r"] = (m["percent_profitable"] / 100 * m["win_loss_ratio"]
                         - (1 - m["percent_profitable"] / 100)) if wins.any() and losses.any() else float("nan")
    if n:
        longs = trades["side"] == "long"
        m["long_trades"] = int(longs.sum())
        m["long_net_profit"] = float(trades.loc[longs, "pnl"].sum())
        m["short_trades"] = int((~longs).sum())
        m["short_net_profit"] = float(trades.loc[~longs, "pnl"].sum())

    eq = equity.to_numpy(float)
    lo = equity_low.to_numpy(float)
    if realized is not None and len(realized):
        # TradingView: the peak is the closed-trade equity high-water mark (open profits never
        # raise it); the trough is the worst intrabar equity while in a position.
        peak = np.maximum.accumulate(np.maximum(realized.to_numpy(float), initial))
        dd_arr = peak - np.minimum(lo, eq)
        k = int(np.argmax(dd_arr))
        dd, dd_pct = float(max(dd_arr[k], 0.0)), float(max(dd_arr[k], 0.0) / peak[k] * 100)
    else:
        dd, dd_pct = _max_drawdown(eq, lo)
    mdd, mdd_pct = _max_drawdown(eq, lo)
    cdd, cdd_pct = _max_drawdown(eq)
    ru, ru_pct = _max_runup(eq, equity_high.to_numpy(float))
    m["max_drawdown"] = dd                 # TradingView "Max equity drawdown (intrabar)"
    m["max_drawdown_pct"] = dd_pct
    m["max_drawdown_mtm"] = mdd            # stricter: peak includes open profits that were given back
    m["max_drawdown_mtm_pct"] = mdd_pct
    m["max_drawdown_close"] = cdd          # bar closes only
    m["max_drawdown_close_pct"] = cdd_pct
    m["max_runup"] = ru
    m["max_runup_pct"] = ru_pct
    m["return_over_max_dd"] = (net + open_pnl) / dd if dd > 0 else float("nan")

    sh, so = sharpe_sortino(equity, initial, rfr_annual)
    m["sharpe"] = sh
    m["sortino"] = so

    if len(data) > 1:
        # TradingView measures buy & hold from the price where the first position opened.
        first = float(trades["entry_price"].iloc[0]) if n else float(data["open"].iloc[0])
        last = float(data["close"].iloc[-1])
        m["buy_hold_return"] = (last - first) / first * initial
        m["buy_hold_return_pct"] = (last - first) / first * 100
        m["outperformance"] = net - m["buy_hold_return"]
        days = (data.index[-1] - data.index[0]).total_seconds() / 86400
        years = days / 365.0
        final = float(eq[-1]) if len(eq) else initial
        m["years"] = years
        m["cagr_pct"] = ((final / initial) ** (365.0 / days) - 1) * 100 if days > 0 and final > 0 else float("nan")
        m["calmar"] = m["cagr_pct"] / dd_pct if dd_pct > 0 else float("nan")
        m["trades_per_month"] = n / (years * 12) if years > 0 else float("nan")
    if pos_size is not None and len(pos_size):
        m["exposure_pct"] = float((pos_size.to_numpy() != 0).mean() * 100)
        m["max_lots_held"] = float(np.abs(pos_size.to_numpy()).max())
    return {k: (float(v) if isinstance(v, (np.floating, np.integer)) else v) for k, v in m.items()}


LABELS = {
    "net_profit": "Net profit", "net_profit_pct": "Net profit %", "gross_profit": "Gross profit",
    "gross_loss": "Gross loss", "profit_factor": "Profit factor", "commission_paid": "Commission paid",
    "open_pnl": "Open P&L", "swap_paid": "Overnight swap paid", "rejected_orders": "Orders skipped (too small)", "total_trades": "Total closed trades", "percent_profitable": "Percent profitable",
    "avg_trade": "Avg trade", "avg_win": "Avg winning trade", "avg_loss": "Avg losing trade",
    "win_loss_ratio": "Ratio avg win / avg loss", "largest_win": "Largest winning trade",
    "largest_loss": "Largest losing trade", "max_consecutive_wins": "Max consecutive wins",
    "max_consecutive_losses": "Max consecutive losses", "avg_bars_in_trade": "Avg # bars in trades",
    "max_drawdown": "Max equity drawdown (intrabar)", "max_drawdown_pct": "Max equity drawdown %",
    "max_runup": "Max equity run-up", "sharpe": "Sharpe ratio", "sortino": "Sortino ratio",
    "buy_hold_return": "Buy & hold return", "buy_hold_return_pct": "Buy & hold return %",
    "cagr_pct": "CAGR %", "calmar": "Calmar ratio", "expectancy_r": "Expectancy (R)",
    "exposure_pct": "Time in market %", "trades_per_month": "Trades per month",
    "return_over_max_dd": "Net profit / max drawdown",
}


def format_summary(m: dict, keys=None) -> str:
    keys = keys or ["net_profit", "net_profit_pct", "total_trades", "percent_profitable", "profit_factor",
                    "max_drawdown", "max_drawdown_pct", "avg_trade", "win_loss_ratio", "sharpe", "sortino",
                    "cagr_pct", "buy_hold_return_pct", "commission_paid", "swap_paid", "exposure_pct", "rejected_orders"]
    lines = []
    for k in keys:
        if k not in m:
            continue
        v = m[k]
        if isinstance(v, float):
            if math.isnan(v):
                s = "n/a"
            elif math.isinf(v):
                s = "inf"
            elif k.endswith("pct") or k in ("percent_profitable",):
                s = f"{v:,.2f}%"
            elif k in ("profit_factor", "sharpe", "sortino", "win_loss_ratio", "calmar", "expectancy_r"):
                s = f"{v:,.3f}"
            else:
                s = f"{v:,.2f}"
        else:
            s = str(v)
        lines.append(f"  {LABELS.get(k, k):<34} {s}")
    return "\n".join(lines)
