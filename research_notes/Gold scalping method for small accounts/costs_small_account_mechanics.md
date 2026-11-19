# Costs, microstructure and account mechanics for scalping XAUUSD with a $100 account (Singapore retail, November 2026)

Conventions used throughout: prices and costs are in US dollars per troy ounce ($/oz). 1 standard CFD lot = 100 oz, so 0.01 lot = 1 oz and a $1 move = $1 P&L per ounce held. "Round trip" (RT) = one entry plus one exit. "Own computation" means numbers computed for these notes on 19 Nov 2026 from the project's Dukascopy bid/ask sample files (5m and 15m: 1 Jan 2025 to 3 May 2026; 1h: Jan 2019 to 30 Sep 2026). In those files the spread column is the average of the bar-open and bar-close ask-minus-bid, at hourly resolution, so spikes lasting seconds are smoothed away. TR = true range of one bar. All times are given in UTC with Singapore time (SGT = UTC+8) alongside.

## 1. Spreads: typical and worst case by broker, account type and time of day; have they widened as gold rose?

### Takeaway
On a real ECN feed (Dukascopy) the median gold spread is now about $0.65 to $0.75/oz in normal hours, roughly double the $0.33 to $0.38 of 2023 to 2024, but almost unchanged as a share of price (about 1.5 to 1.7 basis points); the tail got worse, with the 95th percentile rising from $0.72 (2024) to $2.14 (2026). The reopen hour after the daily break is 4 to 5 times normal (median about $3, worst $8), while broker "from 0.3" and "raw from 0.03 to 0.08" figures are minimums or undated third-party numbers that could not be verified against 2026 conditions.

### Cited Findings
Measured ECN spread (Dukascopy bid/ask), by year:

| Year | Avg price | Median spread $/oz | 95th pct $/oz | Median spread, bps of price |
|---|---|---|---|---|
| 2019 | 1,393 | 0.29 | 0.50 | 2.10 |
| 2023 | 1,943 | 0.33 | 0.70 | 1.72 |
| 2024 | 2,389 | 0.38 | 0.72 | 1.59 |
| 2025 | 3,442 | 0.60 | 1.18 | 1.73 |
| 2026 (Jan to Sep) | 4,547 | 0.71 | 2.14 | 1.55 |

- Table above — [own computation from Dukascopy 1h sample](../../gold-backtester/data/sample/XAUUSD_1h.csv.gz)
- Most recent months measured: monthly median spread was $0.64 (Jun 2026), $0.69 (Jul), $0.65 (Aug), $0.68 (Sep); monthly mean $0.75 to $0.89; monthly 95th percentile $1.81 to $2.71 — [own computation from Dukascopy 1h sample](../../gold-backtester/data/sample/XAUUSD_1h.csv.gz)

Measured spread by time of day, Jan to 3 May 2026 (gold averaging $4,835):

| Window (UTC) | SGT | Median $/oz | 95th pct | Max |
|---|---|---|---|---|
| Asia 00:00 to 07:00 | 08:00 to 15:00 | 0.76 | 1.37 | 3.65 |
| London 07:00 to 12:00 | 15:00 to 20:00 | 0.71 | 1.14 | 2.64 |
| London/NY overlap 12:00 to 17:00 | 20:00 to 01:00 | 0.76 | 1.48 | 6.30 |
| NY afternoon 17:00 to 21:00 | 01:00 to 05:00 | 0.74 | 1.96 | 3.35 |
| Rollover and reopen 21:00 to 24:00 | 05:00 to 08:00 | 1.87 (mean 2.29) | 5.22 | 8.09 |

- Table above — [own computation from Dukascopy 5m sample](../../gold-backtester/data/sample/XAUUSD_5m.csv.gz)
- Jun to Sep 2026 by hour (gold averaging $4,258): cheapest hours were 08:00 to 12:00 UTC (16:00 to 20:00 SGT) at a median $0.54 to $0.58; Asia 00:00 to 05:00 UTC was $0.73 to $0.77; the US data hours 13:00 to 14:00 UTC were $0.65 with hourly maxima of $1.67 to $2.20; the hour before the break (20:00 UTC in US summer time) had a median $0.90 and mean $1.36; the reopen hour (22:00 UTC) had a median $3.23 and max $6.96; the next hour (23:00 UTC) $1.26 with max $5.34 — [own computation from Dukascopy 1h sample](../../gold-backtester/data/sample/XAUUSD_1h.csv.gz)
- In New York clock time for all of 2026 (Jan to Sep): 16:00 to 17:00 NY median $1.16, 95th pct $3.11; 18:00 to 19:00 NY (first hour after the break) median $3.00, mean $3.13, 95th pct $6.04, max $8.09; 19:00 to 20:00 NY median $1.09, 95th pct $1.91 — [own computation from Dukascopy 1h sample](../../gold-backtester/data/sample/XAUUSD_1h.csv.gz)
- In 2026, 19.1% of all 5-minute bars had a spread above $1.00 and 6.4% above $2.00; at 22:00 UTC 97.5% of bars had a spread above $1.50, against 1% to 8% in the main sessions — [own computation from Dukascopy 5m sample](../../gold-backtester/data/sample/XAUUSD_5m.csv.gz)
- News: on first-Friday (NFP-proxy) days the 08:00 to 09:00 New York hour had an hourly-sampled spread of $0.63, the same as other weekdays ($0.62), while the 1-hour true range was 1.5 times larger (median $26.9 against $17.8). Hourly open/close sampling cannot see spikes that last seconds, so this does not show that news is cheap — [own computation from Dukascopy 1h sample](../../gold-backtester/data/sample/XAUUSD_1h.csv.gz)
- A promotional blog (no method disclosed) reports rollover spreads of $2.00 to $2.80 for 5 to 10 minutes and US CPI peak spreads of $1.80 to $3.50, returning to normal in about 45 to 90 seconds — [FXNX blog](https://fxnx.com/en/blog/xauusd-spread-dated-log-measured-cost-changes)
- IG Singapore (MAS-licensed IG Asia Pte Ltd): spot gold contract spread 0.3 (a minimum, in $/oz), no time-of-day breakdown; page dated 29 June 2026 — [IG SG commodities product details](https://www.ig.com/sg/help-and-support/articles/720379-what-are-ig-s-commodities-cfd-product-details); [IG SG gold trading](https://www.ig.com/sg/commodities/gold-trading)
- IG dealing hours for spot gold: 24 hours except 22:00 to 23:00 London time — [IG SG commodities product details](https://www.ig.com/sg/help-and-support/articles/720379-what-are-ig-s-commodities-cfd-product-details)
- OANDA: BrokerChooser lists OANDA's XAU/USD spread as 0.38 against a 0.32 average across the 100+ brokers it covers; entity and date not stated — [BrokerChooser OANDA XAUUSD](https://brokerchooser.com/fi/broker-reviews/oanda-review/xauusd-spread)
- OANDA Asia Pacific "core" pricing charges, on top of a reduced spread, US$3.00 per 50 units of XAU/USD per side for USD accounts (S$4.40 for SGD accounts), pro rata, minimum $0.01 per trade. That is $0.06/oz per side, $0.12/oz RT (S$0.176/oz RT in SGD) — [OANDA Asia Pacific core price sheet, Q4 2025](https://www.oanda.com/assets/documents/1992/Q425_offer__OANDA_Asia_Pacific_Core_spreads__Commissions_Price_Sheet_.pdf)
- IC Markets gold: spreads "variable", commission on Raw Spread accounts US$7 (S$9.50) per 100-oz lot round turn = $0.07/oz RT — [IC Markets commodity specification sheet](https://cdn.icmarkets.com/uploads/Commodity+Specification+Sheet.pdf)
- Pepperstone describes Razor gold as raw spreads "starting at 0.08" plus a fixed commission; no average or commission figure was retrievable — [Pepperstone Razor gold](https://pepperstone.com/en/go/trade-gold-on-razor)
- Third-party averages carried over from the project's earlier notes (not re-verified, mostly from when gold was lower): IC Markets Raw 0.03 (BrokerChooser, May 2026, market average 0.32); Exness Raw about $0.037 plus $3.50 per side per lot; Exness Standard about $0.16 — [BrokerChooser IC Markets XAUUSD](https://brokerchooser.com/de/broker-reviews/ic-markets-review/xauusd-spread); [TradersUnion Exness XAUUSD](https://tradersunion.com/brokers/forex/view/exness/xauusd-spread/); [BrokerListings Exness spreads](https://brokerlistings.com/reviews/exness/spreads)
- BrokersView's January 2026 "Singapore broker spread analysis" gives average XAUUSD spreads of 8.2 points (AUS Global), 14 (Decode Global) and 16.6 (Eightcap); the point size is not defined (if 1 point = $0.01 these are $0.08 to $0.17), and the page disclaims accuracy — [FastBull BrokersView, 12 Feb 2026](https://www.fastbull.com/brokersview/news/whichbrokeroffersbetterspreadsbrokersviewjanuary2026singaporebrokerspreadanalysis-321681)
- Dukascopy's daily break for XAU/USD is 21:00 to 22:00 GMT in summer and 22:00 to 23:00 GMT in winter — [Dukascopy fee schedule](https://www.dukascopy.com/swiss/ch/about/fee-schedule/)

### Inferences
- Dollar spreads have widened roughly in line with price: about 1.9 times from 2024 to 2026 while price rose about 1.9 times. Any dollar spread quoted from the sub-$2,500 era (for example "0.15 to 0.25 raw") should be scaled up by about 1.6 to 2 times before use at $4,050, unless confirmed on a live feed.
- For November 2026 (US standard time) the break is 22:00 to 23:00 UTC = 06:00 to 07:00 SGT. The expensive window for a Singapore trader is roughly 05:00 to 08:00 SGT: the hour before the break, the break itself, and the first hour after reopening.
- The cheapest spread window is London morning, 16:00 to 20:00 SGT. The Asian morning (08:00 to 13:00 SGT) costs about $0.10 to $0.20 more per ounce on the ECN feed.
- A fixed "0.3" at IG is a floor, and the Dukascopy feed (median $0.65 to $0.75) is likely a conservative stand-in for a spread-only MAS broker in liquid hours; the true live spread at OANDA or IG at $4,050 gold has to be logged from the platform or the v20 pricing stream.

### Gaps
- No current (2026) published average or time-of-day gold spread was found for OANDA Asia Pacific, IG, Saxo, Pepperstone, IC Markets, Exness or Interactive Brokers. OANDA's historical-spreads tool and Myfxbook's spread table could not be read (dynamic page; HTTP 403).
- No tick-level measurement of spread around NFP, CPI or FOMC was made; the hourly data cannot show it and the only figures found are from an undocumented blog.
- Saxo Singapore gold spread, commission and minimum size were not found (pricing table failed to load).
- Units in several third-party comparisons ("points", "pips") were undefined, so they cannot be converted to $/oz with confidence.

## 2. All-in cost per round trip, and cost as a share of 5-minute and 15-minute ATR

### Takeaway
A market-order scalp costs roughly $0.27 to $0.37/oz RT on a best-case offshore raw account, $0.40 to $0.50 on an MAS-regulated spread-only account at its advertised minimum, and $0.82 to $0.92 if the real Dukascopy spread is paid (the project backtester's model). With daily ATR near $75, a typical 5-minute bar is about $3 and a 15-minute bar about $5.4, so the cost is 9% to 31% of one 5-minute bar and 5% to 17% of one 15-minute bar.

### Cited Findings
Measured bar ranges (true range, $/oz):

| Period | Avg price | Daily TR (mean) | 5m TR median / mean | 15m TR median / mean |
|---|---|---|---|---|
| 2025 H1 | 3,074 | 53.8 | 2.24 / 2.81 | 4.02 / 4.98 |
| 2025 H2 | 3,800 | 66.1 | 2.80 / 3.61 | 4.95 / 6.38 |
| 2026 Jan to 3 May | 4,835 | 154.2 | 6.01 / 8.23 | 10.77 / 14.61 |

- Table above — [own computation from Dukascopy 5m sample](../../gold-backtester/data/sample/XAUUSD_5m.csv.gz); [15m sample](../../gold-backtester/data/sample/XAUUSD_15m.csv.gz)

By session, median TR ($/oz):

| Session (UTC / SGT) | 5m, 2025 H2 | 5m, 2026 Jan to May | 15m, 2025 H2 | 15m, 2026 Jan to May |
|---|---|---|---|---|
| Asia 00 to 07 / 08 to 15 | 2.68 | 5.64 | 4.78 | 10.08 |
| London 07 to 12 / 15 to 20 | 2.65 | 5.38 | 4.76 | 9.44 |
| NY overlap 12 to 17 / 20 to 01 | 3.91 | 7.89 | 7.00 | 14.18 |
| NY afternoon 17 to 21 / 01 to 05 | 2.32 | 5.43 | 4.12 | 9.70 |
| Late and rollover 21 to 24 / 05 to 08 | 2.11 | 5.68 | 3.70 | 10.69 |

- Table above — [own computation from Dukascopy 5m sample](../../gold-backtester/data/sample/XAUUSD_5m.csv.gz); [15m sample](../../gold-backtester/data/sample/XAUUSD_15m.csv.gz)
- The ratio of intraday bar range to daily range was stable across three very different regimes: 5m median TR = 3.9% to 4.2% of mean daily TR (5m mean = 5.2% to 5.5%); 15m median = 7.0% to 7.5% (15m mean = 9.3% to 9.6%) — [own computation from Dukascopy samples](../../gold-backtester/data/sample/XAUUSD_5m.csv.gz)
- Daily TR after the 5m/15m files end: monthly mean $112 (Jun 2026), $87 (Jul), $104 (Aug), $96 (Sep) — [own computation from Dukascopy 1h sample](../../gold-backtester/data/sample/XAUUSD_1h.csv.gz)
- Measured spread as a share of the median 5m bar, by hour, 2026: 8% to 9% at 13:00 to 15:00 UTC, 10% at 01:00 UTC, 12% to 14% in London hours, 20% at 04:00 UTC (Asian lunch), 30% to 43% at 21:00 to 23:00 UTC — [own computation from Dukascopy 5m sample](../../gold-backtester/data/sample/XAUUSD_5m.csv.gz)
- The spread as a share of the median 5m bar was far higher in quiet months: 34% in Jan 2025, 30% to 31% in Jul to Aug 2025, against 10% to 14% in Jan to Apr 2026 — [own computation from Dukascopy 5m sample](../../gold-backtester/data/sample/XAUUSD_5m.csv.gz)
- The backtester's "realistic" preset charges the recorded spread, $7 per lot round turn, and 5 ticks ($0.05) of slippage on every market and stop fill (none on limit fills) — [goldlab broker.py](../../gold-backtester/goldlab/engine/broker.py)
- Commission inputs: IC Markets Raw $0.07/oz RT; OANDA core $0.12/oz RT — [IC Markets spec sheet](https://cdn.icmarkets.com/uploads/Commodity+Specification+Sheet.pdf); [OANDA core price sheet](https://www.oanda.com/assets/documents/1992/Q425_offer__OANDA_Asia_Pacific_Core_spreads__Commissions_Price_Sheet_.pdf)
- Interactive Brokers Singapore prices London Gold CFDs at 1.5 basis points of trade value with a US$2.00 minimum per order; its knowledge base states the same 0.015% and US$2.00 minimum — [IBKR SG metals CFD commissions](https://www.interactivebrokers.com.sg/en/pricing/commissions-cfd-metals.php); [IBKR KB 3642](https://ibkb.interactivebrokers.com/article/3642)
- Dukascopy's older tariff lists metals at US$52.50 per US$1 million traded at the base tier (figures conflict across sources and may be dated) — [Dukascopy tariffs PDF](https://www.dukascopy.com/swiss/docs/bankFormsEU/Tariffs.pdf)

### Inferences
Estimated all-in cost per market-order round trip in liquid hours (estimate; slippage of $0.05 per fill is the backtester's assumption, not a measurement):

| Account type | Spread | Commission | Slippage (2 fills) | All-in $/oz RT |
|---|---|---|---|---|
| Offshore raw/ECN, best case (advertised spreads, unverified at $4,050) | 0.10 to 0.20 | 0.07 | 0.10 | 0.27 to 0.37 |
| MAS spread-only at advertised minimum (IG 0.30; OANDA 0.38 third-party) | 0.30 to 0.40 | 0 | 0.10 | 0.40 to 0.50 |
| Dukascopy-like measured feed (backtester model) | 0.65 to 0.75 | 0.07 | 0.10 | 0.82 to 0.92 |
| Any account in the reopen hour | about 3.00 (up to 8) | 0 to 0.12 | 0.10 or more | 3 or more |

Estimated bar ranges for November 2026, scaling the stable ratios above to a $75 daily ATR (estimate): 5m median about $2.9 to $3.2 (mean about $4.0); 15m median about $5.3 to $5.6 (mean about $7.1). By session the 5m median is roughly $2.9 in Asia and London, $4.2 in the NY overlap, $2.5 in the NY afternoon and $2.3 late; the 15m median roughly $5.3, $5.1, $7.4, $4.4 and $4.2. 2025 H2 (daily TR $66) is the closest measured analogue.

Cost as a share of one typical bar:

| All-in cost $/oz | % of 5m median ($3.0, Nov 2026 est.) | % of 15m median ($5.4) | % of 5m median, 2026 H1 ($6.0) | % of 15m median, 2026 H1 ($10.8) |
|---|---|---|---|---|
| 0.27 to 0.37 | 9 to 12 | 5 to 7 | 4.5 to 6 | 2.5 to 3.4 |
| 0.40 to 0.50 | 13 to 17 | 7 to 9 | 7 to 8 | 3.7 to 4.6 |
| 0.82 to 0.92 | 27 to 31 | 15 to 17 | 14 to 15 | 7.6 to 8.5 |

- Volatility has roughly halved since the Jan to Apr 2026 blow-off while dollar spreads fell only slightly ($0.79 to $0.84 median in Feb to Mar 2026 against $0.65 to $0.68 in Aug to Sep). Cost relative to bar size is therefore about 1.5 to 2 times worse now than in the period where most of the backtest data sits. A strategy that only just clears costs on Jan to May 2026 data should be expected to fail at November 2026 volatility.
- Targets of $2 to $3/oz are about one median 5-minute bar; a $0.45 cost is 15% to 23% of that target. Targets of $8 to $10 (about 1.5 to 2 median 15-minute bars) bring the cost down to about 5% of target. This favours the 15-minute chart and targets of at least 10 times the cost.
- Minimum-fee brokers are unusable at tiny size: IBKR's US$2 minimum per order is $4 per round trip, which is $4/oz on 1 oz and $40/oz on 0.1 oz. Dukascopy's quoted 52.5 per million would be about $0.21/oz per side at $4,050 (about $0.43/oz RT), if still current.
- Using limit orders for entries or take-profits removes slippage on that fill in the backtester and saves half the spread only if the limit rests inside the spread; that should be tested, not assumed.

### Gaps
- No measured slippage statistics for retail gold market or stop orders were found; $0.05 per fill is an assumption. Stops during news can slip by dollars.
- 5m and 15m data end on 3 May 2026; November 2026 bar ranges are scaled estimates, not measurements.
- OANDA Asia Pacific's actual core and spread-only gold spreads were not retrievable, so its all-in cost is not pinned down.

## 3. Minimum position sizes: who allows less than 0.01 lot (1 oz), and what is available to Singapore residents

### Takeaway
Two MAS-licensed brokers list sub-ounce gold: OANDA Asia Pacific (minimum 0.1 units on the OANDA platform, 0.001 lot on MT5, but 0.01 lot = 1 oz on MT4) and IG Asia (minimum 0.05 of a US$1-per-point contract). Futures do not fit: MGC needs about US$2,180 margin and even the 1-ounce 1OZ contract needs US$219 at a Singapore broker. Cent accounts that go down to 0.01 oz exist only at offshore brokers.

### Cited Findings
- OANDA Singapore minimum trade sizes: "Gold CFD" 0.1 units on the OANDA platform, 0.01 lots on MT4, 0.001 lots on MT5. FX CFDs are 1 unit; silver 1 unit — [OANDA SG help: minimum trade size](https://help.oanda.com/sg/en/faqs/minimum-trade-size.htm)
- The same page does not define the gold unit; the project's OANDA adapter treats XAU_USD as 1 unit = 1 oz — [goldlab oanda.py](../../gold-backtester/goldlab/live/brokers/oanda.py)
- OANDA says there is no minimum deposit to open an account, but available funds limit position size — [OANDA Asia Pacific margin rules, July 2025](https://www.oanda.com/assets/documents/1982/OAP_Margin_Rules_-_July_2025.pdf)
- IG Singapore spot gold market page: minimum size 0.05, contract size US$1, one point = $1 per troy ounce, minimum stop distance 1. The quote on the page (3,735.87 / 3,736.17) is stale relative to November 2026, so the page date is uncertain — [IG SG spot gold market page](https://www.ig.com/sg/commodities/markets-commodities/gold)
- IG's product-details page instead describes spot gold as a 100-oz contract worth US$100 per point, a mini contract at 33% of that, and says minimum sizes "usually start from one contract"; a separate IG page lists a standard gold minimum of 3 reduced to 1.5 for the first 14 days. These conflict with the 0.05 figure — [IG SG commodities product details](https://www.ig.com/sg/help-and-support/articles/720379-what-are-ig-s-commodities-cfd-product-details); [IG SG reduced minimums](https://www.ig.com/sg/reduced-minimums)
- IC Markets gold: minimum 1 oz (MT4 volume 0.01), contract size 100 oz, scalping allowed, no minimum stop distance — [IC Markets spec sheet](https://cdn.icmarkets.com/uploads/Commodity+Specification+Sheet.pdf)
- Cent accounts: Fullerton Markets lists gold on cent accounts at 1 unit per lot with a 0.01-lot minimum and step; VT Markets describes a cent lot as 0.01 of a standard lot — [Fullerton Markets cent account specs](https://fullertonmarkets.ladesk.com/725088-What-are-the-contract-specifications-for-Cent-Accounts); [VT Markets: cent accounts](https://www.vtmarkets.com/en-eu/discover/what-is-a-trading-cent-account/)
- Exness has a Standard Cent account with a "c" symbol suffix; third-party sources conflict on its gold contract size — [BrokerListings: Exness cent account](https://brokerlistings.com/reviews/exness/does-exness-have-a-cent-account)
- Interactive Brokers: London spot gold (XAUUSD) has a 1-ounce minimum order, but IBKR states it is not available to customers of IB Singapore; IB Singapore does publish metals CFD pricing — [IBKR Campus: trading spot gold](https://www.interactivebrokers.com/campus/trading-lessons/trading-spot-gold-and-silver-using-ibkrs-tws/); [IBKR SG metals CFD commissions](https://www.interactivebrokers.com.sg/en/pricing/commissions-cfd-metals.php)
- Dukascopy: minimum gold CFD trade is 1 troy ounce (0.01 lot on MT4) — [Dukascopy gold CFD page](https://www.dukascopy.com/swiss/russian/cfd/range-of-markets/gold/)
- Futures at Phillip Nova (MAS-licensed), margin list dated 18 Nov 2026: COMEX Gold GC (100 oz) initial margin US$21,428; E-micro Gold MGC (10 oz, $0.10 tick = $1) US$2,180; 1-Ounce Gold 1OZ (1 oz, $0.25 tick = $0.25) US$219 (S$283) — [Phillip Nova margin list](https://www.phillipnova.com.sg/wp-content/uploads/download/MarginList.pdf)
- Other MGC margin quotes: CITICS Hong Kong, June 2026: 2,516 initial / 2,287 maintenance; Webull: 3,603.60 initial / 3,276 maintenance / 540.54 day margin (reference only) — [CITICS futures margin sheet, June 2026](https://www.citics.com.hk/upload/files/02June2026/FuturesSpecandmargin202606eng.pdf); [Webull futures margin rates](https://www.webull.com/futures-margin-rates)
- 1OZ is 1/100 of GC, cash settled to the GC price, tick $0.25; CME's own examples put margin near $115 with gold at $2,700 and near $390 at $5,000 — [CME 1-Ounce Gold FAQ](https://www.cmegroup.com/articles/faqs/faq-1-oz-gold-futures.html); [CME 1-Ounce Gold contract specs](https://cmegroup.com/markets/metals/precious/1-ounce-gold.contractSpecs.html)
- Phillip Nova's own spot products: "LOCO GD" (100 oz) at 20% margin, and "Gold Direct" (1 oz) at US$3,849 initial and US$770 maintenance margin, i.e. close to fully funded — [Phillip Nova margin list](https://www.phillipnova.com.sg/wp-content/uploads/download/MarginList.pdf)
- Regulatory status: third-party review pages say Pepperstone and IC Markets hold no direct MAS capital markets services licence and that Singapore residents trade under offshore entities; sources conflict for Exness — [TradersUnion: Pepperstone in Singapore](https://tradersunion.com/brokers/forex/view/pepperstone/is-regulated-in-singapore/); [TradersUnion: IC Markets in Singapore](https://tradersunion.com/brokers/forex/view/ic_markets/is-regulated-in-singapore/); [TradersUnion: Exness in Singapore](https://tradersunion.com/brokers/forex/view/exness/is-regulated-in-singapore/)
- On 6 June 2025 access from Singapore to the websites of Octa and XM was blocked after police found they marketed to Singapore customers without licences — [MAS media release, June 2025](https://www.mas.gov.sg/news/media-releases/2025/blocking-of-unregulated-overseas-online-trading-platforms); [Singapore Police Force release](https://www.police.gov.sg/Media-Room/News/20250606_blocking_of_unregulated_overseas_online_trading_platforms)

### Inferences
Summary for a Singapore resident (regulatory column from the sources above; verify each on the MAS Financial Institutions Directory):

| Venue | Smallest gold size | $ per $1 move | Regulated in Singapore? | Works with $100? |
|---|---|---|---|---|
| OANDA Asia Pacific, OANDA platform / v20 | 0.1 unit (taken as 0.1 oz) | $0.10 | Yes (MAS) | Yes, one position (see section 4) |
| OANDA MT5 | 0.001 lot (0.1 oz if 1 lot = 100 oz) | $0.10 | Yes | Yes |
| OANDA MT4 | 0.01 lot = 1 oz | $1.00 | Yes | No (margin $810) |
| IG Asia | 0.05 of a $1/point contract (unconfirmed) | $0.05 | Yes (MAS) | Yes if the 0.05 minimum is current |
| Phillip Nova 1OZ future | 1 oz | $1.00 | Yes | No (US$219 margin) |
| MGC future | 10 oz | $10.00 | Via MAS brokers | No (US$2,180 or more) |
| IBKR Singapore metals CFD | 1 oz | $1.00 | Yes | No (US$2 minimum fee per order) |
| IC Markets / Pepperstone standard or raw | 0.01 lot = 1 oz | $1.00 | Offshore entity (third-party sources) | Technically yes at high leverage; 1% of account per $1 |
| Offshore cent accounts | typically 0.01 cent lot = 0.01 oz | $0.01 | Offshore | Yes |
| XM | not researched | n/a | Website blocked in Singapore since June 2025 | Not an option |

- The existing OANDA adapter and the backtester assume whole-ounce sizing. If OANDA's 0.1-unit minimum is confirmed, both need 0.1-oz granularity. The v20 account instruments endpoint should be read on the live Singapore account to confirm the minimum trade size, unit precision and margin rate for XAU_USD before anything is built on these notes (verification step, not yet done).

### Gaps
- The definition of one OANDA gold unit (1 troy ounce) and whether the v20 API accepts 0.1-unit orders for XAU_USD on a Singapore account were not confirmed from an OANDA document.
- IG's true current minimum for spot gold is unresolved (0.05 of a $1 contract, 1 contract, or 3).
- Official gold contract specifications for Exness Standard Cent, RoboForex ProCent, FBS Cent and XM Micro were not found; whether each accepts Singapore residents was not verified. Saxo Singapore's minimum gold size was not found.
- MAS licence status of Pepperstone, IC Markets and Exness was taken from third-party review sites, not from the MAS directory.

## 4. Leverage and margin in Singapore versus offshore

### Takeaway
The commonly cited "5% (20:1)" does not apply to gold in Singapore: OANDA Asia Pacific, IG Asia, Phillip Nova and moomoo SG all show 20% margin (5:1) for retail gold, matching the 20% "any other CFD" line in MAS's margin schedule; 5% is the FX and index rate. At $4,050 a $100 account can therefore carry at most about $500 of gold (0.12 oz), so 0.01 lot (1 oz, $810 margin) is impossible on a MAS-regulated account and 0.1 oz ($81 margin) is the only size that fits.

### Cited Findings
- MAS margin schedule (Securities and Futures (Margin Requirements for Exempt Financial Institutions) Regulations 2018, Schedule): FX CFDs 5%; index CFDs 5%; equity CFDs 10% for index stocks and 20% for non-index stocks; "any other CFD without stop-loss features" 20%. Accredited, expert and institutional investors are excluded from the definition of customer — [S 666/2018 schedule (mirror of Singapore Statutes Online)](https://littdb.sfo2.cdn.digitaloceanspaces.com/litt/SG/SSOStatutes/subsidiary_legislation/SFA2001-S666-2018.html); [MAS regulation page](https://www.mas.gov.sg/regulation/regulations/securities-and-futures-margin-requirements-for-exempt-financial-institutions-regulations-2018)
- OANDA Asia Pacific retail margin rates (page data read 19 Nov 2026): Gold 20%, every gold cross 20%, silver 20%; EUR/USD and other major FX 5%; most index CFDs 5%; bonds 20%; crypto 50% — [OANDA SG retail margin rates](https://www.oanda.com/sg-en/legal/margin-rates-retail/)
- OANDA's Singapore page says retail margin and maximum leverage are governed by MAS, with leverage "up to 20:1" for retail traders — [OANDA SG spreads and margin](https://www.oanda.com/sg-en/trading/spreads-margin/)
- IG Singapore: retail margin for spot gold (100 oz) 20%, tiered margining applies — [IG SG commodities product details](https://www.ig.com/sg/help-and-support/articles/720379-what-are-ig-s-commodities-cfd-product-details); [IG SG gold trading](https://www.ig.com/sg/commodities/gold-trading)
- moomoo SG's CFD risk fact sheet says initial margin uses the required minimum margin rate of 20% for XAU/USD — [moomoo SG CFD risk fact sheet](https://static.futunn.com/upload/000/Moomoo%20SG%20%20-%20Risk%20Fact%20Sheet%20for%20Contracts%20for%20Difference%20%28EN%29-75422a5978cb81469b0fe5d22169f0a4.pdf)
- Phillip Nova loco London gold (100 oz) and XAU crosses: 20% initial margin, as at 18 Nov 2026 — [Phillip Nova margin list](https://www.phillipnova.com.sg/wp-content/uploads/download/MarginList.pdf)
- MAS raised the retail leveraged FX minimum margin from 2% to 5% from 8 October (2019); accredited, expert and institutional investors kept 2% — [Yahoo Finance Singapore](https://sg.finance.yahoo.com/news/fx-margin-rules-kick-oct-085800068.html)
- For comparison, gold is 20:1 (5%) for retail clients at OANDA under UK FCA rules and was 20:1 (5%) at OANDA Australia (table dated 16 Dec 2021); IBKR cites a 5% regulatory minimum initial margin for retail London Gold CFDs — [OANDA UK spreads and margin](https://www.oanda.com/uk-en/trading/spreads-margin/); [OANDA Australia margin rates 2021](https://www.oanda.com/assets/documents/1065/OAU_Margin_Rate_16_Dec_2021.pdf); [IBKR KB 3642](https://ibkb.interactivebrokers.com/article/3642)
- Offshore: IC Markets' gold specification shows maximum leverage 1:2000 — [IC Markets spec sheet](https://cdn.icmarkets.com/uploads/Commodity+Specification+Sheet.pdf)
- OANDA's Singapore pages carry the warning "Losses can exceed deposits" — [OANDA SG retail margin rates](https://www.oanda.com/sg-en/legal/margin-rates-retail/)
- MAS and the police: most unregulated platforms are based outside Singapore, which raises fraud risk and makes recovering money very difficult; there is "no regulatory safeguard" for investors who use them; absence from the Investor Alert List does not mean a firm is regulated; the public should deal only with entities on the Financial Institutions Directory. In 2017 the police received 142 reports with S$7.8 million lost on unlicensed platforms, up from 40 reports in 2016 — [MAS and CAD warning, 2018](https://www.mas.gov.sg/news/media-releases/2018/cad-and-mas-warn-investors-about-trading-on-unregulated-online-platforms); [MAS media release, June 2025](https://www.mas.gov.sg/news/media-releases/2025/blocking-of-unregulated-overseas-online-trading-platforms)
- The project's backtester "realistic" preset uses margin_percent = 5.0 — [goldlab broker.py](../../gold-backtester/goldlab/engine/broker.py)

### Inferences
What $100 can hold at $4,050/oz (own arithmetic):

| Margin rule | Max notional | Max ounces | Margin for 0.1 oz | Margin for 1 oz (0.01 lot) |
|---|---|---|---|---|
| MAS-regulated gold, 20% (5:1) | $500 | 0.123 oz | $81.00 | $810 (not possible) |
| 5% (20:1), as in UK/EU/Australia; not available for gold in Singapore | $2,000 | 0.49 oz | $20.25 | $202.50 (not possible) |
| Offshore 1:200 | $20,000 | 4.9 oz | $2.03 | $20.25 |
| Offshore 1:500 | $50,000 | 12.3 oz | $0.81 | $8.10 |
| Offshore 1:2000 | $200,000 | 49 oz | $0.20 | $2.03 |

- On a MAS-regulated $100 account exactly one 0.1-oz position fits ($81 margin, $19 free). A second 0.1 oz needs $162. Position size cannot be varied, so risk per trade is set only by stop distance: a $5 stop is $0.50 (0.5% of the account), a $10 stop is $1.00 (1%), a $20 stop is $2.00 (2%). The account would need to fall below about $85 before even the single 0.1-oz position could not be opened at $4,050 (allowing a small buffer), and gold above about $4,900 would also prevent it on $100.
- At IG, if the 0.05 minimum of a $1-per-point contract is current, margin is about $40.50 and two units could be held.
- Singapore's 20% is four times stricter than the 5% that applies to gold in the UK, EU and Australia. The rule protects the account: at 5:1 a 0.1-oz position cannot realistically be liquidated by a normal move (section 5).
- The backtester preset should use 20% margin (and 0.1-oz sizing) to mirror a MAS-regulated $100 account; the earlier project notes' statement that Singapore retail gold leverage is 20:1 should be corrected.
- Offshore leverage makes 1 oz or more possible on $100 but removes the protections MAS describes; these accounts add counterparty and withdrawal risk to trading risk, and a platform can be blocked for Singapore residents with little notice (XM and Octa, June 2025).

### Gaps
- The margin regulation retrieved covers exempt financial institutions (banks, merchant banks, finance companies). The parallel regulation for capital markets services licence holders such as OANDA, IG and Phillip Nova was not retrieved; the 20% gold rate for them is confirmed from the brokers' own pages rather than from the rule text.
- Whether any MAS-licensed broker offers gold as a product falling under the 5% FX line was not found; none of the four checked does.
- Negative-balance policies of offshore brokers and of IG Asia were not verified. OANDA Asia Pacific warns that losses can exceed deposits.
- Saxo Singapore and CMC Markets Singapore gold margin rates were not checked.

## 5. Stop-out mechanics: how fast is a $100 account liquidated?

### Takeaway
At a MAS-regulated broker with 20% margin and 0.1 oz, forced liquidation needs an adverse move of about $595/oz, so the broker's stop-out is irrelevant and the trader's own stop is the only risk control. Offshore at 1:500 to 1:2000, the same $100 can hold 10 to 20 oz, and then a $3 to $6 move, one or two ordinary 5-minute bars, triggers stop-out.

### Cited Findings
- OANDA Asia Pacific (v20 and MT4): the margin requirement is 50% of the margin needed to open the position, recalculated at prevailing prices; a margin call triggers when the margin closeout percentage reaches 50%; at margin closeout all open positions are closed; in fast markets "there may be little or no time to warn you" — [OANDA Asia Pacific margin rules, July 2025](https://www.oanda.com/assets/documents/1982/OAP_Margin_Rules_-_July_2025.pdf)
- OANDA notes a stop-loss is filled at the current OANDA price, which may differ from the stop price when prices gap, for example at market reopen or around news — [OANDA Asia Pacific margin rules, July 2025](https://www.oanda.com/assets/documents/1982/OAP_Margin_Rules_-_July_2025.pdf)
- IC Markets gold: margin call at 100% margin level, stop-out at 50% — [IC Markets spec sheet](https://cdn.icmarkets.com/uploads/Commodity+Specification+Sheet.pdf)
- Exness Standard Cent: margin call 60% and stop-out 0% according to third-party pages; Exness's own blog describes a 0% stop-out level as letting margin level fall to 0% before stop-out — [Issuu: Exness stop-out levels](https://issuu.com/articles/90340657); [Exness blog: stop out protection](https://www.exness.jo/en/blog/exness-stop-out-protection)
- Typical bar sizes for scale: median 5m TR $2.8 (2025 H2) to $6.0 (2026 H1); median 1h TR $15.7 in Sep 2026; 95th percentile 5m TR $8.8 (2025 H2) and $21.5 (2026 H1) — [own computation from Dukascopy samples](../../gold-backtester/data/sample/XAUUSD_5m.csv.gz)

### Inferences
Adverse move that liquidates a $100 account at $4,050/oz (own arithmetic; stop-out when equity falls to the stated share of used margin):

| Setup | Used margin | Stop-out level | Move to liquidation | In ordinary terms |
|---|---|---|---|---|
| MAS 20%, 0.1 oz (OANDA) | $81.00 | 50% ($40.50) | $595/oz | about 8 daily ATRs; not a practical risk |
| Offshore 1:500, 1 oz (0.01 lot) | $8.10 | 50% | $96/oz | 1.3 daily ATRs |
| Offshore 1:500, 5 oz (0.05 lot) | $40.50 | 50% | $16/oz | about one median 1-hour bar |
| Offshore 1:500, 10 oz (0.10 lot) | $81.00 | 50% | $5.95/oz | about two median 5m bars at $3 |
| Offshore 1:1000, 20 oz (0.20 lot) | $81.00 | 50% | $2.98/oz | one median 5m bar |
| Offshore 1:2000, 20 oz (0.20 lot) | $40.50 | 0% | $5.00/oz | under two median 5m bars |

- At 1 oz offshore, the practical problem is not stop-out but risk per trade: every $1 is 1% of the account, so a $5 stop risks 5% and a $10 stop 10%. Section 6 shows what that does to survival.
- A 0% stop-out level means the whole balance can be lost on one position before the broker intervenes, and a gap can take the balance negative unless the broker forgives it.

### Gaps
- IG Asia's close-out level and Saxo's were not retrieved.
- Exness stop-out figures are from third-party pages; no official specification page was read.
- No data found on how often retail gold stop-outs occur or on gap sizes at reopen at specific brokers.

## 6. Mathematics of small-win strategies: break-even win rate, risk of ruin, Kelly, sample size

### Takeaway
With cost c, target T and stop S (all $/oz), the break-even win rate is (S + c) / (T + S): a $3/$3 scalp needs 55% to 60% wins at $0.30 to $0.60 cost, while a $10/$5 trade needs only 35% to 37%. Risking 5% to 10% per trade destroys even a genuine small edge (41% to 79% chance of halving the account within 500 trades at a 52% win rate), and it takes roughly 400 to 2,500 trades to tell a small edge from luck.

### Cited Findings
- Formula and table are own derivations: a winner nets T − c, a loser costs S + c, so expectancy E = p(T − c) − (1 − p)(S + c) and break-even p* = (S + c)/(T + S) — [own calculation, script inputs and outputs recorded in these notes; cost inputs from section 2](../../gold-backtester/goldlab/engine/broker.py)

Break-even win rate after costs:

| Target T | Stop S | Gross R:R | c = 0 | c = $0.30 | c = $0.45 | c = $0.60 | c = $1.00 | Net R:R at $0.45 |
|---|---|---|---|---|---|---|---|---|
| $2 | $1 | 2.0 | 33.3% | 43.3% | 48.3% | 53.3% | 66.7% | 1.07 |
| $2 | $2 | 1.0 | 50.0% | 57.5% | 61.3% | 65.0% | 75.0% | 0.63 |
| $2 | $4 | 0.5 | 66.7% | 71.7% | 74.2% | 76.7% | 83.3% | 0.35 |
| $3 | $1.5 | 2.0 | 33.3% | 40.0% | 43.3% | 46.7% | 55.6% | 1.31 |
| $3 | $3 | 1.0 | 50.0% | 55.0% | 57.5% | 60.0% | 66.7% | 0.74 |
| $3 | $6 | 0.5 | 66.7% | 70.0% | 71.7% | 73.3% | 77.8% | 0.40 |
| $5 | $2.5 | 2.0 | 33.3% | 37.3% | 39.3% | 41.3% | 46.7% | 1.54 |
| $5 | $5 | 1.0 | 50.0% | 53.0% | 54.5% | 56.0% | 60.0% | 0.83 |
| $5 | $10 | 0.5 | 66.7% | 68.7% | 69.7% | 70.7% | 73.3% | 0.44 |
| $10 | $5 | 2.0 | 33.3% | 35.3% | 36.3% | 37.3% | 40.0% | 1.75 |
| $10 | $10 | 1.0 | 50.0% | 51.5% | 52.2% | 53.0% | 55.0% | 0.91 |
| $10 | $20 | 0.5 | 66.7% | 67.7% | 68.2% | 68.7% | 70.0% | 0.47 |

- Kelly criterion and drawdowns: under Thorp's analysis, full-Kelly betting carries a 50% probability of a 50% drawdown; fractional Kelly lowers drawdown probability at a modest cost in growth — [PMC article summarising Thorp's drawdown results](https://pmc.ncbi.nlm.nih.gov/articles/PMC9955835)
- Secondary sources state that half Kelly keeps roughly 75% of the growth at about one quarter of the variance, and that the main reason to bet a fraction is that edges are estimated from limited samples and are usually overestimated — [Tapeboard glossary: Kelly criterion](https://tapeboard.com/glossary/what-is-the-kelly-criterion); [LuxAlgo: Kelly criterion](https://www.luxalgo.com/library/concept/kelly-criterion/)
- Bailey and López de Prado give the probabilistic Sharpe ratio and the minimum track record length needed to reject, at a chosen confidence, that a measured Sharpe ratio is below a threshold; the required length rises as the Sharpe ratio falls and as returns become more negatively skewed — [Journal of Risk: The Sharpe Ratio Efficient Frontier](https://www.risk.net/journal-risk/2223785/sharpe-ratio-efficient-frontier); [R documentation: MinTrackRecord](https://rdrr.io/cran/PerformanceAnalytics/man/MinTrackRecord.html)
- The Deflated Sharpe Ratio corrects a backtest's Sharpe ratio for selection bias from trying many variants and for non-normal returns — [Bailey and López de Prado, SSRN 2460551](https://papers.ssrn.com/abstract=2460551)

### Inferences
All figures below are own calculations (analytic formulas or 20,000-path Monte Carlo over 500 trades, wins and losses independent, fixed fraction of current equity risked per trade).

Kelly fraction, f* = p − (1 − p)/b, where b = net win divided by net loss:

| Win rate p | Net R:R b | Edge per trade | Full Kelly (share of equity risked) | Half Kelly |
|---|---|---|---|---|
| 52% | 1.0 | +0.04R | 4.0% | 2.0% |
| 55% | 1.0 | +0.10R | 10.0% | 5.0% |
| 45% | 1.5 | +0.125R | 8.3% | 4.2% |
| 40% | 2.0 | +0.20R | 10.0% | 5.0% |

Expected log growth per trade for a 52% / 1:1 system is +0.035% at 1% risk, +0.06% at 2%, peaks at +0.08% at 4%, and turns negative at 10% (−0.10%) and 20% (−1.23%). For 55% / 1:1 it is +0.095% at 1%, +0.18% at 2%, +0.375% at 5%, +0.50% at 10% and negative at 20%. Risking more than twice Kelly makes a winning system lose.

Risk of deep drawdown within 500 trades:

| System | Risk per trade | P(account halves) | P(down 80%) | Median final multiple | P(end below start) |
|---|---|---|---|---|---|
| No edge (50%, 1:1) | 1% | 0.2% | 0% | 0.98x | 54% |
| No edge | 2% | 17% | 0.1% | 0.90x | 59% |
| No edge | 5% | 70% | 30% | 0.53x | 72% |
| No edge | 10% | 94% | 81% | 0.08x | 87% |
| Small edge (52%, 1:1, +0.04R) | 1% | 0% | 0% | 1.19x | 22% |
| Small edge | 2% | 3% | 0% | 1.35x | 25% |
| Small edge | 5% | 41% | 9% | 1.46x | 38% |
| Small edge | 10% | 79% | 54% | 0.60x | 59% |
| Good edge (55%, 1:1, +0.10R) | 1% | 0% | 0% | 1.61x | 2% |
| Good edge | 2% | 0.2% | 0% | 2.46x | 2% |
| Good edge | 5% | 11% | 0.5% | 6.5x | 5% |
| Good edge | 10% | 45% | 15% | 12x | 13% |
| Slightly negative (48%, 1:1, −0.04R) | 1% | 3% | 0% | 0.80x | 85% |
| Slightly negative | 2% | 45% | 1% | 0.61x | 87% |
| Slightly negative | 5% | 91% | 62% | 0.20x | 93% |

- Fixed-dollar risk (a minimum lot that cannot be scaled down as the account shrinks) is worse. With 1:1 payoffs the classic gambler's-ruin probability of losing the whole $100 is (q/p)^(100/risk): at a 52% win rate, 45% when risking $10 per trade, 20% at $5, 2% at $2; at 55%, 13% at $10 and 2% at $5; with no edge, ruin is certain eventually. One ounce with a $5 to $10 stop on $100 is exactly the $5 to $10 case.
- Losing streaks are normal: in 200 trades, the chance of at least 7 losses in a row is 54% at a 50% win rate, 91% at 40% and 17% at 60%; at least 10 in a row is 9%, 38% and 1%. At 5% risk, 7 straight losses is a 30% drawdown; at 1% it is 7%.
- Sample size for win rate (95% confidence interval half-width, p near 50%): ±10 points needs about 96 trades, ±5 points 384, ±3 points 1,067, ±2 points 2,401. A 55% result over 100 trades is statistically indistinguishable from 50%.
- Trades needed for expectancy to reach a t-statistic of 2: about 2,500 for a +0.04R edge (52%, 1:1), about 400 for +0.10R (55%, 1:1, or 45% at 1.5:1), about 220 for +0.20R (40% at 2:1), about 100 for 60% at 1:1. Testing many strategy variants raises these thresholds further (deflated Sharpe logic).
- Because costs act like a fixed negative drift of c per trade, a gross profit factor of 1.0 to 1.1 with T near $3 is a net loser: at $0.45 cost a $3/$3 system needs 57.5% wins, and a 55% win rate (gross profit factor 1.22) still loses 0.04R per trade.
- On a MAS-regulated account with fixed 0.1 oz, a $10 stop is 1% risk and a $5 stop 0.5%, inside the range where ruin risk is negligible for any non-negative edge. That is the structural advantage of the 0.1-oz route over 1 oz offshore.

### Gaps
- Thorp's original paper and Vince's work were not retrieved directly; the Kelly drawdown statement comes from a peer-reviewed secondary source, and the "75% of growth at a quarter of the variance" figure from non-academic pages.
- The exact minimum-track-record-length formula could not be confirmed from the paper text.
- The simulations assume independent trades with fixed payoffs; real gold scalps have clustered losses (trend days, news) and variable slippage, which make drawdowns worse than shown.

## 7. Realistic growth and what happens to small accounts

### Takeaway
Broker disclosures and academic studies agree that most retail leveraged traders lose: about 70% to 75% of retail CFD accounts at the brokers considered, 97% of persistent Brazilian day traders, and fewer than 1% of Taiwanese day traders reliably profitable after fees. "$100 to $10,000" is a 100-fold gain that needs about 48 months at a constant 10% a month with no losing months; no credible source was found documenting it as a repeatable outcome.

### Cited Findings
- Retail loss rates from brokers' mandatory risk warnings (primary EU/UK entities, page "updated 2026", individual dates not given): eToro 51%, Saxo 65%, Dukascopy 65%, CMC Markets 69%, IG 70%, Exness 71.67%, FBS 74%, IC Markets 74.32%, XM 75.33%, Pepperstone 75.5%, Plus500 80%; average 71.0% and median 71.7% across 49 brokers, range 51% to 81% — [BrokerRank retail loss rates](https://brokerrank.net/research/retail-loss-rates)
- OANDA: BrokerChooser's OANDA pages carry the warning that 75% of retail CFD accounts lose money; IC Markets is shown at 73.42% on another undated page — [BrokerChooser OANDA](https://brokerchooser.com/fi/broker-reviews/oanda-review/xauusd-spread); [BrokerChooser IC Markets risk warning](https://brokerchooser.com/broker-reviews/ic-markets-review/cfd-risk-warning)
- A UK aggregate reports a 69.9% mean loss rate across 14 FCA-authorised brokers as of April 2026 — [The Investors Centre: UK CFD statistics](https://www.theinvestorscentre.co.uk/trading/statistics/cfd-trading/)
- ESMA found 74% to 89% of retail CFD accounts lost money, with average losses per client of €1,600 to €29,000 (as cited in 2026 coverage) — [PR Newswire, 21 Apr 2026](https://tools.prnewswire.com/en-us/live/20813/release/20260421EN39616)
- IG's Singapore pages give no loss percentage, only a general warning — [IG SG gold trading](https://www.ig.com/sg/commodities/gold-trading)
- Brazil (Chague, De-Losso, Giovannetti): of individuals who day-traded index futures for at least 300 days, 97% lost money; only about 0.4% to 1.1% earned more than a bank teller or the minimum wage (thresholds differ by summary); no evidence of learning with experience — [EconPapers: Day Trading for a Living?](https://econpapers.repec.org/paper/spawpaper/2019wpecon47.htm); [Quantpedia summary](https://quantpedia.com/retail-day-trading-is-an-uphill-battle/)
- Taiwan (Barber, Lee, Liu, Odean; 1992 to 2006): fewer than 1% of day traders predictably and reliably earn positive abnormal returns net of fees; the top 500 earn 37.9 basis points a day after fees; aggregate day-trader performance net of fees was negative in every one of 15 years — [Barber et al., Cross-Section of Speculator Skill](https://faculty.haas.berkeley.edu/odean/papers/day%20traders/Day%20Trading%20Skill%20110523.pdf); [Barber et al., Do Day Traders Rationally Learn](https://faculty.haas.berkeley.edu/odean/papers/day%20traders/day%20trading%20and%20learning%20110217.pdf)
- Prop-firm evaluations as a proxy for small-stake traders: an FPFX Technology analysis of 300,000+ accounts at 10 firms found 14% passed a challenge and about 7% of buyers ever reached a payout; another blended estimate is 12.3%; no major firm publishes audited pass rates — [FundedTrading career guide](https://fundedtrading.com/prop-trading-career-guide/); [BestPropFirms](https://bestpropfirms.us.com/?p=1728); [Track360 statistics 2026](https://track360.io/blog/prop-trading-industry-statistics-2026); [Thor Trade Copier](https://thortradecopier.com/blog/prop-firm-challenge-pass-rate)
- Broker and education blogs (weak evidence) put beginners at about −5% to +2% a month and experienced professionals at about 5% to 10%, with 2% to 3% a month described as achievable only with genuine skill, and note fund managers typically aim for 10% to 20% a year — [FxPro: how much do day traders make](https://fxpro.com/help-section/education/beginners/articles/how-much-do-day-traders-make-forex-salary-breakdown-2026); [DayTradingToolkit: realistic income](https://daytradingtoolkit.com/beginners-guide/realistic-day-trading-income-expectations)

### Inferences
- Compounding $100 at a constant monthly net return (own arithmetic): 2% a month gives $127 after 12 months and takes 233 months to reach $10,000; 5% gives $180 after 12 months and takes 94 months; 10% gives $314 and takes 48 months; 20% gives $892 and takes 25 months; 50% a month would be needed to do it in under a year. None of these allow a losing month.
- In dollars, a $100 account at 0.1 oz earns cents per trade: an edge of +0.10R with a $5 stop is about $0.05 per trade, about $3 to $5 a month at 60 to 100 trades. The account's value is as a cheap, real-money test of the method and of the trader's discipline, not as income. Growth beyond that has to come from adding capital after the method is proven.
- The realistic success criterion for the test phase is "net expectancy above zero after real costs over a few hundred trades with a drawdown inside the backtest's range", not a return target.

### Gaps
- No study was found that relates starting account size to survival or profitability for CFD traders.
- No current loss-rate disclosure specific to OANDA Asia Pacific, IG Asia or other Singapore entities was found; MAS does not appear to require the percentage warning that ESMA and the FCA do.
- Monthly-return figures for "skilled intraday traders" come only from broker and prop-firm marketing content; no audited source was found.
- No documented outcomes of "$100 to $10,000" challenges were found.

## 8. Practical guardrails for intraday gold trading

### Takeaway
The measured data supports hard time filters (no entries from about one hour before the 17:00 New York close to one hour after the 18:00 reopen, and none in the minutes around NFP, CPI and FOMC), and the mathematics supports risk of 1% or less per trade with a daily stop of about three losses. Sources for "what professionals do" are mostly prop-firm rules and trading-education blogs, so the specific numbers are conventions, not evidence.

### Cited Findings
- Spread by clock time (2026): 16:00 to 17:00 New York median $1.16 (95th pct $3.11); first hour after reopen median $3.00 (max $8.09); second hour $1.09; London morning $0.58 to $0.62 — [own computation from Dukascopy 1h sample](../../gold-backtester/data/sample/XAUUSD_1h.csv.gz)
- US data hours (09:00 to 11:00 New York in the 2026 sample) have ordinary median spreads ($0.71 to $0.73) but fat tails: 95th percentile $1.42 to $1.56 and maxima of $4.26 to $6.30 — [own computation from Dukascopy 1h sample](../../gold-backtester/data/sample/XAUUSD_1h.csv.gz)
- Asian lunch (04:00 UTC, 12:00 SGT) has the smallest bars of the main sessions: median 5m TR $3.76 in 2026 against $5.4 to $8.2 at 00:00 to 02:00 UTC, with the spread at 19.5% of the bar — [own computation from Dukascopy 5m sample](../../gold-backtester/data/sample/XAUUSD_5m.csv.gz)
- Stops can fill away from their price at reopen and around news — [OANDA Asia Pacific margin rules, July 2025](https://www.oanda.com/assets/documents/1982/OAP_Margin_Rules_-_July_2025.pdf)
- The "1% rule" caps risk on any single trade at 1% of the account; a common convention sets the daily loss limit at about three times per-trade risk and treats it as a hard stop for the day; some guides add cutting size after reaching half the daily limit and pausing after two consecutive losses (trading-education and prop-firm blogs, illustrative only) — [DayTrading.com: one percent rule](https://www.daytrading.com/one-percent-rule); [DayTradingToolkit: three levels of risk](https://daytradingtoolkit.com/beginners-guide/three-levels-of-risk-management); [MQL5 blog: daily-loss rule sizing](https://www.mql5.com/en/blogs/post/779669); [Pepperstone: 1% rule](https://pepperstone.com/en-gb/analysis/trading-guides/one-percent-rule-in-day-trading/)
- Prop-firm limits as an external benchmark: daily loss limits of about 3% and maximum drawdowns of 3% to 10% of the account (for example a 1-step $10,000 evaluation with a 12% target, 3% daily loss; trailing 6% at another firm), measured on equity including open trades — [CryptoSlate: cheapest prop firms, updated 14 Nov 2026](https://cryptoslate.com/prop-firms/cheapest/); [MQL5 blog: daily-loss rule sizing](https://www.mql5.com/en/blogs/post/779669)
- NFP and CPI are released at 08:30 New York time and FOMC decisions at 14:00 New York time (12:30/13:30 GMT and 18:00/19:00 GMT depending on daylight saving), per the project's earlier notes — [dev.to: XAUUSD sessions](https://dev.to/xauusdrobot/when-does-gold-actually-move-xauusd-trading-sessions-explained-i4a)

### Inferences
Suggested rule set for the report (derived from the measurements and section 6; values are proposals to be backtested, not sourced standards):

1. Time filter: no new entries from 16:00 New York until 19:00 New York (in November 2026: 05:00 to 08:00 SGT). Flatten before 16:45 New York. No positions over the weekend.
2. News filter: no entries from 10 minutes before to 15 minutes after NFP, CPI, PCE and FOMC statements (winter clock: 21:30 SGT for 08:30 releases, 03:00 SGT for FOMC). The repository already has a news blackout configuration to carry this.
3. Spread filter: skip any entry when the live spread exceeds about 1.5 times the session median (for example above $1.00 to $1.10 on a Dukascopy-like feed), and log the spread at every fill.
4. Session choice: London morning and the London/NY overlap (16:00 to 01:00 SGT) give the best ratio of bar size to spread; the Asian morning open (08:00 to 10:00 SGT) is second; avoid 12:00 to 13:00 SGT.
5. Risk per trade: at most 1% of equity (on $100 at 0.1 oz that means a stop no wider than $10/oz); prefer 0.5%.
6. Daily stop: stop for the day at −3R or three consecutive losses; weekly stop at −6R. Cap the number of trades a day (for example 4 to 6) so costs and tilt cannot compound.
7. Minimum reward: target at least 10 times the all-in cost and at least 1.5 times the stop after costs, so the break-even win rate stays near or below 40%.
8. Strategy stop: suspend live trading when the live drawdown exceeds the worst drawdown in the backtest's Monte Carlo 95% band (or 1.5 times the backtest maximum drawdown), or when after 100 or more live trades the net expectancy is below zero while the backtest predicted positive. Do not judge on fewer than about 100 trades, and do not change parameters during the test.
9. Cost stress: accept a backtest only if it stays profitable at 1.5 times and 2 times modelled cost and on the 2025 H2 volatility regime, which is closest to November 2026.

### Gaps
- No authoritative source (regulator, exchange, institutional desk manual or academic study) was found for intraday guardrail values; the conventions cited come from prop-firm rules and education blogs.
- No evidence was found on the optimal maximum number of trades per day or on drawdown-based strategy-retirement rules for gold specifically.
- Tick-level news behaviour of spreads was not measured (see section 1).

## 9. Ways to test with tiny size: demo, OANDA sub-ounce trades, cent accounts, prop-firm challenges

### Takeaway
The cleanest path for a Singapore resident is OANDA practice (free) followed by live 0.1-unit trades at OANDA Asia Pacific, which keeps MAS protection and makes a $10 stop a 1% risk; offshore cent accounts offer finer sizing at the price of regulatory protection, and prop-firm challenges cost $20 to $35 for a $5,000 account but most buyers never reach a payout.

### Cited Findings
- OANDA practice and live accounts share the v20 API, and the project already has an adapter for XAU_USD on practice or live — [goldlab oanda.py](../../gold-backtester/goldlab/live/brokers/oanda.py)
- OANDA Asia Pacific live: gold minimum 0.1 units on the OANDA platform, 20% retail margin, no minimum deposit, margin closeout at 50% of required margin — [OANDA SG help: minimum trade size](https://help.oanda.com/sg/en/faqs/minimum-trade-size.htm); [OANDA SG retail margin rates](https://www.oanda.com/sg-en/legal/margin-rates-retail/); [OANDA Asia Pacific margin rules, July 2025](https://www.oanda.com/assets/documents/1982/OAP_Margin_Rules_-_July_2025.pdf)
- Cent accounts: gold at 1 unit per lot with a 0.01-lot minimum (Fullerton Markets); a cent lot is 0.01 of a standard lot (VT Markets) — [Fullerton Markets cent account specs](https://fullertonmarkets.ladesk.com/725088-What-are-the-contract-specifications-for-Cent-Accounts); [VT Markets: cent accounts](https://www.vtmarkets.com/en-eu/discover/what-is-a-trading-cent-account/)
- MAS and the police say there is no regulatory safeguard for investors on unregulated platforms and that recovering money from overseas platforms is very difficult; XM and Octa were blocked for Singapore residents in June 2025 — [MAS and CAD warning, 2018](https://www.mas.gov.sg/news/media-releases/2018/cad-and-mas-warn-investors-about-trading-on-unregulated-online-platforms); [MAS media release, June 2025](https://www.mas.gov.sg/news/media-releases/2025/blocking-of-unregulated-overseas-online-trading-platforms)
- Prop-firm challenge list prices (updated 14 Nov 2026): Breakout Turbo $5,000 for $20; AquaFunded and FundingPips 2-step $5,000 for $29; FundedNext Stellar Lite $5,000 for $32.99; The5ers High Stakes $5,000 for $35; FTMO starts at €250 for €25,000. Refund terms vary (FTMO and FundedNext return the fee with the first payout; Breakout never refunds). A failed attempt with no reset roughly doubles the outlay — [CryptoSlate: cheapest prop firms](https://cryptoslate.com/prop-firms/cheapest/)
- About 14% of challenge accounts pass and about 7% of buyers ever receive a payout (FPFX data across 10 firms; not audited) — [FundedTrading career guide](https://fundedtrading.com/prop-trading-career-guide/); [BestPropFirms](https://bestpropfirms.us.com/?p=1728)
- 1OZ gold futures need US$219 initial margin at Phillip Nova (18 Nov 2026) — [Phillip Nova margin list](https://www.phillipnova.com.sg/wp-content/uploads/download/MarginList.pdf)

### Inferences
- Demo or practice account. Pros: free, unlimited, same API and price feed as live at OANDA, safe for testing order handling, time filters and logging; can be run for hundreds of trades quickly. Cons: fills are idealised (no real slippage, no requotes, spreads may differ from live at stress moments) and there is no emotional pressure, so it validates the code and the rules but not execution quality or discipline. Use it first, for at least 100 trades or four weeks.
- OANDA live at 0.1 oz. Pros: MAS-licensed counterparty; real fills and real spreads; P&L of $0.10 per $1 move means a $10 stop is 1% of $100; forced liquidation is practically impossible at 5:1; reuses the existing adapter. Cons: only one position and one size fit on $100, so no scaling in or partial exits; gold above about $4,900 or a balance below about $85 blocks the trade; losses can exceed deposits in a gap; profits are cents per trade; the 0.1-unit minimum and unit definition still need confirming on the live account, and MT4 at OANDA requires 1 oz ($810 margin).
- Offshore cent account. Pros: sizes down to about 0.01 oz allow true percentage position sizing and scaling tests on $100; high leverage removes the margin constraint. Cons: no MAS safeguard, withdrawal and counterparty risk, possible blocking of the platform in Singapore, execution on cent servers may differ from the broker's main accounts, and the high leverage invites oversizing. If used at all, keep only money the trader can lose in full and treat results as execution data, not as a custody arrangement.
- Prop-firm challenge. Pros: $20 to $35 buys a $5,000 evaluation where 1 oz with a $5 stop is 0.1% risk, so proper position sizing is possible for less than the $100; loss is capped at the fee. Cons: it is a simulated account with rules (daily loss and drawdown limits, profit targets, time limits, sometimes news and scalping restrictions) that punish variance; most buyers fail; firms are unregulated and gold and Singapore eligibility must be checked per firm; passing tests rule compliance more than edge. Reasonable as a second step after the method is positive on OANDA, not as the first test.
- 1OZ futures become an exchange-traded alternative once the account is about $500 or more (margin US$219), with a $0.25 tick on 1 oz; costs and data fees were not researched.

### Gaps
- Which prop firms allow XAUUSD scalping, their news rules, and whether they accept Singapore residents were not checked.
- Whether OANDA practice spreads for gold match live spreads was not verified.
- Commissions, platform and data fees for 1OZ and MGC at Singapore futures brokers were not researched.
- Official contract specifications and Singapore eligibility for specific cent-account brokers (Exness, RoboForex, FBS) remain unverified.
