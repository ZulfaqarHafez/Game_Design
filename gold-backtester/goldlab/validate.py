"""Checks that decide whether a backtest is trustworthy enough to paper-trade.

Implements the methods from the research notes:
  * Deflated Sharpe Ratio (Bailey & Lopez de Prado, 2014) using the journal's trial count
  * Minimum backtest length for the number of trials (Bailey et al., 2014)
  * Probability of Backtest Overfitting via CSCV (Bailey et al., 2017)
  * Walk-forward optimisation and efficiency
  * Parameter plateau (+/-20% perturbation), cost stress (1.5x, 2x), pessimistic fills
  * Monte Carlo bootstrap of trades, minimum trade count, look-ahead (truncation) test
Thresholds marked "heuristic" are engineering rules of thumb, not published results.
"""
from __future__ import annotations

import copy
import itertools
import math
from dataclasses import replace
from statistics import NormalDist

import numpy as np
import pandas as pd

from .engine import Settings, run

N01 = NormalDist()
EULER = 0.5772156649


# ---------------------------------------------------------------------------
# statistics
# ---------------------------------------------------------------------------

def expected_max_sharpe(n_trials: int, sr_std: float = 1.0) -> float:
    """Expected maximum of N independent Sharpe ratios with the given spread (null of zero skill)."""
    if n_trials <= 1:
        return 0.0
    return sr_std * ((1 - EULER) * N01.inv_cdf(1 - 1 / n_trials) + EULER * N01.inv_cdf(1 - 1 / (n_trials * math.e)))


def deflated_sharpe(sr: float, n_obs: int, n_trials: int, sr_var: float, skew: float = 0.0,
                    kurt: float = 3.0) -> float:
    """Probability that the true Sharpe is above zero after accounting for N trials.

    sr, sr_var: per-period (e.g. daily, not annualised) Sharpe and the variance of the
    trials' Sharpes. kurt is raw kurtosis (3 for normal returns).
    """
    sr0 = expected_max_sharpe(n_trials, math.sqrt(max(sr_var, 0.0))) if n_trials > 1 else 0.0
    denom = 1 - skew * sr + (kurt - 1) / 4 * sr ** 2
    if denom <= 0 or n_obs < 3:
        return float("nan")
    z = (sr - sr0) * math.sqrt(n_obs - 1) / math.sqrt(denom)
    return N01.cdf(z)


def min_backtest_years(n_trials: int, target_annual_sr: float = 1.0) -> float:
    """Years of data needed so that the best of N skill-less trials is not expected to show target SR."""
    return (expected_max_sharpe(n_trials) / target_annual_sr) ** 2


def pbo(returns: pd.DataFrame, n_blocks: int = 16) -> float:
    """Probability of Backtest Overfitting by combinatorially symmetric cross-validation.

    returns: T x N matrix (rows = periods, columns = strategy variants).
    """
    m = returns.dropna(how="any").to_numpy(float)
    t, n = m.shape
    if n < 2 or t < n_blocks * 2:
        return float("nan")
    blocks = np.array_split(np.arange(t), n_blocks)
    logits = []
    for combo in itertools.combinations(range(n_blocks), n_blocks // 2):
        is_idx = np.concatenate([blocks[k] for k in combo])
        oos_idx = np.concatenate([blocks[k] for k in range(n_blocks) if k not in combo])
        def sharpe(x):
            sd = x.std(axis=0, ddof=1)
            return np.where(sd > 0, x.mean(axis=0) / np.where(sd > 0, sd, 1), 0.0)
        is_sr, oos_sr = sharpe(m[is_idx]), sharpe(m[oos_idx])
        best = int(np.argmax(is_sr))
        rank = (oos_sr < oos_sr[best]).sum() + 0.5 * ((oos_sr == oos_sr[best]).sum() - 1) + 1
        w = rank / (n + 1)
        logits.append(math.log(w / (1 - w)))
    return float(np.mean(np.array(logits) <= 0))


def return_stats(result) -> dict:
    r = result.daily_returns()
    r = r[r != 0] if (r != 0).sum() > 20 else r
    if len(r) < 3 or r.std() == 0:
        return {"daily_sharpe": float("nan"), "annual_sharpe": float("nan"), "skew": 0.0, "kurt": 3.0, "n_days": len(r)}
    sr = r.mean() / r.std(ddof=1)
    return {"daily_sharpe": float(sr), "annual_sharpe": float(sr * math.sqrt(252)), "skew": float(r.skew()),
            "kurt": float(r.kurt() + 3), "n_days": int(len(r))}


def monte_carlo(trades: pd.DataFrame, initial: float, n: int = 5000, seed: int = 7) -> dict:
    """Bootstrap the trade sequence to see how lucky the ordering was."""
    p = trades["pnl"].to_numpy(float)
    if len(p) < 5:
        return {}
    rng = np.random.default_rng(seed)
    sims = rng.choice(p, size=(n, len(p)), replace=True)
    eq = initial + np.cumsum(sims, axis=1)
    peak = np.maximum.accumulate(np.concatenate([np.full((n, 1), initial), eq], axis=1), axis=1)[:, 1:]
    dd = ((peak - eq) / peak).max(axis=1) * 100
    final = eq[:, -1]
    return {"final_p5": float(np.percentile(final, 5)), "final_p50": float(np.percentile(final, 50)),
            "final_p95": float(np.percentile(final, 95)), "max_dd_p50": float(np.percentile(dd, 50)),
            "max_dd_p95": float(np.percentile(dd, 95)), "prob_loss": float((final < initial).mean())}


# ---------------------------------------------------------------------------
# experiments
# ---------------------------------------------------------------------------

def _with_params(strategy, **params):
    s = copy.copy(strategy)
    s.p = copy.copy(strategy.p)
    for k, v in params.items():
        setattr(s.p, k, v)
    return s


def sweep(strategy, data: pd.DataFrame, grid: dict, settings: Settings, journal=None, group: str | None = None,
          metric: str = "net_profit") -> pd.DataFrame:
    """Run every combination in `grid`. Each run is recorded in the journal as a trial."""
    keys = list(grid)
    rows = []
    group = group or f"sweep-{pd.Timestamp.now():%Y%m%d-%H%M%S}"
    for combo in itertools.product(*(grid[k] for k in keys)):
        params = dict(zip(keys, combo))
        res = run(_with_params(strategy, **params), data, settings)
        res.metrics.update(return_stats(res))
        if journal is not None:
            journal.record_run(res, kind="trial", group=group, save_artifacts=False)
        rows.append({**params, **{k: res.metrics.get(k) for k in
                                  ("net_profit", "profit_factor", "max_drawdown", "total_trades", "sharpe",
                                   "annual_sharpe", "percent_profitable")}})
    return pd.DataFrame(rows).sort_values(metric, ascending=False).reset_index(drop=True)


def walk_forward(strategy, data: pd.DataFrame, grid: dict, settings: Settings, folds: int = 5,
                 train_frac: float = 0.7, metric: str = "net_profit", journal=None) -> dict:
    """Rolling walk-forward: optimise on each training window, then test the winner on the next slice."""
    # windows: [train | test] slides forward by one test length each fold
    n = len(data)
    seg = int(n / (folds + train_frac / (1 - train_frac)))
    rows = []
    train_len = int(seg * train_frac / (1 - train_frac))
    for k in range(folds):
        start = k * seg
        tr = data.iloc[start: start + train_len]
        te = data.iloc[start + train_len: start + train_len + seg]
        if len(tr) < 100 or len(te) < 20:
            continue
        table = sweep(strategy, tr, grid, settings, journal=journal, group=f"wf-fold{k}")
        best = {key: (int(table.iloc[0][key]) if isinstance(grid[key][0], int) else float(table.iloc[0][key]))
                for key in grid}
        is_res = run(_with_params(strategy, **best), tr, settings)
        oos = run(_with_params(strategy, **best), te, settings)
        days_is = max((tr.index[-1] - tr.index[0]).days, 1)
        days_oos = max((te.index[-1] - te.index[0]).days, 1)
        rows.append({"fold": k, "train": f"{tr.index[0]:%Y-%m-%d}..{tr.index[-1]:%Y-%m-%d}",
                     "test": f"{te.index[0]:%Y-%m-%d}..{te.index[-1]:%Y-%m-%d}", "params": best,
                     "is_profit": is_res.metrics["net_profit"], "oos_profit": oos.metrics["net_profit"],
                     "is_per_year": is_res.metrics["net_profit"] / days_is * 365,
                     "oos_per_year": oos.metrics["net_profit"] / days_oos * 365,
                     "oos_trades": oos.metrics["total_trades"]})
    df = pd.DataFrame(rows)
    if df.empty:
        return {"folds": df, "efficiency": float("nan"), "oos_win_rate": float("nan")}
    is_rate = df["is_per_year"].mean()
    eff = df["oos_per_year"].mean() / is_rate if is_rate > 0 else float("nan")
    return {"folds": df, "efficiency": float(eff), "oos_win_rate": float((df["oos_profit"] > 0).mean())}


def lookahead_test(strategy, data: pd.DataFrame, settings: Settings, n_cuts: int = 12, warmup: float = 0.2) -> dict:
    """Truncation test: the orders placed on a bar must be the same whether or not later bars exist.

    The data is cut at several points; for each cut the orders placed on the LAST visible bar
    are compared with the orders the full run placed on that same bar. Any difference means the
    strategy used information from the future.
    """
    full = run(strategy, data, settings).strategy.broker.placed
    by_bar: dict = {}
    for row in full:
        by_bar.setdefault(row[0], []).append(row[1:])
    n = len(data)
    cuts = np.unique(np.linspace(int(n * warmup), n - 2, n_cuts).astype(int))
    problems = []
    for k in cuts:
        part = run(strategy, data.iloc[: k + 1], settings).strategy.broker.placed
        mine = sorted(r[1:] for r in part if r[0] == k)
        theirs = sorted(by_bar.get(k, []))
        if mine != theirs:
            problems.append(f"orders on {data.index[k]:%Y-%m-%d %H:%M} change when later bars are removed")
    return {"ok": not problems, "problems": problems, "cuts": len(cuts)}


def plateau(strategy, data: pd.DataFrame, settings: Settings, base_profit: float, pct: float = 0.2) -> dict:
    """Nudge each numeric parameter by +/-20%: a robust strategy degrades gently."""
    rows = []
    for k, v in vars(strategy.p).items():
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v == 0:
            continue
        for f in (1 - pct, 1 + pct):
            nv = type(v)(round(v * f)) if isinstance(v, int) else v * f
            if nv == v:
                nv = v + (1 if f > 1 else -1) if isinstance(v, int) else nv
            if isinstance(v, int) and nv < 1:
                continue
            res = run(_with_params(strategy, **{k: nv}), data, settings)
            rows.append({"param": k, "value": nv, "net_profit": res.metrics["net_profit"]})
    df = pd.DataFrame(rows)
    if df.empty or base_profit <= 0:
        return {"table": df, "median_ratio": float("nan"), "negatives": int((df["net_profit"] < 0).sum()) if len(df) else 0}
    return {"table": df, "median_ratio": float(df["net_profit"].median() / base_profit),
            "negatives": int((df["net_profit"] < 0).sum())}


# ---------------------------------------------------------------------------
# the full checklist
# ---------------------------------------------------------------------------

def _check(name, status, value, rule):
    return {"name": name, "status": status, "value": value, "rule": rule}


def validate(strategy, data: pd.DataFrame, settings: Settings | None = None, journal=None,
             grid: dict | None = None, holdout: float = 0.3, mc_runs: int = 5000, quick: bool = False) -> dict:
    settings = settings or Settings.realistic()
    checks = []
    base = run(strategy, data, settings)
    m = base.metrics
    m.update(return_stats(base))
    initial = settings.initial_capital

    # 1. sample size
    n = m["total_trades"]
    checks.append(_check("Enough trades", "pass" if n >= 100 else ("warn" if n >= 30 else "fail"), f"{n} trades",
                         "≥100 closed trades (30-99 is thin evidence)"))
    # 2. profitable after realistic costs
    pf = m.get("profit_factor") or 0
    checks.append(_check("Profitable after costs", "pass" if pf >= 1.2 and m["net_profit"] > 0 else
                         ("warn" if pf >= 1.0 else "fail"), f"PF {pf:.2f}, net ${m['net_profit']:,.0f}",
                         "profit factor ≥1.2 with spread, commission, slippage and swap"))
    # sizing: signals the account could not take
    rej = int(m.get("rejected_orders", 0) or 0)
    checks.append(_check("Account size fits the risk setting", "pass" if rej == 0 else "warn",
                         f"{rej} signals skipped (below 0.01 lot)" if rej else "every signal could be sized",
                         "risk % x equity must cover at least 0.01 lot at the stop distance"))
    bh = m.get("buy_hold_return_pct")
    if bh is not None:
        checks.append(_check("Compared with buy & hold", "info",
                             f"strategy {m['net_profit_pct']:.1f}% vs holding gold {bh:.1f}%",
                             "context: a trading strategy should earn its risk, not only beat zero"))
    # 3. cost stress
    stress = {}
    for mult in (1.5, 2.0):
        st = replace(settings, commission_value=settings.commission_value * mult,
                     slippage_ticks=int(math.ceil(settings.slippage_ticks * mult)),
                     spread_fixed=settings.spread_fixed * mult, swap_long=settings.swap_long * mult,
                     swap_short=settings.swap_short * mult)
        d = data.copy()
        if "spread" in d and settings.spread_mode == "data":
            d["spread"] = d["spread"] * mult
        d.attrs = data.attrs
        stress[mult] = run(strategy, d, st).metrics
    s15 = stress[1.5]
    checks.append(_check("Survives 1.5× costs", "pass" if s15["net_profit"] > 0 and (s15.get("profit_factor") or 0) > 1 else "fail",
                         f"net ${s15['net_profit']:,.0f}", "still profitable when all costs are 50% higher"))
    checks.append(_check("At 2× costs", "pass" if stress[2.0]["net_profit"] > 0 else "info",
                         f"net ${stress[2.0]['net_profit']:,.0f}", "informational"))
    # 4. pessimistic intrabar
    pess = run(strategy, data, replace(settings, intrabar="pessimistic")).metrics
    checks.append(_check("Pessimistic in-bar fills", "pass" if pess["net_profit"] > 0 else "warn",
                         f"net ${pess['net_profit']:,.0f}", "still profitable if the stop is always hit before the target"))
    # 5. holdout
    cut = int(len(data) * (1 - holdout))
    ins, oos = data.iloc[:cut], data.iloc[cut:]
    r_in, r_out = run(strategy, ins, settings), run(strategy, oos, settings)
    yrs_in = max((ins.index[-1] - ins.index[0]).days, 1) / 365
    yrs_out = max((oos.index[-1] - oos.index[0]).days, 1) / 365
    rate_in, rate_out = r_in.metrics["net_profit"] / yrs_in, r_out.metrics["net_profit"] / yrs_out
    ok = r_out.metrics["net_profit"] > 0 and (rate_in <= 0 or rate_out >= 0.5 * rate_in)
    checks.append(_check("Recent out-of-sample period", "pass" if ok else ("warn" if r_out.metrics["net_profit"] > 0 else "fail"),
                         f"${rate_out:,.0f}/yr vs ${rate_in:,.0f}/yr earlier",
                         f"last {int(holdout * 100)}% of data keeps ≥50% of the earlier profit rate"))
    # 6. Monte Carlo
    mc = monte_carlo(base.trades, initial, mc_runs) if n >= 5 else {}
    if mc:
        checks.append(_check("Monte Carlo (trade order luck)", "pass" if mc["final_p5"] > initial else "warn",
                             f"5th pct final ${mc['final_p5']:,.0f}; 95th pct max DD {mc['max_dd_p95']:.1f}%",
                             "5th percentile of 5,000 reshuffles still ends above the start (heuristic)"))
    # 7. plateau
    if not quick:
        pl = plateau(strategy, data, settings, m["net_profit"])
        if len(pl["table"]):
            ratio = pl["median_ratio"]
            st_ = "pass" if ratio >= 0.7 and pl["negatives"] == 0 else ("warn" if ratio >= 0.4 else "fail")
            checks.append(_check("Parameter stability (±20%)", st_,
                                 f"neighbours keep {ratio * 100:.0f}% of profit, {pl['negatives']} lose money" if not math.isnan(ratio) else "base not profitable",
                                 "median neighbour ≥70% of the base result, none negative (heuristic)"))
    # 8. look-ahead
    if not quick:
        la = lookahead_test(strategy, data, settings)
        checks.append(_check("No look-ahead (truncation test)", "pass" if la["ok"] else "fail",
                             "signals stable" if la["ok"] else "; ".join(la["problems"])[:120],
                             "cutting off future bars must not change past trades"))
    # 9. walk-forward
    wf = None
    if grid:
        wf = walk_forward(strategy, data, grid, settings, journal=journal)
        eff, wr = wf["efficiency"], wf["oos_win_rate"]
        st_ = "pass" if (eff >= 0.5 and wr >= 0.6) else ("warn" if eff > 0 else "fail")
        checks.append(_check("Walk-forward", st_, f"efficiency {eff:.2f}, {wr * 100:.0f}% of test windows profitable",
                             "efficiency ≥0.5 and ≥60% profitable windows (Pardo, heuristic)"))
    # 10. deflated sharpe & trial count
    n_trials = 1
    sr_var = 0.0
    if journal is not None:
        from .journal import slugify
        slug = slugify(strategy.name)
        journal.record_run(base, kind="backtest", notes="validate() base run", extra={"stats": return_stats(base)})
        n_trials = max(journal.trial_count(slug), 1)
        runs = journal.runs(slug)
        if "daily_sharpe" in runs:
            vals = runs["daily_sharpe"].dropna().to_numpy(float)
            sr_var = float(np.var(vals, ddof=1)) if len(vals) > 1 else 0.0
        if sr_var == 0.0 and n_trials > 1:
            sr_var = (m["daily_sharpe"] * 0.5) ** 2  # fallback guess when trials were not stored
        rets = journal.trial_returns(slug)
        if rets.shape[1] >= 8:
            p = pbo(rets, n_blocks=min(16, max(4, (len(rets.dropna()) // 4) // 2 * 2)))
            if not math.isnan(p):
                checks.append(_check("Probability of overfitting (PBO)", "pass" if p <= 0.05 else ("warn" if p <= 0.2 else "fail"),
                                     f"{p:.2f} across {rets.shape[1]} variants", "≤0.05 (≤0.2 acceptable while exploring)"))
    dsr = deflated_sharpe(m["daily_sharpe"], m["n_days"], n_trials, sr_var, m["skew"], m["kurt"]) if not math.isnan(m["daily_sharpe"]) else float("nan")
    checks.append(_check("Deflated Sharpe ratio", "pass" if dsr >= 0.95 else ("warn" if dsr >= 0.8 else "fail"),
                         f"{dsr:.2f} (annual Sharpe {m['annual_sharpe']:.2f}, {n_trials} trials)" if not math.isnan(dsr) else "n/a",
                         "≥0.95 probability the edge is real after counting every variant tried"))
    years = m.get("years", 0)
    need = min_backtest_years(n_trials)
    checks.append(_check("Enough history for trials tried", "pass" if years >= need else "warn",
                         f"{years:.1f} years for {n_trials} trials (need {need:.1f})", "minimum backtest length (Bailey et al. 2014)"))

    fails = sum(c["status"] == "fail" for c in checks)
    warns = sum(c["status"] == "warn" for c in checks)
    if fails:
        verdict, headline = "not-ready", f"Not ready: {fails} check(s) failed. Fix those before automating."
    elif warns >= 2:
        verdict, headline = "caution", f"Caution: {warns} warnings. Paper trade only, and watch closely."
    else:
        verdict, headline = "ready", "Ready for paper trading. Run it on a practice account before real money."
    return {"verdict": verdict, "headline": headline, "checks": checks, "metrics": m,
            "stress": {str(k): v for k, v in stress.items()}, "monte_carlo": mc,
            "walk_forward": None if wf is None else {"efficiency": wf["efficiency"], "oos_win_rate": wf["oos_win_rate"],
                                                    "folds": wf["folds"].to_dict("records")},
            "deflated_sharpe": dsr, "trials": n_trials, "result": base}


def format_checks(v: dict) -> str:
    icon = {"pass": "PASS", "warn": "WARN", "fail": "FAIL", "info": "info"}
    lines = [v["headline"], ""]
    for c in v["checks"]:
        lines.append(f"  [{icon[c['status']]:>4}] {c['name']:<34} {c['value']}")
    return "\n".join(lines)
