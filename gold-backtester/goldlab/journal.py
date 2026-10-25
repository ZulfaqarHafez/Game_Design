"""The strategy journal: a permanent, git-friendly record of everything you try.

Layout (all plain text, so `git diff` shows what changed):

    journal/
      strategies/<slug>/<fingerprint>.yaml   every version of every strategy
      runs.jsonl                             one line per backtest / sweep trial / import
      runs/<run_id>/                         trades.csv, equity.csv, report.html for full runs
      tradingview/<slug>/...                 trade lists you exported from TradingView

Why record every trial? A strategy that looks great after 200 variations is
much weaker evidence than one that looks great on the first try. The number
of trials per strategy (never decreasing) feeds the Deflated Sharpe Ratio in
goldlab.validate.
"""
from __future__ import annotations

import json
import re
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "journal"


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60] or "strategy"


def _git_commit() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              cwd=Path(__file__).parent, timeout=5).stdout.strip() or None
    except Exception:
        return None


def _clean(v):
    if isinstance(v, (np.floating,)):
        v = float(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
        return None
    if isinstance(v, (pd.Timestamp, datetime)):
        return v.isoformat()
    if isinstance(v, dict):
        return {k: _clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_clean(x) for x in v]
    return v


class Journal:
    def __init__(self, root: str | Path = DEFAULT_ROOT):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.runs_file = self.root / "runs.jsonl"

    # -- strategies ----------------------------------------------------
    def record_strategy(self, strategy) -> dict:
        slug = slugify(strategy.name)
        fp = strategy.fingerprint()
        d = self.root / "strategies" / slug
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{fp}.yaml"
        new = not path.exists()
        if new:
            snap = {"name": strategy.name, "fingerprint": fp, "first_seen": datetime.now(timezone.utc).isoformat(),
                    "kind": strategy.spec().get("kind"), "description": strategy.description}
            src = strategy.source()
            body = yaml.safe_dump(snap, sort_keys=False) + "---\n" + src
            path.write_text(body)
        return {"slug": slug, "fingerprint": fp, "path": str(path), "new_version": new}

    def strategies(self) -> pd.DataFrame:
        rows = []
        base = self.root / "strategies"
        if not base.exists():
            return pd.DataFrame(columns=["slug", "versions", "trials", "last_run"])
        runs = self.runs()
        for d in sorted(p for p in base.iterdir() if p.is_dir()):
            r = runs[runs["slug"] == d.name] if len(runs) else runs
            rows.append({"slug": d.name, "versions": len(list(d.glob("*.yaml"))), "trials": len(r),
                         "last_run": r["time"].max() if len(r) else None,
                         "best_net_profit": r["net_profit"].max() if len(r) and "net_profit" in r else None})
        return pd.DataFrame(rows)

    # -- runs ----------------------------------------------------------
    def record_run(self, result, kind: str = "backtest", group: str | None = None, notes: str = "",
                   save_artifacts: bool = True, extra: dict | None = None) -> str:
        strat = result.strategy
        info = self.record_strategy(strat)
        run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        a = result.data.attrs
        m = result.metrics
        monthly = _monthly(result.equity)
        row = {
            "run_id": run_id, "time": datetime.now(timezone.utc).isoformat(), "kind": kind, "group": group,
            "strategy": strat.name, "slug": info["slug"], "fingerprint": info["fingerprint"],
            "params": vars(strat.p), "symbol": a.get("symbol"), "timeframe": a.get("timeframe"),
            "source": a.get("source"), "start": str(result.data.index[0]), "end": str(result.data.index[-1]),
            "bars": len(result.data), "settings": result.settings_dict(), "metrics": m,
            "monthly_returns": monthly, "git": _git_commit(), "notes": notes, **(extra or {}),
        }
        with self.runs_file.open("a") as f:
            f.write(json.dumps(_clean(row), default=str) + "\n")
        if save_artifacts and kind == "backtest":
            d = self.root / "runs" / run_id
            d.mkdir(parents=True, exist_ok=True)
            result.trades.to_csv(d / "trades.csv", index=False)
            eq = result.equity
            step = max(1, len(eq) // 5000)
            eq.iloc[::step].to_csv(d / "equity.csv")
            (d / "summary.txt").write_text(result.summary() + "\n")
        return run_id

    def runs(self, slug: str | None = None, kind: str | None = None) -> pd.DataFrame:
        if not self.runs_file.exists():
            return pd.DataFrame(columns=["run_id", "slug", "kind", "time"])
        rows = []
        for line in self.runs_file.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            flat = {k: v for k, v in r.items() if k not in ("metrics", "settings", "monthly_returns")}
            flat.update({k: v for k, v in (r.get("metrics") or {}).items()})
            rows.append(flat)
        df = pd.DataFrame(rows)
        if slug is not None and len(df):
            df = df[df["slug"] == slug]
        if kind is not None and len(df):
            df = df[df["kind"] == kind]
        return df

    def run(self, run_id: str) -> dict:
        for line in self.runs_file.read_text().splitlines():
            if line.strip() and json.loads(line)["run_id"] == run_id:
                return json.loads(line)
        raise KeyError(run_id)

    def trial_count(self, slug: str) -> int:
        """Total variants ever tested for this strategy (backtests + sweep trials). Never decreases."""
        r = self.runs(slug)
        return int(len(r[r["kind"].isin(["backtest", "trial", "walkforward"])])) if len(r) else 0

    def trial_sharpes(self, slug: str) -> np.ndarray:
        """Monthly Sharpe of every recorded trial for this strategy (for the Deflated Sharpe Ratio)."""
        r = self.runs(slug)
        if not len(r) or "sharpe" not in r:
            return np.array([])
        return r["sharpe"].dropna().to_numpy(float)

    def trial_returns(self, slug: str) -> pd.DataFrame:
        """Monthly returns of every recorded trial, one column per run (for PBO)."""
        if not self.runs_file.exists():
            return pd.DataFrame()
        cols = {}
        for line in self.runs_file.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("slug") == slug and r.get("monthly_returns"):
                cols[r["run_id"]] = pd.Series(r["monthly_returns"])
        return pd.DataFrame(cols)

    # -- TradingView imports -------------------------------------------
    def import_tradingview(self, csv_path: str | Path, name: str, initial_capital: float = 10_000.0,
                           notes: str = "") -> dict:
        """Record a strategy you ran on TradingView from its exported "List of Trades" CSV."""
        trades = read_tradingview_trades(csv_path)
        slug = slugify(name)
        d = self.root / "tradingview" / slug
        d.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        trades.to_csv(d / f"{stamp}-trades.csv", index=False)
        pnl = trades["pnl"].to_numpy(float)
        wins, losses = pnl[pnl > 0], pnl[pnl < 0]
        eq = initial_capital + np.cumsum(pnl)
        peak = np.maximum.accumulate(np.concatenate([[initial_capital], eq]))[1:]
        m = {"net_profit": float(pnl.sum()), "total_trades": int(len(pnl)),
             "percent_profitable": float((pnl > 0).mean() * 100) if len(pnl) else None,
             "profit_factor": float(wins.sum() / -losses.sum()) if len(losses) else None,
             "avg_trade": float(pnl.mean()) if len(pnl) else None,
             "max_drawdown_close": float((peak - eq).max()) if len(eq) else 0.0}
        run_id = f"tv-{stamp}-{uuid.uuid4().hex[:4]}"
        row = {"run_id": run_id, "time": datetime.now(timezone.utc).isoformat(), "kind": "tradingview_import",
               "strategy": name, "slug": slug, "fingerprint": None, "params": {}, "source": str(csv_path),
               "start": str(trades["entry_time"].min()), "end": str(trades["exit_time"].max()),
               "metrics": m, "notes": notes}
        with self.runs_file.open("a") as f:
            f.write(json.dumps(_clean(row), default=str) + "\n")
        return {"run_id": run_id, "metrics": m, "trades": len(trades)}


def _monthly(equity: pd.Series) -> dict:
    if equity.empty:
        return {}
    idx = equity.index.tz_convert(None) if equity.index.tz is not None else equity.index
    m = pd.Series(equity.to_numpy(), index=idx).groupby(idx.to_period("M")).last()
    r = m.pct_change().dropna()
    return {str(k): round(float(v), 6) for k, v in r.items()}


def read_tradingview_trades(path: str | Path) -> pd.DataFrame:
    """Parse TradingView's Strategy report "List of trades" export (CSV; old and 2025+ layouts).

    Each trade appears as two rows (entry and exit) sharing a "Trade #".
    Returns one row per trade: trade, side, entry/exit time and price, qty, pnl.
    """
    raw = pd.read_csv(path)
    cols = {c: c.lower().strip() for c in raw.columns}
    raw = raw.rename(columns=cols)

    def find(*keys):
        for c in raw.columns:
            if all(k in c for k in keys):
                return c
        return None

    c_trade = find("trade")
    c_type = find("type")
    c_time = find("date") or find("time")
    c_price = find("price")
    c_qty = find("contracts") or find("size") or find("qty")
    c_pnl = find("net p&l") or find("profit") or find("p&l")
    c_sig = find("signal")
    if not all([c_trade, c_type, c_time, c_price, c_pnl]):
        raise ValueError(f"Unrecognised TradingView export columns: {list(raw.columns)}")
    num = lambda s: pd.to_numeric(s.astype(str).str.replace(",", "").str.replace("−", "-")
                                  .str.extract(r"(-?[\d.]+)")[0], errors="coerce")
    raw["_time"] = pd.to_datetime(raw[c_time], errors="coerce")
    raw["_price"] = num(raw[c_price])
    raw["_pnl"] = num(raw[c_pnl])
    raw["_qty"] = num(raw[c_qty]) if c_qty else np.nan
    rows = []
    for tid, g in raw.groupby(c_trade):
        typ = g[c_type].astype(str).str.lower()
        en = g[typ.str.contains("entry")]
        ex = g[typ.str.contains("exit")]
        if en.empty:
            continue
        side = "long" if "long" in typ.iloc[0] else "short"
        rows.append({"trade": tid, "side": side,
                     "entry_time": en["_time"].iloc[0], "entry_price": en["_price"].iloc[0],
                     "exit_time": ex["_time"].iloc[0] if len(ex) else pd.NaT,
                     "exit_price": ex["_price"].iloc[0] if len(ex) else np.nan,
                     "qty": en["_qty"].iloc[0], "pnl": (ex if len(ex) else en)["_pnl"].iloc[0],
                     "signal": en[c_sig].iloc[0] if c_sig else ""})
    return pd.DataFrame(rows).sort_values("entry_time").reset_index(drop=True)
