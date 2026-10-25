# Gold (XAUUSD spot and COMEX GC futures): historical data sources, trading costs and market structure for backtesting

Research date: 2026-10-25. Scope: free or cheap data for a Python multi-timeframe gold backtester (1-minute to daily), plus the cost and market-structure facts a backtest has to model. The trader is a retail trader, probably based in Singapore.

Method note: besides web research, the researcher ran **live checks on 2026-10-25** against the Dukascopy datafeed and the Yahoo chart API (the endpoint yfinance uses). Downloaded files were decoded and the numbers computed locally. Measurements carry the label "**[measured 2026-10-25]**" and cite the endpoint URL used. All other figures come from the cited web pages. Many broker and blog figures are marketing "from" numbers, so treat them as best-case values.

---

## 1. Free and cheap data sources for XAUUSD and GC: timeframes, history depth, bid/ask, time zone, terms, limits, cost

### Takeaway
**Dukascopy** is the strongest free source for multi-year intraday spot gold. It needs no account and has true bid **and** ask ticks from 2003-05-05, with UTC timestamps. It throttles hard (HTTP 429). **HistData** has free M1 bid-only bars from 2009, timestamped in fixed EST without DST. **Yahoo/yfinance GC=F** is fine for daily data and recent intraday only: 1m data is limited to the last 30 days in 8-day chunks, 2m–90m to 60 days, and 1h to 730 days. **OANDA v20** gives bid/ask/mid candles in pages of 5,000 and needs an account token. Paid options at about $49/month include Massive (formerly Polygon) FX flat files back to 2009.

### Cited Findings

**Dukascopy (Swiss bank/ECN): free, no account**
- URL pattern verified live: `https://datafeed.dukascopy.com/datafeed/XAUUSD/{YYYY}/{MM}/{DD}/{HH}h_ticks.bi5`. **The month is zero-indexed** (00 = January) and the hour is UTC. `XAUUSD/2025/00/06/14h_ticks.bi5` (6 Jan 2025) decoded to ask 2624.665 / bid 2624.048. `XAUUSD/2008/05/02/13h_ticks.bi5` (2 June 2008) decoded to about 893.1/892.7, which matches gold's June 2008 level. `XAUUSD/2026/08/15/14h_ticks.bi5` (15 Sep 2026) decoded to about 4295.0/4294.6. **[measured 2026-10-25]** — [Dukascopy datafeed](https://datafeed.dukascopy.com/datafeed/XAUUSD/2025/00/06/14h_ticks.bi5)
- Tick file format: LZMA-compressed binary with 20-byte big-endian rows (`>IIIff`): ms offset from the start of the hour, ask (int), bid (int), ask volume (float), bid volume (float) — [ninety47/dukascopy (GitHub)](https://github.com/ninety47/dukascopy). Verified by decoding. **For XAUUSD the price integers divide by 1000** (3 decimals). **[measured 2026-10-25]**
- Daily candle files also exist: `.../XAUUSD/{YYYY}/{MM}/{DD}/BID_candles_min_1.bi5` (and `ASK_candles_min_1.bi5`). Each holds 1,440 rows of 24 bytes (`>IIIIIf`): seconds offset from 00:00 UTC, **open, close, low, high** (note the order: close comes before low and high), and volume. Verified: the first row of 6 Jan 2025 was O 2640.835, C 2640.755, L 2640.585, H 2641.155. **[measured 2026-10-25]** — [Dukascopy datafeed](https://datafeed.dukascopy.com/datafeed/XAUUSD/2025/00/06/BID_candles_min_1.bi5)
- Earliest available XAUUSD data (UTC): ticks and seconds from 2003-05-05 00:01:03; m1–m30 from 2003-05-05 00:01; h1/h4 from 2003-05-05 00:00; d1/mn1 from 1999-06-03 — [dukascopy-node instrument page](https://www.dukascopy-node.app/instrument/xauusd)
- Throttling: repeated requests returned **HTTP 429** with a 113-byte error body, and some connections were reset. A downloader must retry with backoff and should validate that each file decompresses (a 113-byte file is an error, not data). An hour with no trading returns HTTP 200 with **0 bytes**. **[measured 2026-10-25]** — [Dukascopy datafeed](https://datafeed.dukascopy.com/datafeed/XAUUSD/2026/08/15/21h_ticks.bi5)
- Dukascopy's own XAUUSD spread (ask − bid), measured from tick files **[measured 2026-10-25]** — [Dukascopy datafeed](https://datafeed.dukascopy.com/datafeed/XAUUSD/2026/08/15/13h_ticks.bi5):
  - 6 Jan 2025, 14:00–15:00 UTC: median **$0.567**, range $0.001–$1.361, 28,985 ticks in the hour.
  - 15 Sep 2026: 01h UTC (Asia) median $0.577 (p90 $0.693); 08h UTC (London open) median $0.560; 13h UTC (London/NY overlap) median **$0.507** (p90 $0.590, max $1.00); 20h UTC (last hour before the 17:00 ET break) median $0.71 (p99 $1.16, **max $5.80**); 21h UTC empty (daily break); 22h UTC (reopen hour) median $0.82 (p90 $1.23, p99 $2.78, **max $5.97**).
  - June 2008 (gold about $893): median $0.46.
- Tick volume fields are small floats (for example 0.00012). Their units are not documented in the sources found. **[measured 2026-10-25]**
- Third-party tooling that wraps this feed includes tickterial (Python) and Bi5.NET (converts to CSV) — [tickterial (PyPI)](https://pypi.org/project/tickterial), [Bi5.NET (NuGet)](https://www.nuget.org/packages/Bi5.NET/0.2.0); also [TickVault](https://github.com/keyhankamyar/TickVault) and [theorycraft-trading/dukascopy](https://github.com/theorycraft-trading/dukascopy).

**HistData.com: free, manual download**
- XAUUSD M1 (Generic ASCII) is available as full-year zip files for **2009–2025** and monthly zips for **Jan–Oct 2026**; the file list was updated 2026-10-18. Paid conveniences: automatic updates via Google Drive at $7/month, and FTP/SFTP via PayPal — [HistData XAUUSD M1](https://www.histdata.com/download-free-forex-data/?/ascii/1-minute-bar-quotes/xauusd)
- M1 format: `YYYYMMDD HHMMSS;Open;High;Low;Close;Volume` with semicolons. **All OHLC values are bid quotes.** The time zone is **Eastern Standard Time WITHOUT daylight-saving adjustments** (fixed UTC−5). The volume column shows 0 in the examples. Tick format: `YYYYMMDD HHMMSSNNN,Bid,Ask,Volume` — [HistData file specification](https://www.histdata.com/f-a-q/data-files-detailed-specification/)
- The download page has no explicit terms-of-use statement — [HistData XAUUSD M1](https://www.histdata.com/download-free-forex-data/?/ascii/1-minute-bar-quotes/xauusd)

**Yahoo Finance / yfinance (GC=F = COMEX front-month gold futures): free, no account**
- Live Yahoo API errors on 2026-10-25 **[measured]** — [Yahoo chart API](https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1m&range=30d):
  - 1m: "Only **8 days** worth of 1m granularity data are allowed to be fetched per request" and "The requested range must be within the **last 30 days**".
  - 5m: "must be within the **last 60 days**".
  - 1h: "must be within the **last 730 days**".
- yfinance source code agrees: `period="max"` maps 1m → 8 days, 2m/5m/15m/30m/90m → 60 days, 1h/60m → 730 days. The repair logic uses lookbacks of 1m = 30 days, 2m–30m = 60 days, 1h = 730 days. Valid intervals are 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo, and 30m is fetched as 15m and resampled — [yfinance history.py](https://github.com/ranaroussi/yfinance/blob/main/yfinance/scrapers/history.py)
- **Correction to the brief:** the old rule of thumb "1m ≈ 7 days" is outdated. Yahoo now allows 8 days per request within a 30-day lookback; a GitHub issue also mentions the 30-day 1m window — [yfinance issue #2451](https://github.com/ranaroussi/yfinance/issues/2451). One forum post still quotes "only 7 days" — [Streamlit forum](https://discuss.streamlit.io/t/how-to-show-an-error-message-when-the-interval-of-historical-data-is-too-small-or-big/13726)
- Daily GC=F data from 2023-01-03 to 2026-10-23 (959 bars) and 1h data from 2024-10-27 to 2026-10-23 (11,416 bars) downloaded without an API key using a browser User-Agent. **[measured 2026-10-25]** — [Yahoo chart API](https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1d)

**OANDA v20 REST API: free with an account (practice account works)**
- Endpoint `GET /v3/instruments/{instrument}/candles`. The `price` parameter takes any combination of "M" (mid), "B" (bid) and "A" (ask), for example `BA` or `MBA`. The default `dailyAlignment` is **17** (range 0–23) and the default `alignmentTimezone` is **America/New_York**. Returned times are always **UTC** — [OANDA Instrument Endpoints](https://developer.oanda.com/rest-live-v20/instrument-ep); [async-v20 docs](https://async-v20.readthedocs.io/en/latest/api.html); [tessl OANDA v20 binding](https://tessl.io/registry/tessl/maven-oanda--v20/files/docs/instruments.md)
- `count` is 1 to **5,000** with a default of 500. Deeper history needs pagination with `from` + `count`, or `from`/`to` — [oandapyV20 InstrumentsCandlesFactory docs](https://oanda-api-v20.readthedocs.io/en/stable/contrib/factories/instrumentscandlesfactory.html); [oanda-go](https://pkg.go.dev/github.com/florinel-chis/oanda-go)

**Massive (formerly Polygon.io): paid**
- Polygon.io rebranded as Massive in early 2026. Forex minute-aggregate flat files (OHLCV per minute, 1,750+ currency pairs) go back to **2009-09-25**. The free "Currencies Basic" tier does **not** include flat files. **Currencies Starter at $49/month** includes all history — [Massive forex minute aggregates docs](https://massive.com/docs/flat-files/forex/minute-aggregates.md)
- Older free-tier description, outdated: 5 calls/minute, EOD data, up to 2 years of history — [QuantStart (pre-rebrand)](https://www.quantstart.com/articles/creating-a-returns-series-with-polygons-forex-data/)

**Twelve Data: freemium**
- Basic (free) tier: **8 API credits/minute and 800/day**. Credits used = data weight × number of symbols — [Twelve Data support: API credits limits](https://support.twelvedata.com/en/articles/5194820-api-credits-limits); [Twelve Data pricing](https://twelvedata.com/pricing)

**TraderMade: freemium**
- The free plan's minute time series is limited to **2 days of history including today**. The download page lists XAUUSD — [TraderMade download](https://marketdata.tradermade.com/download-forex-data)

**Static datasets**
- A dataset listing describes cleaned minute-level XAU/USD data covering 2011-11-01 to 2024-01-03. It is static, its provenance is unclear, and it cannot be verified — [alphaneural XAUUSD dataset](https://app.alphaneural.io/datasets/ta4500/xauusd)

### Inferences
- **Bid/ask matters for gold scalping.** A $0.50 spread is a large share of a $3–5 scalp target. HistData M1 is bid-only, so a backtest must add the spread to long entries and short exits (half-spread to a mid price). Dukascopy is the only free source found with full bid **and** ask history at tick resolution back to 2003. You can build bid and ask M1 bars from its `BID_`/`ASK_candles_min_1.bi5` files or by resampling ticks.
- The spread measured on Dukascopy (median ~$0.50–0.58 in liquid hours in 2025–2026) is **wider than the advertised raw-ECN broker spreads** ($0.03–0.10 "from"). Using Dukascopy's ask/bid directly therefore makes a backtest conservative for a raw-account trader, and roughly right for a standard-account trader.
- Yahoo GC=F is a **futures** series: it trades at a premium to spot, and its front-month continuation jumps at each roll. Its intraday windows are rolling (30, 60 and 730 days), so a multi-year intraday archive is only possible by collecting it yourself every day.
- Dukascopy's 2003 history and its throttling mean a full tick download (~23 years × ~6,000 trading hours/year ≈ 140k files) takes many hours or days at polite request rates. Download M1 candle files per day (~24× fewer requests) for bar-level backtests, and ticks only for the periods where tick precision matters.

### Gaps
- **OANDA:** how far back XAU_USD M1 history goes, and the exact practice/live base URLs (commonly documented as `api-fxpractice.oanda.com` / `api-fxtrade.oanda.com`). The official docs page loaded only partly. Ownership, Singapore entity status and terms were not researched.
- **Stooq** (`stooq.com/q/d/l/?s=xauusd&i=d`): the connection was reset during the test. Whether it still serves free CSV, and whether it now needs an API key or captcha, is unknown.
- **Alpha Vantage, Tiingo, FXCM, Kaggle, MetaTrader 5 broker history:** no reliable 2026 sources found on gold coverage, history depth or limits. MT5 broker history depth varies by broker and server; check each one.
- **Licence and terms:** no explicit redistribution or commercial-use terms found for the Dukascopy datafeed, HistData or Yahoo. Treat all three as personal or research use only.
- Whether Massive lists gold as `C:XAUUSD` in its forex flat files was not confirmed.
- Twelve Data: whether the free tier covers XAU/USD intraday history, and how far back it goes, was not confirmed.
- No sources researched for paid tick-level **GC futures** history (for example CME DataMine, Databento, Norgate, Barchart).

---

## 2. Data quality issues: weekend gaps, daily break, DST, futures roll and continuous contracts, spot vs futures basis, volume

### Takeaway
Gold trades about 23 hours a day, Sunday 18:00 to Friday 17:00 New York time, with a daily one-hour halt at 17:00–18:00 ET. Measured spreads widen several-fold either side of that halt. Each source uses a different clock: Dukascopy UTC, HistData fixed EST (UTC−5, no DST), OANDA UTC with 17:00 NY daily alignment, Yahoo exchange time. Normalise everything to UTC and derive session labels from America/New_York. COMEX GC trades at a premium (basis) to spot. That premium blew out to $60–100+ in 2025 on tariff fears. Futures continuation series also have roll gaps that need back-adjustment.

### Cited Findings
- **Daily maintenance break, measured:** the Dukascopy XAUUSD tick file for 15 Sep 2026 at 21:00 UTC (= 17:00 EDT) is empty (0 bytes). In Yahoo GC=F 1h bars over 2 years, the 17:00 ET hour has only 7 bars against about 495 for every other hour. **[measured 2026-10-25]** — [Dukascopy datafeed](https://datafeed.dukascopy.com/datafeed/XAUUSD/2026/08/15/21h_ticks.bi5); [Yahoo chart API](https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1h)
- **Spreads around the break, measured:** Dukascopy median spread was $0.71 in the hour before the break and $0.82 in the reopen hour (max ~$5.8–6.0), against $0.51 in the 13:00 UTC overlap hour. **[measured 2026-10-25]** — [Dukascopy datafeed](https://datafeed.dukascopy.com/datafeed/XAUUSD/2026/08/15/22h_ticks.bi5)
- Rollover-window spreads "can jump 3–10 times" at roughly 21:00–23:00 GMT (educational blog, not broker execution data) — [dev.to: XAUUSD spread](https://dev.to/xauusdrobot/the-xauusd-spread-the-hidden-cost-that-quietly-decides-your-trading-results-574d). After about 20:00 server time, moves compress and spreads widen into the daily rollover — [MQL5 blog: XAUUSD trading day](https://www.mql5.com/en/blogs/post/772224)
- **Weekly open:** the first Yahoo GC=F 1h bar in the sample is Sunday 2024-10-27 22:00 UTC (= 18:00 EDT), which matches the Sunday 18:00 ET reopen. **[measured 2026-10-25]** — [Yahoo chart API](https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1h). Micro gold futures trade Sunday–Friday 5:00 p.m.–4:00 p.m. **CT** (= 18:00–17:00 ET) — [Optimus Futures: micro gold](https://optimusfutures.com/blog/micro-gold-futures/)
- **Time zones:** HistData uses EST without DST — [HistData spec](https://www.histdata.com/f-a-q/data-files-detailed-specification/). Dukascopy uses UTC — [dukascopy-node](https://www.dukascopy-node.app/instrument/xauusd). OANDA returns UTC, with daily candles aligned to 17:00 America/New_York by default — [OANDA Instrument Endpoints](https://developer.oanda.com/rest-live-v20/instrument-ep)
- Pepperstone applies the rollover/swap adjustment to positions open past **5 pm New York time** — [Pepperstone: trade gold on Razor](https://pepperstone.com/en-au/go/trade-gold-on-razor)
- **Futures listing and roll:** CME added October as a gold lead month effective **12 Jan 2026**. Base active months are now Feb, Apr, Jun, Aug, **Oct**, Dec, and CME publishes a schedule of last notice day, new spot month and new active month — [CME SER-9637R (June 2026)](https://www.cmegroup.com/content/dam/cmegroup/notices/ser/2026/06/ser-9637r.pdf). Older sources list only five base months (Feb, Apr, Jun, Aug, Dec) — [CME client site](https://cmegroupclientsite.atlassian.net/wiki/x/AQAqHQ). The standard definition: first notice day is the last business day of the month before delivery (older page, may be dated) — [Duke: COMEX gold futures](https://people.duke.edu/~charvey/options/cs/goldf.htm)
- Traders typically roll gold one or two days before first notice day, when volume shifts to the next contract (informal forum guidance) — [NexusFi thread](https://nexusfi.com/showthread.php?p=586456); [Metalsmine: gold roll date](https://www.metalsmine.com/news/988725-gold-futures-roll-date-april-2020/news)
- **Spot–futures basis (EFP):** the normal COMEX-vs-London EFP is about $10–20/oz (freight, storage, financing). In early 2025 it went from about $10 to over $60/oz on tariff fears — [Mappr: US gold exports](https://www.mappr.co/us-gold-exports/); [BullionVault: EFP and tariffs (Jan 2025)](https://www.bullionvault.com/gold-news/gold-price-news/gold-silver-efp-trump-tariffs-011420251); [StoneX Bullion weekly (13 Jan 2025)](https://stonexbullion.com/en/blog/gold-investment-trends-weekly-roundup-13january2025/). In August 2025 it reached over $100 intraday, then $57, after reports of a gold-bar tariff order (forum repost of a news report, unverified) — [Forex Peace Army repost](https://www.forexpeacearmy.com/community/threads/gold-pro-weekly-august-11-15-2025.86654/post-478211). A bank presentation argued the 2024–25 moves were more contained than the 2020 dislocation — [HSBC/Commerzbank to ECB FXCG (Mar 2025)](https://ecb.europa.eu/paym/groups/pdf/fxcg/2025/20250326/Item_1_Presentation_by_HSBC_and_COBA.pdf)
- **Volume:** HistData's volume column is 0 in the examples — [HistData spec](https://www.histdata.com/f-a-q/data-files-detailed-specification/). Dukascopy volumes are small floats in undocumented units. **[measured]** Yahoo GC=F 1h bars carry exchange volume: median about 18.6k contracts in the 09:00 ET hour against 0–3k in the overnight and reopen hours. **[measured 2026-10-25]** — [Yahoo chart API](https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1h)
- Educational sources say COMEX futures volume dominates gold price discovery — [MQL5 blog](https://www.mql5.com/en/blogs/post/772224)

### Inferences
- **Normalisation recipe:**
  - Store everything in UTC.
  - HistData: add 5 hours all year (fixed EST to UTC), with no DST logic.
  - Dukascopy: already UTC.
  - Derive the "trading day" as 17:00 America/New_York to 17:00 the next day, matching OANDA/broker daily candles, and use `zoneinfo` so DST shifts the break between 21:00 UTC (summer) and 22:00 UTC (winter).
  - Daily bars built at UTC midnight will not match broker or TradingView daily candles. Brokers using GMT+2/+3 server time align close to NY 17:00 (this convention is unverified here).
- **Gaps:**
  - Treat the 17:00–18:00 ET break and the Friday 17:00 to Sunday 18:00 ET weekend as non-trading. Do not forward-fill them as flat bars.
  - Model **gap risk**: stops get filled at the reopen price, not at the stop level.
  - Block or penalise entries in the last ~15 minutes before the break and the first ~15–30 minutes after it, when the measured spread is 1.4–1.6× normal at the median, with spikes over 10×.
- **Futures:**
  - For GC/MGC backtests, build a back-adjusted continuous series yourself. Roll about 2 days before first notice day of the Feb/Apr/Jun/Aug/Oct/Dec active contract (October joined from 2026), and use difference adjustment for P&L in dollars.
  - Never mix GC prices with XAUUSD spot prices in the same series.
  - The basis is normally the carry (about $10–20 here, more at higher rates and prices) and can spike to $60–100+.
- Volume-based indicators on spot data (Dukascopy, HistData) use tick or quote volume, not traded volume. For real volume, use GC futures data.

### Gaps
- An official CME page for GC trading hours and the exact maintenance window: cmegroup.com returned HTTP 503 during this research. The 17:00–18:00 ET halt is confirmed above by measurement, not by an exchange document.
- No source found that documents Dukascopy volume units or Dukascopy's own weekend/holiday schedule (for example, early closes on US holidays).
- No authoritative source on back-adjustment methods (ratio vs difference) specific to gold.

---

## 3. Trading costs for retail gold CFDs/spot (2025–2026) and contract specs

### Takeaway
Raw/ECN accounts advertise XAUUSD spreads "from" $0.03–0.10 plus about **$7 per 100-oz lot round turn** ($3.50 per side). Standard (no-commission) accounts run about $0.16–0.40, and MAS-regulated Singapore brokers such as IG quote "from" 0.3. Spreads widen 1.5–10× at the daily rollover and during NFP, CPI and FOMC. Long swaps are typically negative, roughly $30–60 per lot per night at 2026 prices, with triple swap on Wednesday. Contracts: 1 CFD lot = 100 oz; GC = 100 oz with a $0.10 tick worth $10; MGC = 10 oz with a $0.10 tick worth $1. Retail leverage in Singapore is capped at 20:1.

### Cited Findings

**Contract specifications**
- **Micro Gold (MGC):** 10 troy oz (1/10 of GC); minimum fluctuation $0.10/oz = **$1.00 per contract**; quoted in 10-cent increments like the 100-oz GC. So a GC tick is $10, and a $1 move is $100 for GC and $10 for MGC — [CME Micro Gold contract specs](https://cmegroup.com/markets/metals/precious/e-micro-gold.contractSpecs.options.html); [CME micro gold and silver overview](https://www.cmegroup.com/education/lessons/micro-gold-and-micro-silver-futures-product-overview)
- One third-party source cites a daily limit of 10% from the previous settlement and MGC margin around $825/$750; both are illustrative and change — [Optimus Futures](https://optimusfutures.com/blog/micro-gold-futures/)
- **CFD lot and points:** a broker spec sheet lists XAUUSD at **100 oz per lot** — [RoboMarkets XAUUSD spec](https://www.robomarkets.de/en/market-trading/trading/specifications/card/pro-stan/XAUUSD). With 2-decimal quoting, 1 point = $0.01 and is worth $1 per lot; some brokers quote 3 decimals (1 point = $0.001) — [FXNX: XAUUSD swap rates table](https://fxnx.com/en/blog/xauusd-swap-rates-table-nightly-long-short-cost-per-lot). "Pip" conventions vary: one guide equates a $25–35 move with "250–350 pips" (1 pip = $0.10) — [FXNX: gold vs FX volatility](https://fxnx.com/en/blog/gold-vs-forex-volatility-xauusd-data-guide)
- Dukascopy prices XAUUSD to 3 decimals (integer/1000). **[measured 2026-10-25]** — [Dukascopy datafeed](https://datafeed.dukascopy.com/datafeed/XAUUSD/2025/00/06/14h_ticks.bi5)

**Broker spreads and commissions (marketing "from" or third-party averages, so check live quotes)**

| Broker / account | XAUUSD spread | Commission | Source |
|---|---|---|---|
| IC Markets Raw Spread | 0.03 (third-party, May 2026, account not specified; market average 0.32) | $7 per standard lot round turn (help-centre pages that may be dated) | [IC Markets help centre](https://www.icmarkets.com/client-area/faq/?camp=2677); [BrokerChooser IC Markets XAUUSD](https://brokerchooser.com/de/broker-reviews/ic-markets-review/xauusd-spread) |
| IC Markets Standard | Raw spread + markup | None | [IC Markets help centre](https://www.icmarkets.com/client-area/faq/?camp=2677) |
| Pepperstone Razor | From **0.08** (AU pages); "0.1 on XAU/USD" (global page) | **$3.50 per lot per side** ($7 round trip, cTrader and Pepperstone platform, UK document) | [Pepperstone Razor gold](https://pepperstone.com/en-au/go/trade-gold-on-razor); [Pepperstone global](https://pepperstone.com/global/trading); [Pepperstone UK costs and charges](https://eu-assets.contentstack.com/v3/assets/bltd74737b907a31bbb/bltc19314db598b7ab0/UK_Legal_Costs_and_Charges.pdf) |
| Exness Raw Spread | About **$0.037** average (third-party) | $3.50 per side per lot | [TradersUnion: Exness XAUUSD](https://tradersunion.com/brokers/forex/view/exness/xauusd-spread/) |
| Exness Standard | About **$0.16** average (one source); "20–35 pips" (another); conflicting | None | [BrokerListings: Exness spreads](https://brokerlistings.com/reviews/exness/spreads) |
| Exness Zero | 0.0 | Conflicting reports ($5.50 per side, among others) | [BrokerListings: Exness spreads](https://brokerlistings.com/reviews/exness/spreads) |
| IG Singapore (MAS) | From **0.3** points | Built into spread | [IG SG commodities](https://www.ig.com/sg/commodities); [IG SG gold trading](https://www.ig.com/sg/commodities/gold-trading) |
| CMC Markets SG / Saxo SG | 0.3 / 0.6 (undated comparison table) | Not given | [MoneySmart CFD comparison](https://blog.moneysmart.sg/invest/cfd-trading-singapore) |

- Rough guide figures: raw-account spreads about 10–35 cents, standard about 30–50 cents (blog) — [dev.to: XAUUSD spread](https://dev.to/xauusdrobot/the-xauusd-spread-the-hidden-cost-that-quietly-decides-your-trading-results-574d). A broker-comparison article for 2026 also exists — [Finance Magnates: best gold brokers 2026](https://www.financemagnates.com/forex/best-brokers-to-trade-gold-in-2026-xauusd-brokers-compared/)
- On scalping, commission can have a considerable impact even on raw accounts — [MQL5: broker for scalping gold](https://www.mql5.com/en/blogs/post/773025)
- **Measured Dukascopy spread** (its own ECN quotes): median **$0.51–0.58** in liquid hours in 2025–2026, $0.71–0.82 around the daily break, max about $6. **[measured 2026-10-25]** — [Dukascopy datafeed](https://datafeed.dukascopy.com/datafeed/XAUUSD/2026/08/15/13h_ticks.bi5)

**News slippage**
- Around NFP, CPI and FOMC, spreads blow out and slippage happens within seconds. One blog says spreads can reach "several dollars for minutes". NFP and CPI release at 12:30/13:30 GMT and FOMC at 18:00/19:00 GMT, depending on DST. Stops on long positions fill at the bid. These are educational and blog sources, not execution statistics — [dev.to: XAUUSD spread](https://dev.to/xauusdrobot/the-xauusd-spread-the-hidden-cost-that-quietly-decides-your-trading-results-574d); [dev.to: XAUUSD sessions](https://dev.to/xauusdrobot/when-does-gold-actually-move-xauusd-trading-sessions-explained-i4a)
- The big US releases come at 08:30 and 10:00 NY — [MQL5 blog](https://www.mql5.com/en/blogs/post/772224)

**Swap and overnight financing**
- Swaps are broker-specific and quoted in points. One broker's Pro account lists long **−60** points and short +19; another listing from the same broker shows long −29 and short −3 — [RoboMarkets XAUUSD spec](https://www.robomarkets.de/en/market-trading/trading/specifications/card/pro-stan/XAUUSD)
- Cost per night = lots × swap points × point value. At 2 decimals, −32.50 points = **$32.50 per lot per night**. Many brokers apply a **triple swap on Wednesday**. A 2026 estimate: holding one long lot costs about **$30–45 per night** (author estimate) — [FXNX: XAUUSD swap rates table](https://fxnx.com/en/blog/xauusd-swap-rates-table-nightly-long-short-cost-per-lot)
- Of 32 accounts surveyed, all charged on gold longs except one offering promotional positive swaps (+19.99 long, no Wednesday triple) — [Finance Magnates: gold swaps](https://www.financemagnates.com/forex/analysis/the-battle-for-gold-traders-moves-overnight-32-accounts-charge-one-offers-positive-swaps/)
- Pepperstone charges swap when a position is held past 5 pm New York; the amount depends on interest-rate benchmarks and other factors — [Pepperstone Razor gold](https://pepperstone.com/en-au/go/trade-gold-on-razor)

**Singapore-specific**
- MAS has capped retail FX leverage at **20:1 since 8 Oct 2019**; accredited investors can access 50:1 — [Finance Magnates: FX leverage cut to 20:1 in Singapore](https://www.financemagnates.com/forex/regulation/fx-leverage-cut-to-201-in-singapore/)
- One March 2026 guide lists **gold at 20:1**, alongside major FX pairs and indices (equity CFDs 5–10:1, crypto 2:1) — [CapitalMarkets.SG leverage guide](https://capitalmarkets.sg/guides/best-leverage-forex-singapore). Another source is vaguer and says commodities are "even lower than forex", which conflicts — [StashAway: CFDs in Singapore](https://www.stashaway.sg/r/how-to-trade-cfd-singapore)
- IG Asia Pte Ltd is a Capital Markets Services licensee and has been MAS-regulated since 2005 — [IG SG commodities](https://www.ig.com/sg/commodities); [Singsaver: IG Asia](https://singsaver.com.sg/investment/products/ig-asia)
- A list of Singapore brokers exists, but it is a comparison site — [CompareForexBrokers SG](https://www.compareforexbrokers.com/sg)

### Inferences
- **Default cost model for XAUUSD in a backtest** (per 100-oz lot; all amounts in USD per oz unless stated):
  - **Raw/ECN account:** spread $0.15 in London/NY hours and $0.25 in Asia, plus $7 round-turn commission (= $0.07/oz). Total about **$0.22–0.32 per oz round trip**, i.e. $22–32 per lot.
  - **Standard or MAS-broker account:** spread $0.30–0.40, no commission.
  - **Conservative option:** use Dukascopy's actual bid/ask, median about $0.55.
  - **Spread multiplier by time:** 1.5× in the last 30 minutes before 17:00 ET and the first 60 minutes after 18:00 ET; 3–5× (or a no-trade window) from −2 to +5 minutes around NFP, CPI and FOMC; 1.2–1.5× in thin Asian hours.
  - **Slippage on market and stop orders:** about $0.05–0.10 normally; $0.50–2.00 within ±2 minutes of tier-1 US data. Stops crossing a gap fill at the next available price.
- **Financing from first principles:** at about $4,000/oz, 1 lot (100 oz) ≈ **$400,000 notional**, so each 1%/yr of financing costs about $11 per lot per night. Benchmark plus broker markup of 3–5%/yr gives about $33–55 per lot per night, which matches the $30–45 estimate and the −29 to −60 point quotes. Apply ×3 on Wednesday (most brokers; check yours). For swing trades held about 5 nights, swap (~$150–250 per lot) can exceed the spread and commission (~$25–40).
- At 2026 prices, a $0.30 spread is only about 0.007% of price, but against a $5 scalp target it is 6% of the gross move. Costs are what decide whether a scalping backtest is real or an illusion. Run every strategy at 1×, 1.5× and 2× cost.
- Singapore retail traders at 20:1 need margin of about 5% of notional, roughly **$20,000 per 100-oz lot** at $4,000. A 0.01 lot (1 oz) is about $200 margin. Use 1-oz-granular position sizing in the backtester.
- For futures accounts: GC at about $4,000 is about $400k notional per contract, so MGC (about $40k notional) is the practical retail size; tick $1 per MGC.

### Gaps
- **Unverified IC Markets XAUUSD figures:** live 2026 average spread (Raw vs Standard), the Standard-account gold markup, and whether the $7 round-turn commission has changed.
- **Swap data:** no current published XAUUSD swap figures for IC Markets, Pepperstone, Exness, OANDA, IG or Saxo (swap tables sit in client portals or MT5 symbol specs).
- **Singapore MAS rules and licensing:** the MAS rule text on retail leverage for **gold** CFDs (20:1 vs lower) was not found; the sources conflict. Which of IC Markets, Pepperstone and Exness hold an MAS licence, as opposed to serving Singapore clients offshore, was not verified (check the MAS Financial Institutions Directory). OANDA Asia Pacific, Saxo Markets SG and CMC Markets SG current gold spreads, commissions and swaps were not verified.
- **News execution data:** no broker execution statistics or measured spreads around NFP, CPI or FOMC found. The Dukascopy NFP-hour measurement (4 Sep 2026, 12h UTC) failed because of HTTP 429 throttling.
- COMEX exchange, clearing and broker commissions for GC/MGC were not researched; they typically run a few dollars per side per contract, but this is unverified.

---

## 4. Market sessions, when gold moves, and typical daily range (ATR) in 2024–2026

### Takeaway
Gold's busiest hours are **08:00–11:00 New York**: the COMEX day session (08:20 ET), US data at 08:30 and 10:00, and the London PM auction at 15:00 London (10:00 ET). In Singapore that is about 20:00–23:00 SGT in northern summer, or 21:00–24:00 in winter. A secondary bump appears at the Asian/Shanghai open (about 08:00–10:00 SGT). Volatility has risen sharply. Average daily true range was about $33–38 (about 1.5%) in 2024, $60–73 (about 1.9%) in 2025, and **about $152 (3.2%) in H1 2026** at the January 2026 peak. As of 23 Oct 2026 the 14-day ATR was about **$72** and the 60-day ATR about $95, with GC near $4,008. Older "$25–35 ATR" guidance is outdated.

### Cited Findings
- **LBMA Gold Price:** electronic auctions run by ICE Benchmark Administration (IBA) at **10:30 and 15:00 London time**, priced in USD (GBP and EUR versions are published but not tradeable). IBA took over from the London Gold Fix in March 2015 and is FCA-authorised. Prices are not published on weekends or UK bank holidays, and use for valuation needs an IBA licence — [LBMA Gold Price](https://www.lbma.org.uk/prices-and-data/lbma-gold-price/lbma-gold-price); [ICE IBA LBMA gold and silver](https://www.ice.com/iba/lbma-gold-silver-price); [ICE precious metals benchmark statement](https://ice.com/publicdocs/Precious_Metals_Benchmark_statement.pdf); [LBMA prices summary](https://www.lbma.org.uk/lbma-prices-summary)
- **COMEX:** activity picks up around **08:20 NY**. The old COMEX pit session ran 08:20–13:30 NY, and the 13:30 close is still watched — [TradingView London-open scripts](https://www.tradingview.com/scripts/londonopen/); [TradingView NY-open scripts](https://br.tradingview.com/scripts/newyorkopen/)
- **Overlap and news:** the London–NY overlap (about 08:00–12:00 ET / 13:00–17:00 GMT) has the highest liquidity and the strongest moves. Major moves follow Fed decisions, CPI and geopolitics — [CMC Markets: gold trading hours](https://www.cmcmarkets.com/en-gb/commodities/gold-trading-hours); [RoboForex: XAUUSD](https://roboforex.com/blog/education/gold-trading-xauusd/); [FXStreet: gold market hours](https://www.fxstreet.com/education/guides/gold/what-time-does-the-gold-market-open-gold-trading-hours); [MQL5 blog](https://www.mql5.com/en/blogs/post/772224)
- **Volatility by hour, measured.** Source: Yahoo GC=F 1h bars, 2024-10-27 to 2026-10-23, about 495 bars per hour bucket; mean (high−low)/close per hourly bar, by New York clock hour. **[measured 2026-10-25]** — [Yahoo chart API](https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1h)

  | NY hour (ET) | SGT (EDT / EST) | Mean 1h range % | Mean 1h range $ | Median volume (contracts) |
  |---|---|---|---|---|
  | 18:00 (reopen) | 06 / 07 | 0.42 | 16.9 | 0 |
  | 19:00 | 07 / 08 | 0.36 | 14.2 | 2,610 |
  | 20:00 | 08 / 09 | 0.50 | 20.0 | 4,780 |
  | 21:00 | 09 / 10 | 0.54 | 21.4 | 5,889 |
  | 22:00–00:00 | 10–12 / 11–13 | 0.31–0.41 | 12–16 | 3–4k |
  | 01:00–07:00 (London) | 13–19 / 14–20 | 0.37–0.44 | 14.5–17.2 | 4.5–6.7k |
  | **08:00** | 20 / 21 | **0.63** | **24.7** | 13,844 |
  | **09:00** | 21 / 22 | **0.70** | **27.3** | **18,567** |
  | **10:00** | 22 / 23 | **0.68** | **26.9** | 17,527 |
  | 11:00 | 23 / 00 | 0.53 | 21.0 | 11,932 |
  | 12:00–15:00 | 00–03 / 01–04 | 0.36–0.42 | 14.5–16.4 | 4.7–9.4k |
  | 16:00 (pre-break) | 04 / 05 | 0.30 | 11.9 | 2,314 |
  | 17:00 (break) | 05 / 06 | n/a (7 bars) | n/a | ~0 |

- **Daily true range by half-year,** measured from Yahoo GC=F daily bars. **[measured 2026-10-25]** — [Yahoo chart API](https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1d)

  | Period | Mean TR | Median TR | Mean TR % | Average close | Max TR |
  |---|---|---|---|---|---|
  | 2023-H1 | $28.4 | $26.5 | 1.46% | $1,942 | $71 |
  | 2023-H2 | $22.8 | $19.5 | 1.15% | $1,967 | $114 |
  | 2024-H1 | $33.3 | $30.2 | 1.48% | $2,216 | $102 |
  | 2024-H2 | $37.6 | $34.0 | 1.46% | $2,587 | $107 |
  | 2025-H1 | $60.3 | $50.3 | 1.92% | $3,088 | $149 |
  | 2025-H2 | $72.5 | $61.1 | 1.86% | $3,827 | $301 |
  | **2026-H1** | **$151.6** | **$127.8** | **3.22%** | **$4,703** | **$780** |
  | 2026-H2 (to 23 Oct) | $94.7 | $89.7 | 2.21% | $4,269 | $207 |

  As of 2026-10-23: **ATR(14) ≈ $71.9, ATR(60) ≈ $95.4, last close $4,007.9**. Highest daily close in the sample: **$5,318.4 on 2026-01-29**.
- The record close is corroborated: gold futures closed at a record $5,318 on 29 Jan 2026 and were about $4,157 on 5 Oct 2026, roughly 21.8% below the record — [thetrading.tools gold price](https://www.thetrading.tools/gold-price). Sources disagree on the January 2026 intraday peak (about $5,420 to $5,595) — same search set; unverified. Early-2026 context: a record start to 2026 put $5,000 gold in view — [Engineering News (Jan 2026)](https://www.engineeringnews.co.za/article/record-start-to-2026-brings-prospect-of-5-000-gold-into-view-2026-01-13)
- **Outdated figures, flagged:** a 2026 guide says a 14-day gold ATR "frequently hovers between $25 and $35" — [FXNX](https://fxnx.com/en/blog/gold-vs-forex-volatility-xauusd-data-guide). Another says daily range "regularly reaches 30–60 USD", with over $100 on news — [RoboForex](https://roboforex.com/blog/education/gold-trading-xauusd/). Both match 2023–2024 levels, not 2025–2026.

### Inferences
- **Singapore-based trader:**
  - The prime gold window is about **20:00–24:00 SGT** (northern summer) or **21:00–01:00 SGT** (northern winter), when the London/NY overlap and US data hit.
  - A secondary window opens at **08:00–10:00 SGT**, around the Asia/Shanghai open; it is about 0.50–0.54% per hour against about 0.31% at the quietest hours.
  - The daily break falls at **05:00–06:00 SGT** (summer) or **06:00–07:00 SGT** (winter).
  - Session filters in the backtester should be defined in America/New_York and Europe/London time, not fixed UTC or SGT, so they track DST correctly.
- **Scale parameters to volatility, not dollars.** Daily range more than quadrupled from 2023 to H1 2026 ($23–28 to $152), so fixed-dollar stops, targets and slippage tuned on 2023–2024 data will be badly mis-scaled for 2026, and the reverse is also true. Use ATR- or percentage-based stops and targets, and run walk-forward tests separately across regimes: 2023–24 low-vol, 2025 trending, 2026-H1 blow-off and crash, 2026-H2.
- Costs fall in relative terms as volatility rises. A $0.30 spread is about 0.2% of a 2026 1h range ($15–27) against about 1% of a 2023 1h range. Scalping strategies that look profitable in 2026 may be untradeable in quieter regimes.
- The 2026-H1 max TR of $780 implies extreme gap and limit-move risk. Backtests should include stop-gap slippage and margin-call logic at 20:1.

### Gaps
- The measured hourly profile uses futures (GC=F) bars over only the last 2 years (Yahoo's 730-day limit). A longer spot profile would need Dukascopy M1 data.
- The exact date and cause of the $780 true-range day in 2026-H1 were not researched.
- No primary-source intraday volatility statistics, such as CME or LBMA research, were found; the hourly profile is the researcher's own calculation.

---

## 5. Recommended sources: (a) quick start with no account, (b) serious multi-year intraday backtests

### Takeaway
**(a) Quick start:** use yfinance `GC=F` for daily data over the full history and 1h over 730 days. Add **HistData** M1 XAUUSD (2009 to the latest month, bid-only, fixed EST) for intraday prototyping. Neither needs an account.
**(b) Serious work:** use **Dukascopy** bid and ask M1 candles (and ticks where needed) from 2003 as the primary spot dataset, cross-checked against HistData. Add **OANDA v20** bid/ask candles from a free practice account, or your own broker's MT5 history, to calibrate to the broker you will actually trade. For futures, build a back-adjusted GC/MGC series from a paid vendor; Massive's $49/month FX tier covers spot FX back to 2009.

### Cited Findings
- Dukascopy offers free, account-less bid/ask ticks and M1 candles from 2003-05-05 (UTC), but throttles with HTTP 429 — [dukascopy-node](https://www.dukascopy-node.app/instrument/xauusd); **[measured 2026-10-25]** [Dukascopy datafeed](https://datafeed.dukascopy.com/datafeed/XAUUSD/2025/00/06/BID_candles_min_1.bi5)
- HistData offers free M1 bars from 2009 to Oct 2026, bid-only, in EST without DST — [HistData XAUUSD M1](https://www.histdata.com/download-free-forex-data/?/ascii/1-minute-bar-quotes/xauusd); [HistData spec](https://www.histdata.com/f-a-q/data-files-detailed-specification/)
- Yahoo/yfinance limits: 1m within 30 days (8 days per request); 2m–90m within 60 days; 1h within 730 days; daily is unrestricted — **[measured 2026-10-25]** [Yahoo chart API](https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1m&range=30d); [yfinance history.py](https://github.com/ranaroussi/yfinance/blob/main/yfinance/scrapers/history.py)
- OANDA v20 offers M/B/A candles at up to 5,000 per request, UTC timestamps, and 17:00 NY daily alignment — [OANDA Instrument Endpoints](https://developer.oanda.com/rest-live-v20/instrument-ep); [oandapyV20 docs](https://oanda-api-v20.readthedocs.io/en/stable/contrib/factories/instrumentscandlesfactory.html)
- Massive FX minute flat files go back to 2009-09-25, at $49/month for Currencies Starter — [Massive docs](https://massive.com/docs/flat-files/forex/minute-aggregates.md)
- Free API tiers (Twelve Data at 800 credits/day; TraderMade free with 2 days of minute history) are too limited for multi-year intraday pulls — [Twelve Data support](https://support.twelvedata.com/en/articles/5194820-api-credits-limits); [TraderMade](https://marketdata.tradermade.com/download-forex-data)

### Inferences
- **Suggested pipeline:**
  1. Download Dukascopy `BID_candles_min_1.bi5` and `ASK_candles_min_1.bi5` per day for 2003 (or 2009) to the present. Throttle to about 1–2 requests per second with exponential backoff on 429. Treat a 0-byte file as a no-trade day and a 113-byte file as a retry.
  2. Decode the 24-byte rows as `>IIIIIf` (O, C, L, H order), divide prices by 1000, and store as Parquet in UTC.
  3. Resample to M5, M15, H1, H4 and D1. Use the 17:00 New York session boundary for D1 so daily bars match brokers and TradingView.
  4. Validate against HistData M1 bid (convert EST+5 to UTC) and against Yahoo GC=F daily (expect a positive futures basis).
  5. Model execution on bid/ask: buy at ask, sell at bid. Optionally replace Dukascopy's spread (about $0.55) with a broker-specific spread model for raw accounts.
- For a TradingView-centred workflow, TradingView's own XAUUSD feeds (OANDA, FXCM, broker feeds) will differ by cents to dollars from Dukascopy. Signal timing should be robust to that, and a quick check is to replay a few weeks of TradingView-exported bars through the Python engine.
- Hourly-collected Yahoo data is acceptable for monitoring only. Its 730-day 1h window and 30-day 1m window make it unsuitable as the archive of record.

### Gaps
- Not researched: the tick-replay quality differences between Dukascopy and retail MT5 broker feeds (for example quote filtering, and spread differences during news).
- Not established: the legal permissibility of storing or redistributing Dukascopy, HistData or Yahoo data inside a shared or commercial tool. Check each provider's terms before shipping data with the backtester.
- Cheapest reliable source of multi-year **GC/MGC intraday futures** data with roll metadata: not researched.
