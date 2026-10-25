"""High-level helpers used by the CLI and notebooks."""
from __future__ import annotations

import importlib.util
from dataclasses import fields
from pathlib import Path

import pandas as pd

from . import data as D
from .engine import Settings, run
from .rules import RuleStrategy, load_card
from .strategy import Strategy

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = {"1h": "XAUUSD_1h.csv.gz", "15m": "XAUUSD_15m.csv.gz", "5m": "XAUUSD_5m.csv.gz"}
FROM_SAMPLE = {"1h": "1h", "2h": "1h", "4h": "1h", "1d": "1h", "1w": "1h", "15m": "15m", "30m": "15m",
               "5m": "5m"}


def load_strategy(spec, **params) -> Strategy:
    """A .yaml card, 'file.py:ClassName', 'file.py' (first Strategy subclass), or a Strategy instance."""
    if isinstance(spec, Strategy):
        return spec
    spec = str(spec)
    path, _, cls = spec.partition(":")
    p = Path(path)
    if not p.exists():
        for base in (ROOT / "strategies", ROOT / "strategies" / "examples"):
            for cand in (base / path, base / f"{path}.yaml", base / f"{path}.py"):
                if cand.exists():
                    p = cand
                    break
            if p.exists():
                break
    if not p.exists():
        raise FileNotFoundError(f"No strategy file {spec!r} (looked in strategies/ and strategies/examples/)")
    if p.suffix in (".yaml", ".yml"):
        return load_card(p, **params)
    mod_spec = importlib.util.spec_from_file_location(p.stem, p)
    mod = importlib.util.module_from_spec(mod_spec)
    mod_spec.loader.exec_module(mod)
    if cls:
        return getattr(mod, cls)(**params)
    for v in vars(mod).values():
        if isinstance(v, type) and issubclass(v, Strategy) and v not in (Strategy, RuleStrategy):
            return v(**params)
    raise ValueError(f"No Strategy subclass found in {p}")


def make_settings(strategy: Strategy, preset: str = "realistic", **overrides) -> Settings:
    names = {f.name for f in fields(Settings)}
    card = dict(getattr(strategy, "card", {}).get("settings") or {}) if isinstance(strategy, RuleStrategy) else {}
    card = {k: v for k, v in card.items() if k in names}
    over = {k: v for k, v in overrides.items() if v is not None and k in names}
    if preset == "tradingview":
        # keep the card's sizing but drop costs, like a default TradingView strategy()
        return Settings.tradingview(**{**{k: v for k, v in card.items() if k.startswith("qty")}, **over})
    if preset == "realistic":
        return Settings.realistic(**{**card, **over})
    return Settings(**{**card, **over})


def get_data(timeframe: str, source: str = "auto", start: str | None = None, end: str | None = None,
             path: str | None = None) -> pd.DataFrame:
    if source == "auto":
        base = FROM_SAMPLE.get(timeframe)
        f = D.SAMPLE_DIR / SAMPLES[base] if base else None
        if f is not None and f.exists():
            df = D.load("csv", timeframe=timeframe, start=start, end=end, path=str(f))
            df.attrs.update(symbol="XAUUSD", timeframe=timeframe, source=f"dukascopy (sample {SAMPLES[base]})")
            return df
        source = "dukascopy"
    df = D.load(source, "XAUUSD", timeframe, start=start, end=end, path=path)
    df.attrs.setdefault("timeframe", timeframe)
    return df


def backtest(strategy, timeframe: str | None = None, source: str = "auto", start=None, end=None,
             preset: str = "realistic", journal=None, notes: str = "", magnifier: bool = False, **settings):
    s = load_strategy(strategy)
    tf = timeframe or s.timeframe or "1h"
    data = get_data(tf, source, start, end)
    st = make_settings(s, preset, **settings)
    ltf = None
    if magnifier and tf not in ("1m", "5m"):
        ltf_tf = "5m" if tf in ("15m", "30m", "1h") else "15m"
        try:
            ltf = get_data(ltf_tf, "auto", start, end)
        except Exception:
            ltf = None
    res = run(s, data, st, magnifier=ltf)
    from .validate import return_stats
    res.metrics.update(return_stats(res))
    run_id = None
    if journal is not None:
        run_id = journal.record_run(res, kind="backtest", notes=notes, extra={"preset": preset})
    res.run_id = run_id
    return res
