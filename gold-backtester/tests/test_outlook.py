"""The gold outlook: free data parsing, the stand-in analyst, the refresh policy, scoring. No network."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from goldlab import analyst as A
from goldlab import fundamentals as F

FIX = Path(__file__).parent / "fixtures"
SNAP = json.loads((FIX / "snapshot.json").read_text())


@pytest.fixture
def offline(monkeypatch, tmp_path):
    monkeypatch.setattr(F, "snapshot", lambda: SNAP)
    monkeypatch.setattr(F, "yahoo_bars", lambda *a, **k: (_ for _ in ()).throw(OSError("offline")))
    monkeypatch.setenv("GSL_OUTLOOK_DIR", str(tmp_path))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    monkeypatch.delenv("CRON_SECRET", raising=False)
    monkeypatch.delenv("GSL_PIN", raising=False)
    return tmp_path


def test_fred_csv_parsing():
    pts = F.parse_fred_csv("observation_date,DFII10\n2026-10-20,2.70\n2026-10-21,.\n2026-10-22,2.64\n")
    assert pts == [("2026-10-20", 2.70), ("2026-10-22", 2.64)]
    assert F._change([("2026-09-01", 2.0), ("2026-09-20", 2.5), ("2026-10-01", 2.9)], 7) == pytest.approx(0.4)
    assert F._change([("2026-10-01", 2.9)], 7) is None


def test_rss_parsing_cleans_titles_and_sources():
    xml = """<rss><channel><item><title>Gold eases ahead of Fed decision - Reuters</title><link>https://x/1</link>
    <pubDate>Wed, 28 Oct 2026 06:16:00 GMT</pubDate><source url="https://reuters.com">Reuters</source></item>
    <item><title>Gold slips - CNBC</title><link>https://x/2</link><pubDate>bad date</pubDate></item></channel></rss>"""
    items = F.parse_rss(xml)
    assert items[0]["title"] == "Gold eases ahead of Fed decision" and items[0]["source"] == "Reuters"
    assert items[0]["time"].startswith("2026-10-28T06:16") and items[1]["time"] is None and items[1]["source"] == "CNBC"


def test_technicals_from_daily_bars():
    idx = pd.date_range("2025-01-01", periods=300, freq="D", tz="UTC")
    close = pd.Series(3000 + pd.Series(range(300)).to_numpy() * 2.0, index=idx)
    df = pd.DataFrame({"open": close - 1, "high": close + 5, "low": close - 5, "close": close, "volume": 1.0}, index=idx)
    t = F.technicals(df, 3700.0)
    assert t["regime"].startswith("uptrend") and t["last_close"] == 3598 and t["spot"] == 3700.0
    assert t["chg_1w_pct"] == pytest.approx(10 / 3588 * 100, abs=0.01) and t["high_20d"] == 3603 and t["ath"] == 3603
    assert 0 < t["rsi14"] <= 100 and len(t["closes_30d"]) == 30


def test_describe_is_compact_and_numeric():
    text = F.describe(SNAP)
    assert "Spot gold" in text and "Macro" in text and "Headlines" in text and len(text) < 12_000


def test_stand_in_outlook_is_schema_shaped():
    out = A.rules_outlook(SNAP)
    for k in A.SCHEMA["required"]:
        assert k in out, k
    assert out["direction"] in ("bullish", "bearish", "neutral") and 0 <= out["confidence"] <= 100
    assert all(d["effect"] in ("supports", "against", "neutral") for d in out["drivers"])
    assert len(out["levels"]["support"]) == 2 and out["levels"]["support"][0] < (SNAP["spot"]["price"])


def test_first_get_makes_an_outlook_and_hourly_refresh_rule(offline):
    code, body = A.http("GET", {}, {})
    assert code == 200 and body["outlook"]["source"] == "rules" and body["outlook"]["reason"] == "first"
    assert body["can_refresh"] is False and body["calls"] == 1 and body["has_key"] is False
    first_id = body["outlook"]["id"]
    code, body = A.http("GET", {}, {})
    assert code == 200 and body["outlook"]["id"] == first_id, "a second GET serves the stored view"
    code, body = A.http("POST", {"refresh": "1"}, {})
    assert code == 429 and "60 minutes" in body["error"] and body["outlook"]["id"] == first_id
    # an old view may be refreshed by anyone
    st = A.FileStore(offline)
    old = st.get("latest"); old["time"] = "2026-01-01T00:00:00Z"; st.put("latest", old)
    code, body = A.http("GET", {}, {})
    assert body["can_refresh"] is True
    code, body = A.http("POST", {"refresh": "1"}, {})
    assert code == 200 and body["outlook"]["id"] != first_id and body["outlook"]["reason"] == "manual" and body["calls"] == 2


def test_cron_secret_forces_a_refresh_and_wrong_secret_does_not(offline, monkeypatch):
    A.http("GET", {}, {})
    monkeypatch.setenv("CRON_SECRET", "s3cret")
    code, body = A.http("GET", {}, {"authorization": "Bearer nope"})
    assert code == 200 and body["calls"] == 1
    code, body = A.http("GET", {}, {"authorization": "Bearer s3cret"})
    assert code == 200 and body["calls"] == 2 and body["outlook"]["reason"] == "cron"


def test_lock_stops_overlapping_refreshes(offline):
    st = A.FileStore(offline)
    st.put("lock", {"started": A._iso(A._now())})
    code, body = A.http("GET", {}, {})
    assert code == 200 and body["outlook"] is None and body["busy"] is True


def test_failed_refresh_keeps_the_previous_view(offline, monkeypatch):
    A.http("GET", {}, {})
    st = A.FileStore(offline)
    old = st.get("latest"); old["time"] = "2026-01-01T00:00:00Z"; st.put("latest", old)
    monkeypatch.setattr(A, "rules_outlook", lambda snap: (_ for _ in ()).throw(RuntimeError("boom")))
    code, body = A.http("POST", {"refresh": "1"}, {})
    assert code == 502 and "boom" in body["error"] and body["outlook"]["id"] == old["id"]
    assert not (A._now() - A._parse(st.get("lock")["started"])).total_seconds() < A.LOCK_SECONDS, "lock released"


def test_scoring_calls_against_later_prices():
    now = datetime(2026, 10, 28, tzinfo=timezone.utc)
    hist = [{"time": "2026-10-10T00:00:00Z", "direction": "bullish", "confidence": 60, "horizon_days": 5, "price_at": 4000},
            {"time": "2026-10-12T00:00:00Z", "direction": "bearish", "confidence": 60, "horizon_days": 5, "price_at": 4100},
            {"time": "2026-10-27T00:00:00Z", "direction": "bullish", "confidence": 60, "horizon_days": 5, "price_at": 4050},
            {"time": "2026-10-13T00:00:00Z", "direction": "neutral", "confidence": 50, "horizon_days": 5, "price_at": 4050}]
    closes = [(f"2026-10-{d:02d}", 4000 + d * 5) for d in range(1, 28)]
    s = A.score(hist, closes, 4054.0, now)
    assert s["scored"] == 2 and s["hits"] == 2 and s["hit_rate"] == 100.0 and s["pending"] == 1
    assert s["recent"][0]["price_after"] == 4085 and s["recent"][1]["hit"] is True
    assert A.score([], closes, None, now)["hit_rate"] is None


def test_telegram_is_optional(offline):
    assert A.notify("hi") is False
