"""Free data behind the gold outlook: macro drivers, prices, news, technicals and strategy signals.

Sources (no keys, all free):
  * FRED  fredgraph.csv   real yields, nominal yields, breakevens, the broad dollar, VIX, oil, Fed funds
  * gold-api.com         spot gold right now
  * Yahoo Finance        COMEX gold futures (GC=F) daily and hourly bars for the technical snapshot
  * Google News RSS      headlines from the last two days

Every source fails soft: a source that is down becomes a note in the snapshot, never an exception,
so the analyst can still reason with what it has. Results are cached in memory for a few minutes.
"""
from __future__ import annotations

import html
import json
import math
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import numpy as np
import pandas as pd

from . import indicators as ta

TIMEOUT = 15
UA = {"User-Agent": "Mozilla/5.0 (compatible; GoldStrategyLab/1.0; +https://gold-strategy-lab-eight.vercel.app)"}

# id -> (name, unit, how a RISE in the series usually acts on gold, note)
SERIES = {
    "DFII10": ("10-year real yield (TIPS)", "%", "against", "Gold pays no yield; higher real yields raise its opportunity cost."),
    "DGS10": ("10-year Treasury yield", "%", "against", "Nominal yields matter through real yields and the dollar."),
    "T10YIE": ("10-year inflation breakeven", "%", "supports", "Gold is an inflation hedge; rising expectations help."),
    "DTWEXBGS": ("Broad US dollar index", "index", "against", "Gold is priced in dollars; a stronger dollar is a headwind."),
    "VIXCLS": ("VIX (equity volatility)", "index", "supports", "Fear bids safe havens, though forced selling can hit gold too."),
    "DCOILWTICO": ("WTI crude oil", "$/bbl", "mixed", "Oil feeds inflation (supportive) but also yields (negative)."),
    "DFEDTARU": ("Fed funds target, upper bound", "%", "against", "Higher policy rates lift real yields and the dollar."),
}
NEWS_QUERIES = ["gold price", "Federal Reserve rates", "central bank gold buying", "geopolitical risk markets"]
_CACHE: dict = {}
CACHE_SECONDS = 300


def _get(url: str, timeout: int = TIMEOUT) -> str:
    import requests
    r = requests.get(url, timeout=timeout, headers=UA)
    r.raise_for_status()
    return r.text


def _cached(key: str, fn, ttl: int = CACHE_SECONDS):
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    val = fn()
    _CACHE[key] = (time.time(), val)
    return val


def _num(v, nd=4):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return None if not math.isfinite(v) else round(v, nd)


# --------------------------------------------------------------------------- FRED
def parse_fred_csv(text: str) -> list[tuple[str, float]]:
    """fredgraph.csv: 'observation_date,ID' header, '.' for missing values."""
    out = []
    for line in text.strip().splitlines()[1:]:
        d, _, v = line.partition(",")
        v = v.strip()
        if v and v != ".":
            try:
                out.append((d.strip(), float(v)))
            except ValueError:
                pass
    return out


def fred_series(series_id: str) -> list[tuple[str, float]]:
    return _cached("fred:" + series_id, lambda: parse_fred_csv(_get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}")), 3600)


def _change(points: list[tuple[str, float]], days: int):
    """Change from the last observation at least `days` days before the latest."""
    if len(points) < 2:
        return None
    last_d = datetime.strptime(points[-1][0], "%Y-%m-%d")
    for d, v in reversed(points[:-1]):
        if (last_d - datetime.strptime(d, "%Y-%m-%d")).days >= days:
            return _num(points[-1][1] - v)
    return None


def macro(notes: list[str]) -> list[dict]:
    out = []
    for sid, (name, unit, effect, why) in SERIES.items():
        try:
            pts = fred_series(sid)
        except Exception as e:  # noqa: BLE001 - any failure is a note
            notes.append(f"{name}: unavailable ({type(e).__name__})")
            continue
        if not pts:
            notes.append(f"{name}: no data")
            continue
        recent = pts[-90:]
        out.append({"id": sid, "name": name, "unit": unit, "rise_is": effect, "why": why,
                    "latest": _num(pts[-1][1]), "date": pts[-1][0],
                    "chg_1w": _change(pts, 7), "chg_1m": _change(pts, 30), "chg_3m": _change(pts, 90),
                    "history": [[d, _num(v)] for d, v in recent]})
    return out


# --------------------------------------------------------------------------- prices
def spot(notes: list[str]) -> dict | None:
    try:
        js = json.loads(_cached("spot", lambda: _get("https://api.gold-api.com/price/XAU"), 60))
        return {"price": _num(js.get("price"), 2), "time": js.get("updatedAt"), "source": "gold-api.com (spot)"}
    except Exception as e:  # noqa: BLE001
        notes.append(f"Spot price: unavailable ({type(e).__name__})")
        return None


def yahoo_bars(symbol: str = "GC=F", rng: str = "2y", interval: str = "1d") -> pd.DataFrame:
    """OHLCV bars from Yahoo Finance's chart endpoint, as a UTC-indexed frame the engine can use."""
    def fetch():
        js = json.loads(_get(f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol)}?range={rng}&interval={interval}", 20))
        res = js["chart"]["result"][0]
        q = res["indicators"]["quote"][0]
        idx = pd.to_datetime(res["timestamp"], unit="s", utc=True)
        df = pd.DataFrame({"open": q["open"], "high": q["high"], "low": q["low"], "close": q["close"],
                           "volume": [v or 0 for v in q["volume"]]}, index=idx).dropna(subset=["open", "high", "low", "close"])
        df.index.name = "time"
        df["spread"] = 0.0
        df.attrs.update(symbol=symbol, timeframe=interval, source="Yahoo Finance " + symbol)
        return df
    return _cached(f"yahoo:{symbol}:{rng}:{interval}", fetch, 600)


# --------------------------------------------------------------------------- news
def _clean_title(t: str) -> tuple[str, str]:
    t = html.unescape(t or "").strip()
    m = re.match(r"^(.*)\s+-\s+([^-]{2,40})$", t)
    return (m.group(1).strip(), m.group(2).strip()) if m else (t, "")


def parse_rss(text: str) -> list[dict]:
    root = ET.fromstring(text)
    out = []
    for it in root.iter("item"):
        title, src = _clean_title(it.findtext("title"))
        src = (it.findtext("source") or src or "").split(" - ")[0].strip()[:40]
        try:
            when = parsedate_to_datetime(it.findtext("pubDate") or "").astimezone(timezone.utc)
        except (TypeError, ValueError):
            when = None
        out.append({"title": title, "source": src, "link": it.findtext("link") or "",
                    "time": when.isoformat(timespec="minutes") if when else None, "ts": when.timestamp() if when else 0})
    return out


def news(notes: list[str], limit: int = 30) -> list[dict]:
    seen, out = set(), []
    for q in NEWS_QUERIES:
        url = f"https://news.google.com/rss/search?q={quote(q + ' when:2d')}&hl=en-US&gl=US&ceid=US:en"
        try:
            items = _cached("news:" + q, lambda u=url: parse_rss(_get(u, 20)), 900)
        except Exception as e:  # noqa: BLE001
            notes.append(f"News '{q}': unavailable ({type(e).__name__})")
            continue
        for it in items[:15]:
            key = re.sub(r"\W+", " ", it["title"].lower())[:60]
            if key in seen or not it["title"]:
                continue
            seen.add(key)
            out.append({**it, "topic": q})
    out.sort(key=lambda x: -x["ts"])
    return [{k: v for k, v in it.items() if k != "ts"} for it in out[:limit]]


# --------------------------------------------------------------------------- technicals
def technicals(daily: pd.DataFrame, spot_price: float | None = None) -> dict:
    c = daily["close"]
    n = len(c)
    last = float(c.iloc[-1])
    ema20, ema50, ema200 = (ta.ema(c, k) for k in (20, 50, 200))
    rsi = ta.rsi(c, 14)
    atr = ta.atr(daily["high"], daily["low"], c, 14)
    hi20, lo20 = ta.highest(daily["high"], 20), ta.lowest(daily["low"], 20)
    hi252, lo252 = ta.highest(daily["high"], min(252, n)), ta.lowest(daily["low"], min(252, n))
    ath = float(daily["high"].max())

    def pct(a, b):
        return _num((a / b - 1) * 100, 2) if a is not None and b else None

    def back(k):
        return float(c.iloc[-1 - k]) if n > k else None

    e20, e50, e200 = (float(x.iloc[-1]) if not np.isnan(x.iloc[-1]) else None for x in (ema20, ema50, ema200))
    regime = ("uptrend (EMA 20 > 50 > 200)" if e20 and e50 and e200 and e20 > e50 > e200 else
              "downtrend (EMA 20 < 50 < 200)" if e20 and e50 and e200 and e20 < e50 < e200 else "mixed / range")
    return {
        "last_close": _num(last, 2), "as_of": str(daily.index[-1].date()), "spot": spot_price,
        "chg_1d_pct": pct(last, back(1)), "chg_1w_pct": pct(last, back(5)), "chg_1m_pct": pct(last, back(21)),
        "chg_3m_pct": pct(last, back(63)), "chg_6m_pct": pct(last, back(126)), "chg_1y_pct": pct(last, back(min(251, n - 1))),
        "ema20": _num(e20, 2), "ema50": _num(e50, 2), "ema200": _num(e200, 2),
        "vs_ema20_pct": pct(last, e20), "vs_ema50_pct": pct(last, e50), "vs_ema200_pct": pct(last, e200),
        "regime": regime, "rsi14": _num(rsi.iloc[-1], 1),
        "atr14": _num(atr.iloc[-1], 2), "atr14_pct": pct(last + float(atr.iloc[-1]), last) if not np.isnan(atr.iloc[-1]) else None,
        "high_20d": _num(hi20.iloc[-1], 2), "low_20d": _num(lo20.iloc[-1], 2),
        "high_52w": _num(hi252.iloc[-1], 2), "low_52w": _num(lo252.iloc[-1], 2),
        "from_ath_pct": pct(last, ath), "ath": _num(ath, 2),
        "closes_30d": [[str(t.date()), _num(v, 2)] for t, v in c.iloc[-30:].items()],
    }


# --------------------------------------------------------------------------- strategies
def strategy_signals(notes: list[str]) -> list[dict]:
    """What each example strategy is doing right now, on recent market bars."""
    from .engine import Settings, run
    from .rules import RuleStrategy
    from .webapi import _card_files
    import yaml
    out = []
    bars: dict[str, pd.DataFrame] = {}

    def data_for(tf: str) -> pd.DataFrame:
        if tf in bars:
            return bars[tf]
        from .data.resample import resample
        if tf == "1d":
            df = yahoo_bars("GC=F", "2y", "1d")
        elif tf in ("1h", "4h"):
            df = yahoo_bars("GC=F", "60d", "1h")
            if tf == "4h":
                df = resample(df, "4h")
        else:
            df = yahoo_bars("GC=F", "30d", "15m")
            if tf == "5m":
                df = yahoo_bars("GC=F", "10d", "5m")
        bars[tf] = df
        return df

    for p in _card_files():
        try:
            card = yaml.safe_load(p.read_text())
            tf = card.get("timeframe", "1h")
            df = data_for(tf)
            s = RuleStrategy(card)
            st = Settings.realistic(**{k: v for k, v in (card.get("settings") or {}).items()
                                       if k in ("qty_type", "qty_value", "initial_capital")})
            st.spread_mode = "none"
            res = run(s, df, st)
            last = df["close"].iloc[-1]
            if res.open_trades:
                t = res.open_trades[0]
                side = "long" if t["side"] in ("long", 1) else "short"
                out.append({"id": p.stem, "name": s.name, "timeframe": tf, "position": side,
                            "entry_price": _num(t["entry_price"], 2), "entry_time": str(pd.Timestamp(t["entry_time"]).date()),
                            "open_move_pct": pct_move(side, float(t["entry_price"]), float(last))})
            else:
                lt = res.trades.iloc[-1] if len(res.trades) else None
                out.append({"id": p.stem, "name": s.name, "timeframe": tf, "position": "flat",
                            "last_trade": (f"{lt.side} closed {pd.Timestamp(lt.exit_time).date()} ({'+' if lt.pnl >= 0 else ''}{lt.pnl:.0f})" if lt is not None else "none recently")})
        except Exception as e:  # noqa: BLE001
            notes.append(f"Strategy {p.stem}: could not evaluate ({type(e).__name__}: {str(e)[:80]})")
    return out


def pct_move(side: str, entry: float, last: float):
    return _num((last / entry - 1) * 100 * (1 if side == "long" else -1), 2)


# --------------------------------------------------------------------------- the snapshot
def snapshot() -> dict:
    """Everything the analyst reads, gathered with a short in-memory cache."""
    def build():
        notes: list[str] = []
        sp = spot(notes)
        tech = None
        try:
            daily = yahoo_bars("GC=F", "2y", "1d")
            tech = technicals(daily, sp["price"] if sp else None)
        except Exception as e:  # noqa: BLE001
            notes.append(f"Price history: unavailable ({type(e).__name__})")
        return {"as_of": datetime.now(timezone.utc).isoformat(timespec="minutes"), "spot": sp, "technicals": tech,
                "macro": macro(notes), "news": news(notes), "strategies": strategy_signals(notes), "notes": notes}
    return _cached("snapshot", build, CACHE_SECONDS)


def describe(snap: dict) -> str:
    """The snapshot as compact text for the model (numbers first, no fluff)."""
    L = []
    sp, t = snap.get("spot"), snap.get("technicals")
    L.append(f"As of {snap['as_of']} UTC.")
    if sp:
        L.append(f"Spot gold: ${sp['price']:,} ({sp['time']}, {sp['source']}).")
    if t:
        L.append(f"COMEX gold futures daily (to {t['as_of']}): close {t['last_close']}, 1d {t['chg_1d_pct']}%, 1w {t['chg_1w_pct']}%, "
                 f"1m {t['chg_1m_pct']}%, 3m {t['chg_3m_pct']}%, 6m {t['chg_6m_pct']}%, 1y {t['chg_1y_pct']}%. "
                 f"Regime: {t['regime']}. EMA20 {t['ema20']} ({t['vs_ema20_pct']}%), EMA50 {t['ema50']} ({t['vs_ema50_pct']}%), "
                 f"EMA200 {t['ema200']} ({t['vs_ema200_pct']}%). RSI14 {t['rsi14']}. ATR14 {t['atr14']} ({t['atr14_pct']}%/day). "
                 f"20-day range {t['low_20d']}–{t['high_20d']}; 52-week {t['low_52w']}–{t['high_52w']}; {t['from_ath_pct']}% from the all-time high {t['ath']}.")
        L.append("Last 30 closes: " + ", ".join(f"{d[5:]} {v}" for d, v in t["closes_30d"]))
    if snap.get("macro"):
        L.append("Macro (latest, change over 1w / 1m / 3m; 'rise is' = what a rise usually does to gold):")
        for m in snap["macro"]:
            L.append(f"  - {m['name']}: {m['latest']} {m['unit']} on {m['date']}; 1w {m['chg_1w']}, 1m {m['chg_1m']}, 3m {m['chg_3m']}; rise is {m['rise_is']} gold. {m['why']}")
    if snap.get("strategies"):
        L.append("Systematic strategies on this site right now:")
        for s in snap["strategies"]:
            L.append(f"  - {s['name']} ({s['timeframe']}): {s['position']}" + (f" since {s['entry_time']} @ {s['entry_price']} ({s['open_move_pct']:+}% so far)" if s['position'] != 'flat' else f"; last trade: {s.get('last_trade')}"))
    if snap.get("news"):
        L.append("Headlines (newest first):")
        for n in snap["news"][:25]:
            L.append(f"  - [{(n['time'] or '')[:16]}] {n['title']} ({n['source']})")
    if snap.get("notes"):
        L.append("Data gaps: " + "; ".join(snap["notes"]))
    return "\n".join(L)
