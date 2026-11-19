# Mean-reversion, range-fade and liquidity-sweep (reversal-style) intraday methods for gold (XAUUSD) on 5m/15m - rules, evidence, evidence quality

Researched 19 Nov 2026. Conventions used throughout: times are New York (NY) time unless stated; Singapore (SGT) is NY+13h in
US winter time and NY+12h in US summer time. "R" = initial risk (entry-to-stop distance). 0.01 lot = 1 oz, so a $1 move = $1.
Evidence-quality labels: HIGH (independent, cost-inclusive, out-of-sample, reproducible), MEDIUM (independent or
against-interest, reasonable method, gaps), LOW (self-published, short, no costs, not reproducible), MARKETING (seller of a
product, no method). Items marked "(snippet)" come from a search-result summary; the page itself was not opened.
Rule templates under "Inferences" are my own reductions of the published rules to OHLCV logic; they are hypotheses to test, not
sourced claims.

## 1. VWAP mean reversion (fade N-sigma / N-ATR stretches back to session VWAP): what are the rules, what is the evidence, how good is it?

### Takeaway
The only fully specified VWAP-fade rule set is for US index futures (2-sigma band, ADX < 25, rejection bar, target VWAP) and its
performance figures are unverified vendor numbers; the one independent cost-inclusive test that included XAUUSD on M5 found VWAP
fades roughly zero before costs and negative after costs out-of-sample. No independent gold-specific VWAP-fade backtest was found.

### Cited Findings
Rules as published
- CrossTrade (ES/NQ, 5m): session VWAP anchored at session open; fade when price is 2+ standard deviations from VWAP; skip
  the day on major US releases (FOMC, CPI, NFP, ISM), when ADX(14) on 5m > 25, or when the opening-hour range is > 2x its
  20-day average; trigger = rejection candle (pin bar / engulfing / volume spike; their Pine template uses wick > 2x body);
  enter at next bar's open; stop 1x ATR beyond the trigger bar's extreme; target VWAP (optional half off at VWAP, trail rest);
  best windows 10:00-11:30 and 13:30-14:30 ET, avoid 09:30-10:00, FOMC afternoons, Friday after 14:30; RTH only, overnight
  not recommended because "thin volume makes bands noisy". — [CrossTrade](https://crosstrade.io/learn/trading-strategies/vwap-reversion)
- A 5-minute TradingView gold strategy ("The Alchemist") includes a "VWAP Mean-Reversion" engine that "fades stretched moves
  back toward value when trend pressure is light", with no performance figures on the listing (snippet). — [TradingView](https://it.tradingview.com/script/sRxAxNms-The-Alchemist)

Evidence
- CrossTrade's "realistic performance" for the ES rules: win rate 55-65% with filters (about 45% without), average winner
  0.8-1.2x average loser, profit factor 1.2-1.6, 2-5 trades/day in good regimes, often zero on trend days. No period, sample
  size or method is given. It also warns that widening signals to a 1.5-sigma band "triples signals and halves edge" and that a
  $2 round-trip commission is meaningful against $75-150 average ES winners. — [CrossTrade](https://crosstrade.io/learn/trading-strategies/vwap-reversion)
- Pineify tutorial (vendor): VWAP mean reversion on NQ 5m over six months: 142 trades, 58.45% win rate, profit factor 1.78
  (snippet). — [Pineify](https://pineify.app/free-tools/vwap-strategy-tradingview)
- Independent multi-market test (I. Schuch, MQL5 blog, 6 Nov 2026; no product sold; costs = max(1.5x live spread, bar spread)
  + commission, i.e. "0.7 to 1.6 bp per trade"): on M1/M5 data 2020 - Oct 2026 for nine FTMO markets including XAUUSD, the
  best in-sample versions of N-bar breakout, RSI(2) reversion and VWAP fade all "lost out-of-sample on all nine markets, from
  -0.2 to -2.0 bp per trade"; before costs the result was about zero; of 432 scalping rule versions, one was significant
  in-sample and none out-of-sample. Exact VWAP-fade parameters are not published. — [MQL5 blog, Schuch](https://www.mql5.com/en/blogs/post/779464)
- Counter-evidence from the trend side: Zarattini & Aziz's VWAP paper (long above VWAP, short below, QQQ, Jan 2018 - Sep 2023)
  reports +671% net of commissions, Sharpe about 2.1, max drawdown 9.4% (snippet; a QuantConnect reproduction exists). — [Concretum](https://concretumgroup.com/volume-weighted-average-price-vwap-the-holy-grail-for-day-trading-systems/)
- Gold VWAP mean-reversion EAs listed on the MQL5 Market target H4 and show no 5-minute results (snippet). — [MQL5 Market](https://www.mql5.com/en/market/product/189160)

### Inferences
- Evidence quality: MARKETING for the published win-rate/profit-factor figures (CrossTrade, Pineify); MEDIUM for the negative
  Schuch result (independent, cost-inclusive, out-of-sample, but rules and per-market numbers unpublished).
- Cost check: Schuch's cost of 0.7-1.6 bp equals $0.28-0.65/oz at $4,050, i.e. the same as our $0.30-0.50 assumption; his
  out-of-sample result of -0.2 to -2.0 bp is about -$0.08 to -$0.81 per ounce per trade. "About zero before costs" means the
  loss is the cost: there is no gross edge to protect.
- This matches the project's own 5m data (sibling note `own_data_statistics.md`): price > 3 ATR from session VWAP had mean
  forward moves of -$0.84 to +$0.15 over 15-120 minutes, smaller than cost.
- The equity-index result that trading WITH the VWAP side is profitable (Zarattini & Aziz) suggests that, at least on trending
  instruments, the systematic fade is on the wrong side of a real effect; transfer to gold is unproven either way.
- Codeable template (for a falsification test, not a recommendation): session VWAP anchored at 18:00 NY (Globex/spot day
  start) using tick volume, alternative anchors 03:00 NY (London) and 08:20 NY (COMEX open); bands = VWAP +/- 2.0 x rolling
  stdev of (typical price - VWAP) or +/- 2.5 x ATR(14, 5m); trade only when ADX(14, 5m) < 25 and no bar in the last 12 has
  range > 3 ATR; trigger = 5m close back inside the band after a close outside; enter next open; stop = trigger bar extreme
  +/- 1 ATR; target = VWAP; time stop 12 bars; max 2 trades per session; skip 08:25-08:40 and 09:55-10:10 NY (US data).

### Gaps
- No source specifies which VWAP anchor gold traders use; spot XAUUSD has no consolidated volume (brokers supply tick volume),
  and I found no test comparing anchors (18:00 NY day start vs London vs COMEX open) for gold.
- No independent XAUUSD or GC VWAP-fade backtest with full statistics (win rate, profit factor, trades) was found.

## 2. Bollinger Band + RSI fades on 5m/15m (with and without a higher-timeframe trend filter): rules, evidence, quality?

### Takeaway
The standard recipe (close at/below the lower 20,2 band with RSI(14) < 30, exit at the middle band, about 1 ATR stop) is
everywhere, but every positive M5/M15 gold result found is self-published or vendor-supplied, while the independent
cost-inclusive evidence (Schuch's 49,000-variant test; our own RSI(2) 1h result) says the gross edge is near zero and negative
after costs. The long side with a trend filter is the only variant that repeatedly looks less bad.

### Cited Findings
Rules as published
- PineForge (vendor blog, 14 Apr 2026), "Bollinger Band Mean Reversion" for gold: BB(20,2), RSI(14), ATR(14); long when price
  touches or closes below the lower band and RSI < 30; stop = lower band minus 1 ATR(14); exit when price reaches the middle
  band (20 SMA); 15m to 1h; long-only; no performance numbers given for this strategy. — [PineForge](https://getpineforge.com/blog/gold-trading-strategies)
- PineForge "RSI + MA filter": long only when price > 50 EMA and RSI crosses above 30; exit RSI > 70 or price < 50 EMA; 1h;
  no stop stated; no performance numbers. — [PineForge](https://getpineforge.com/blog/gold-trading-strategies)
- TradingView "High Win Rate Mean Reversion Strategy for Gold": long when price touches/crosses the lower Bollinger Band with
  RSI < 30 (snippet; no statistics in the listing). — [TradingView](https://in.tradingview.com/script/BhwmTgik-High-Win-Rate-Mean-Reversion-Strategy-for-Gold)
- Connors RSI(2) adapted to intraday (MQL5 article, 3 Apr 2025, US500 M30 only, not gold): V1 buy RSI2 < 5 with close > 200 SMA,
  exit close > 5 SMA or close < 200 SMA, stop 0.15%; V2 buy when last 3 RSI2 values < 10 with close > 200 SMA, exit close >
  prior candle high, stop 0.15%; V3 buy RSI2 < 5 with close > 50 SMA, exit RSI2 > 70, stop 1%; shorts mirrored. — [MQL5 article 17636](https://www.mql5.com/en/articles/17636)

Evidence
- Schuch (MQL5 blog, Nov 2026): 49,448 backtests on 208 symbols x M15/H1/D1, 13 strategy families x 96 settings including
  "RSI reversion, RSI(2) trend, Bollinger fade and breakout"; first 60% in-sample, last 40% out-of-sample; "Every family lost
  on its median out-of-sample result after costs"; least bad was RSI(14) reversion with median Sharpe -0.15; the best
  in-sample setting was positive out-of-sample only 49% of the time. On M5, RSI(2) reversion lost out-of-sample on all nine
  markets (incl. XAUUSD), -0.2 to -2.0 bp per trade. — [MQL5 blog, Schuch](https://www.mql5.com/en/blogs/post/779464)
- TradingView "XAUUSD 10-Minute Strategy" (MACD + RSI + Bollinger; self-published): 526 trades, 53.99% win rate, profit
  factor 1.44 with a 38-point spread and no slippage/commission; long profit factor 1.96 vs short 1.14 (snippet). — [TradingView](https://in.tradingview.com/script/LxrgnsTO-XAUUSD-10-Minute-Strategy)
- Vendor M5 gold EAs: "RSI Bollinger Reversal Scalper EA" claims profit factor > 1.5, win rate about 58%, max drawdown < 20%
  over 1.5 years, no method (snippet) — [MQL5 Market](https://www.mql5.com/en/market/product/187010); "Pack Invest Mean
  Reversion EA" shows an M5 tester report 2025.11.01 - 2026.04.22 with profit factor 3.75, spread model not stated (snippet) —
  [MQL5 Market](https://www.mql5.com/en/market/product/174110); "ScalpGold" claims profit factor 3.92 on XAUUSD M5 but marks
  spread handling as "Fixed spread demo only" (snippet) — [ScalpGold page](https://leotaby.github.io/scalpgold-sniper-ea/ScalpGold_3D_Viz.html)
- MQL5 forum, BBMA-style XAUUSD EA with profit factor 1.52: author had not forward-tested; repliers warn of curve fitting,
  broker spread differences and live slippage (snippet). — [MQL5 forum](https://www.mql5.com/en/forum/509738/page2)
- Intraday Connors RSI(2) on US500 M30, Jan 2024 - Mar 2025: results shown only as images; no spread/commission modelled; the
  author says V3 has the higher win rate and profit factor but "the drawdown needs to be tackled", and frames the work as
  promising but unproven. — [MQL5 article 17636](https://www.mql5.com/en/articles/17636)
- Daily-bar context (not intraday, not gold-only): Quantpedia (19 Jun 2026) tested trend-filtered pullbacks (price > 200-day MA
  plus 2-5 consecutive down days or RSI(2)/RSI(3) < 10/20) on SPY, EEM, IEF, FXE, GLD, DBC, 2006-2025: per-ETF Sharpe range
  0.11-0.22 and win rates above 55% for the 2-day/1-day-hold set-up; no transaction costs; 600-backtest grid; authors flag the
  analysis as largely AI-produced and needing verification. — [Quantpedia](https://quantpedia.com/?p=44948)
- Backtrex (vendor) Connors RSI(2) on NAS100 daily: strategy +26.9% vs buy-and-hold +528.3% (period not shown in the listing
  I read). — [Backtrex](https://backtrex.com/en/backtests/ict-kill-zone-fvg-gbp-usd)
- Higher-timeframe gold mean reversion (2h bars, stochastic crossover + undisclosed trend filter, paywalled): Apr 2006 - Aug
  2025, win rate 68.95%, profit factor 1.65, CAGR 4.98%, max drawdown 8.8%, spread "0,5 p", out-of-sample from 2021;
  parameters undisclosed. — [Algomatic Trading](https://algomatictrading.substack.com/p/strategy-7-a-mean-reversion-gold)
- QuantifiedStrategies: no gold-specific Bollinger/RSI intraday backtest was found; their RSI work located is on S&P 500
  stocks, SPY and QQQ daily bars (snippets). — [QuantifiedStrategies, RSI drop](https://quantifiedstrategies.substack.com/p/rsi-drop-trading-strategy); [QuantifiedStrategies, RSI on QQQ](https://quantifiedstrategies.substack.com/p/rsi-mean-reversion-trading-strategy)

### Inferences
- Evidence quality: MARKETING for all positive M5/M15 gold figures (profit factor 1.5-3.9 from sellers, fixed spread or
  undisclosed costs, 6-18 month windows inside a bull run); MEDIUM for the negative independent result; LOW-MEDIUM for
  daily-bar ETF evidence, which does not transfer directly (Connors-style edges are equity-index, daily, long-only).
- Our own 1h RSI(2) + 200-SMA result (2,066 trades, 60% wins, profit factor 1.09 before costs, 0.82 after) is fully consistent
  with Schuch's independent finding ("least bad family, still negative after costs"). Moving the same idea down to 5m makes
  the cost share worse, not better, because the average move shrinks while the cost per trade stays the same.
- The long/short asymmetry in the one spread-adjusted gold script (long PF 1.96 vs short 1.14) and in the project's own data
  (buy RSI < 30 in a 1h uptrend PF about 1.24 net; sell RSI > 70 in a downtrend PF 0.66-0.69) says the "edge" is mostly
  trend/drift exposure of the 2025 bull market, not mean reversion. In the 2026 correction a long-only trend filter will often
  have been switched off or pointing the other way, so 2025 results say little about now.
- Codeable template: 15m bars; BB(20,2), RSI(14) (variant: RSI(2) < 5), ATR(14); trend filter = 1h close > 1h 200-SMA (longs
  only) or < (shorts only); entry at next open after a 15m close below the lower band with RSI(14) < 30; stop = entry - 2 x
  ATR; target = 20-SMA at entry time or +2 x ATR, whichever is nearer but not less than 4x the round-trip cost; time stop 8
  bars; one position at a time; no entries 16:00-19:00 NY or within 10 minutes of 08:30/10:00 NY releases.
- If tested, expect win rates of 55-65% with average win about equal to or smaller than average loss; such a profile needs
  the win rate to stay several points above break-even (see section 11), which is exactly what costs remove.

### Gaps
- No independent, reproducible, cost-inclusive M5/M15 Bollinger+RSI backtest on XAUUSD with full statistics was found.
- QuantifiedStrategies/Robot Wealth/Alvarez publish no intraday gold mean-reversion test that I could locate; the
  QuantifiedStrategies "A Gold Strategy" post is paywalled and appears to be a daily trend/momentum rule.
- Schuch does not publish separate numbers for the Bollinger-fade family or for XAUUSD alone.

## 3. Asian-session range fade and the London fake-out ("Judas swing"): rules, evidence, quality?

### Takeaway
On 18 years of Dukascopy gold data the London break of the Asian range reverses about half the time (48.9-50.0%) and the day
closes back inside the Asian range on only 46% of break days, so the unconditional Judas-swing fade is a coin flip; the only
strongly positive gold result (76% win rate) is an unverified forum post with no trade count or costs. Fading inside the Asian
session itself has no quantified evidence at all, only descriptive "Asia is quiet" claims.

### Cited Findings
Rules as published
- ICT-style definitions used in an 18-year gold test: Asia 20:00-00:00 NY, London 02:00-05:00 NY, New York to 16:00; Judas
  swing = "the first move after midnight is the fake one, and the rest of the day goes the opposite way"; Power of Three =
  Asia builds a range, London fakes out of one side, New York moves the other way. — [MQL5 blog, Karakanchev](https://www.mql5.com/en/blogs/post/778873)
- TradingView "Asian Range Liquidity Sweep - Kill Zone Reversal": Asian range 20:00-00:00 NY; London kill zone 02:00-05:00
  (optional 01:30 start), New York kill zone 07:00-10:00; above the Asian range only sell, below only buy; target 1 = opposite
  side of the Asian range; skip high-impact US news days; entries need discretionary elements (higher-timeframe point of
  interest, MSS/CISD, FVG taps) and the author says the model is "mechanical up to the trigger"; expects "zero to four setups a
  day across two pairs"; no backtest ("not a performance claim"). — [TradingView](https://www.tradingview.com/script/1ZcOyqs5-Asian-Range-Liquidity-Sweep-Kill-Zone-Reversal/)
- QuantConnect forum post "Institutional XAUUSD Tokyo range liquidity sweep engine" (H1): map the Tokyo session high/low;
  require a fake breakout at the London open penetrating by 0.7 x ATR; after price closes back inside, trade against the
  breakout; target the range midpoint; stop not stated. — [QuantConnect forum](https://www.quantconnect.com/forum/discussion/20960/institutional-xauusd-tokyo-range-liquidity-sweep-engine-76-wr-1-dd/)
- TakeProfit (vendor guide): London window 02:00-05:00 ET in one section and 02:00-04:00 ET in another; price spikes 20-50
  pips beyond the Asian range high/low; wait for a strong reversal candle 5-15 minutes after the sweep (body > 15 pips on
  EURUSD, "> $1 on XAUUSD"); enter on a retest of the broken Asian-range edge from inside (do not fade the spike itself);
  stop 5-10 pips beyond the spike extreme; target the opposite end of the Asian range (1:1 to 1:2), then the previous day's
  high/low. — [TakeProfit](https://takeprofitapp.com/en/learn/ict-judas-swing-explained)
- For contrast, a continuation rule on the same range (vendor, real ticks Jan 2023 - Sep 2026): Asian range 03:00-08:00 server
  time, skip days with range < 0.30% or > 1.60% of price, stop capped at 0.6% of price; the author notes very narrow ranges
  "produce many false breakouts" and that tight stops inside the range were hit by noise "far too often" (no numbers). — [MQL5 blog](https://www.mql5.com/en/blogs/post/777540)

Evidence
- 18 years of gold (Dukascopy hourly, 2008-2026, 4,844 trading days): London breaks above the Asian range and New York then
  falls: 48.9% of 2,026 days; London breaks below and New York rises: 50.0% of 1,761 days; Judas swing (rest of day opposite
  to the 00:00-05:00 move): 50.0% of 4,841 days vs an unconditional "rest of day up" rate of 50.3%; London breaks the Asian
  high or low and the day closes back inside the range: 46% of 4,268 days (author reads this as about 54% continuation);
  average move in the predicted direction +0.02%, -0.03%, -0.03%. Author's conclusion: not an automatic daily signal; any edge
  must come from untested filters. The author sells a gold EA. — [MQL5 blog, Karakanchev](https://www.mql5.com/en/blogs/post/778873)
- QuantConnect forum claim for the Tokyo-range sweep fade: 76% win rate, "strict 1.0% maximum drawdown" over a 5-year
  backtest; no dates, trade count, profit factor, stop rule or cost model; post marked pending review. — [QuantConnect forum](https://www.quantconnect.com/forum/discussion/20960/institutional-xauusd-tokyo-range-liquidity-sweep-engine-76-wr-1-dd/)
- TakeProfit (vendor, affiliate links to a broker): "65-75% reversal rate when filtered for proper conditions"; a table for
  "250 trading days 2024-2025" with no methodology lists XAUUSD 167 setups, 109 wins, 65.3%, average R:R 1:2.1, profit factor
  2.31 (EURUSD 69.7%, GBPUSD 72.0%, USDJPY 62.8%); filters said to add +5% (daily bias), +6% (their AI bias), +4% (skip news
  days). The page gives no spike-detection, entry or exit rules for the sample and does not report how often London sweeps
  the Asian range at all. — [TakeProfit](https://takeprofitapp.com/en/learn/ict-judas-swing-explained)
- Qualitative session description (vendor blog, no statistics): Tokyo builds a range that London later resolves, Tokyo
  breakouts are often retraced when London arrives, London "often sweeps the Asian range", New York often reverses London's
  initial push. — [MQL5 blog, Nakayama](https://www.mql5.com/en/blogs/post/772224)
- Schuch's SMC sweep test, XAUUSD M15 out-of-sample after costs: -0.051R per trade vs +0.004R for random entry with the same
  stop/target (see section 4). — [MQL5 blog, Schuch](https://www.mql5.com/en/blogs/post/779464)

### Inferences
- Evidence quality: MEDIUM for the coin-flip frequency result (vendor author, but long sample, Dukascopy data, result is against
  the popular narrative and easy to replicate on our own data); MARKETING/LOW for the 76% and 65-75% win-rate claims.
- The TakeProfit table is internally inconsistent: 65.3% winners at an average 2.1R would give a profit factor near 3.9
  (0.653 x 2.1 / 0.347), not the 2.31 printed, and a 65% win rate at 2R is far outside anything an independent test has
  produced (25-52% at 1.5-2R). It should not be used as a base rate.
- The project's own 5m data agrees: London held its first break of the Asian range 50% of the time; 66% of breaks closed back
  inside within three 5m bars but mean follow-through was about zero, and Asian-range size made no difference (sibling
  `own_data_statistics.md`). Two independent data sets, same answer: the sweep itself carries no directional information.
- A "close back inside" happening often (66% within 15 minutes) is not an edge: with a target at the range midpoint and a stop
  beyond the sweep extreme the pay-off is typically < 1R, so a high hit rate is required just to break even (compare the
  63%-win fade that still lost in section 6).
- Codeable template (Judas fade): Asian range = high/low of 20:00-00:00 NY (variant 18:00-03:00 NY); window 02:00-05:00 NY
  (15:00-18:00 SGT winter, 14:00-17:00 SGT summer); sweep = 5m high > Asian high by at least 0.1 x ATR(14, 15m); reclaim = a
  5m close back below the Asian high within 3 bars; enter short at next open; stop = sweep high + 0.25 x ATR(15m); target 1 =
  Asian mid, target 2 = Asian low (test each as a single target); time stop 08:00 NY; max 1 trade/day; skip if Asian range <
  0.30% or > 1.60% of price; mirror for longs. Add a random-entry control (same stop/target/time window) as Schuch did.
- Codeable template (in-Asia range fade): 19:00-01:00 NY only; range = first 2 hours (19:00-21:00); fade a 5m close outside
  the range that closes back inside on the next bar; stop 1 x range height beyond the edge; target range mid; given the
  positive Asia-hours drift documented in section 9, test long-only as well as two-sided.

### Gaps
- No published statistic on fading inside the Asian session for gold (how often an intra-Asia break fails, expectancy).
- No gold study conditions the Judas fade on higher-timeframe trend, range size or day of week with out-of-sample results.
- Edgeful-type "Asian high/low swept in London" frequency tables for gold futures were not found in public posts.

## 4. ICT / "smart money concepts" on gold (sweep-and-reclaim, fair value gaps, Silver Bullet 10:00-11:00 NY, killzones): what reduces to objective rules, and what do independent backtests show?

### Takeaway
Every independent, cost-inclusive mechanisation found loses or is indistinguishable from random entry: a 16-year futures test
including gold (GC) lost in all 92 hour-market combinations with about 25% winners; a 12-symbol test put XAUUSD M15 sweeps at
-0.051R versus +0.004R for random entry; a 10-year FVG kill-zone test had 33.9% wins and profit factor 0.80. The only clearly
positive numbers (XAUUSD profit factor 1.75, 53.7% wins) come from a backtesting vendor that does not state costs. Across
studies the liquidity sweep is the one component that sometimes adds something; "special hours", market-structure-shift and
bias filters do not.

### Cited Findings
Rules as published (objective versions)
- Silver Bullet [GBB] (open TradingView indicator with a 16-year test): windows 03:00-04:00, 10:00-11:00, 14:00-15:00 NY; sweep
  = a candle trades at least one tick through an untouched liquidity level (swing high/low, Asia or London range, previous-day
  high/low, prior-hour range), wick is enough, each level swept once; displacement = 3-candle fair value gap in the opposite
  direction inside the window at/after the sweep, middle-candle body >= 1.0 x ATR(14), gap >= 0.1 x ATR and 2 ticks; entry =
  limit at the near edge of the gap; stop = one tick beyond the sweep extreme; target = nearest untouched opposite liquidity
  level, skip if closer than 1.5R, 2R if none; time stop = window end + 60 minutes (never past 17:00); one trade per window;
  stop-before-target if both hit in one candle. — [TradingView, GoodBadBitcoin](https://id.tradingview.com/script/teL2dDvS-Silver-Bullet-GBB/)
- "ICT Silver Bullet Backtest" script: same three windows; 3-candle FVG formed in the window; entry on retrace to the 50%
  midpoint of the gap; stop at candle/FVG boundary plus buffer; targets fixed 1:1 to 1:4 or 2 x ATR(14) trail activating at
  1.5R; no sweep requirement; no results published. — [TradingView](https://www.tradingview.com/script/SuBXi3p8-ICT-Silver-Bullet-Backtest/)
- Backtrex "liquidity sweep" rules: price exceeds an H1 equal high/low by at least 3 pips; within 2 candles a decisive close
  the other way with body >= 70% of range; enter at the midpoint of the resulting H1/M15 FVG on retest; kill zones only,
  London 02:00-05:00 UTC and New York 07:00-10:00 UTC (as written on the page); stop 5 pips beyond the swept level; target
  nearest opposite liquidity with minimum 1:1.5; 1% risk. — [Backtrex](https://backtrex.com/en/blog/liquidity-sweep-strategy-backtest-results)
- Simplest codeable sweep (Warrior_EA research script): high exceeds the prior N-bar high (N = 20 or 50) by at most ov x
  ATR(14) (ov = 0.25 or 0.5) and the bar closes back below that prior high; enter next bar's open; stop beyond the sweep
  extreme by 0.05 x ATR plus spread; target R x risk (R = 1, 2, 3); max hold 48 H1 bars; loss booked if both hit in one bar;
  significance by shuffling directions (2,000 permutations). — [forge.mql5.io Warrior_EA](https://forge.mql5.io/aron3/Warrior_EA/blame/branch/main/research/test_liquidity.py)
- Backtrex FVG kill-zone test rules (GBP/USD 15m): entries 12:00-15:00 UTC only; first-touch retest of a 15m FVG; 15m close
  above/below 50 EMA as trend filter; 30-pip stop, 60-pip target; 0.02% commission per side. — [Backtrex](https://backtrex.com/en/backtests/ict-kill-zone-fvg-gbp-usd)

Independent or against-interest evidence
- Silver Bullet [GBB], Sierra Chart 1-minute futures data 2011-2026 on ES, NQ, YM and GC across all 23 hours, costs = 2 ticks
  slippage + $4.50 commission per round trip: "About one trade in four wins", roughly 73% of filled trades hit the stop;
  after costs the model "lost money in all 92 hour-market combinations"; before costs flat to negative; 70-76% of armed
  setups whose limit never filled would have reached target (filled orders tend to be the losers); the Silver Bullet hours
  were no better than equally active hours; "the one exception, gold's 10:00 hour, lost money and was not confirmed".
  Conclusion: "with these rules, the Silver Bullet hours are not special, and the model is not a profitable strategy on its
  own." — [TradingView, GoodBadBitcoin](https://id.tradingview.com/script/teL2dDvS-Silver-Bullet-GBB/)
- Schuch SMC tests (XAUUSD, EURUSD, GBPUSD, Volatility 75, Step Index on M5/M15; stop at structure capped 0.5-3 ATR, 2R
  target, time stop; control = random entry with same stop/target/costs). Out-of-sample expectancy per trade, sweep vs random:
  XAUUSD M15 -0.051R vs +0.004R; EURUSD M15 -0.257 vs -0.182; GBPUSD M15 -0.151 vs -0.103; EURUSD M5 -0.299 vs -0.317. Across
  50 strategy/market tests 21 beat random (25 expected by chance), none significant (highest t 1.04); a rerun with wider
  swings and a 1:3 target "gave the same picture". — [MQL5 blog, Schuch](https://www.mql5.com/en/blogs/post/779464)
- "I backtested 25,000 ICT Silver Bullet trades" (third-party summary of a video by "Adam S."; NQ and ES, 16 years of
  1-minute data, costs included, 2-year holdout): of 25,000 sampled configurations, 9,481 had 100+ trades, 6,190 were
  profitable after costs, 1,614 survived a luck correction and 420 (1.7%) survived a cold run on ES; most profitable versions
  centred on a 52% win rate, top performers 34-48%; the few near 70% took small profits about 20 times a year; the 10:00
  window "trended slightly negative" and the special hours did no better than the rest; the liquidity sweep was "the only
  rule that consistently added edge"; the 15-minute bias and market-structure-shift rules "caused performance to crater";
  caveats: bull-market backdrop and paper fills. — [gist.ly summary](https://gist.ly/youtube-summarizer/i-backtested-25000-ict-silver-bullet-trades)
- Backtrex FVG kill-zone test, GBP/USD 15m, 2 Oct 2016 - 1 Oct 2026: 1,009 trades, win rate 33.89%, profit factor 0.80, total
  return -30.3%, max drawdown -33.5%, every calendar year negative, longest losing streak 14. Same page: GBP/USD 1h order
  block -15.3%, 1h previous-day high/low breakout -65.6%, 15m London breakout -60%. — [Backtrex](https://backtrex.com/en/backtests/ict-kill-zone-fvg-gbp-usd)
- Offbeat Forex mechanical ICT bot (EURUSD 15m, 17 Jul 2025 - 17 Jul 2026, killzone sweep-reversal + displacement-FVG, no
  spread/commission modelled): 125 trades, 29.6% wins, average winner +1.63R, profit factor 0.81, -15.1R; "a naive
  mechanization of ICT loses money". An AI-discretionary run over two months made +27.6R on 47 trades (40.4% wins, PF 1.99);
  only higher-timeframe bias had a confidence interval that "barely" cleared zero; author: 90%-win-rate ICT accounts are
  "marketing, not math". — [Offbeat Forex](https://offbeatforex.com/is-ict-strategy-profitable/)
- Warrior_EA N-bar sweep script (H1; EURUSD, USDJPY, XAUUSD, SP500): commit message reports 19 of 24 configs cleared the
  family-wise significance bar on EURUSD and USDJPY; R = 1 configs were negative, R = 2 and 3 positive; split-half expectancy
  for the best EURUSD configs only +0.013/+0.042R and +0.014/+0.034R; the author calls it "a lead, not a system". — [forge.mql5.io Warrior_EA](https://forge.mql5.io/aron3/Warrior_EA/blame/branch/main/research/test_liquidity.py)

Vendor claims
- Backtrex liquidity-sweep blog (2019-2024): kill zones only 1,247 trades, 53.2% wins, profit factor 1.68, max drawdown
  -14.3%; all sessions 3,891 trades, 47.1%, PF 1.21, -26.7%; XAUUSD H1 504 trades, 53.7% wins, PF 1.75, +61.2%; 2022 was a
  losing year (-8.1%, 46.5% wins) attributed to "false sweeps during high macro volatility"; in-sample PF 1.66, out-of-sample
  PF 1.71; kill-zone filter +6 points of win rate, 1:1.5 minimum reward:risk +0.31 PF. Costs are not stated, and the page's
  yearly trade counts (987 / 260) do not reconcile with its in/out-of-sample counts (956 / 291). — [Backtrex](https://backtrex.com/en/blog/liquidity-sweep-strategy-backtest-results)
- TakeProfit guide: 55-70% win rate on "properly filtered" Silver Bullet setups, e.g. 60.4% EURUSD and 63.6% NAS100 in
  2024-2025; page promotes its own product (snippet). — [TakeProfit](https://takeprofitapp.com/en/learn/ict-silver-bullet-strategy)

### Inferences
- Evidence quality: MEDIUM for the three negative tests (GBB, Schuch, Backtrex FVG) - independent or against the publisher's
  interest, cost-inclusive, long samples, but blog/indicator-page publications without downloadable trade lists; LOW-MEDIUM
  for the 25,000-configuration study (second-hand summary, index futures only); MARKETING for Backtrex's positive sweep
  blog and TakeProfit. No HIGH-quality source exists.
- The Backtrex XAUUSD figures imply an average win of about 1.5x the average loss and about +0.35R per trade
  (PF x (1-p)/p = 1.75 x 0.463/0.537 = 1.51; 0.537 x 1.51 - 0.463). That is irreconcilable with Schuch's -0.051R on XAUUSD
  M15; the differences are costs (unstated vs. 1.5x spread), period (2019-2024 vs. to Oct 2026) and level definition (H1
  equal highs vs. swing structure). Treat the vendor figure as an upper bound that has not survived independent testing.
- Realistic win rates for mechanised sweep/FVG entries with 1.5-2R targets are 25-52%, not 70-90%. A trader who wants "many
  small wins" will not get them from this family without shrinking the target below 1R, which section 6 shows loses.
- The repeated finding that unfilled limit setups would have won (GBB: 70-76%) is adverse selection: retrace-entry limits are
  filled mostly when the move is failing. A market entry on the reclaim close avoids that but pays a wider stop.
- If a sweep rule is tested, the Warrior_EA formulation is the cleanest OHLCV version. Template for gold: levels = previous-day
  high/low, Asian range high/low (20:00-00:00 NY), prior-hour high/low; sweep = 15m high exceeds level by <= 0.5 x ATR(14)
  and closes back below; enter next open; stop = sweep high + 0.1 x ATR; target 2R; time stop 16 bars; windows 02:00-05:00 and
  07:00-11:00 NY; one trade per level per day; require the random-entry control.

### Gaps
- No independent XAUUSD spot test of the complete Silver Bullet sequence with a published trade list; GBB's GC result is
  summarised on an indicator page without per-market tables in the text I could read.
- The original video behind the 25,000-configuration summary was not viewed; channel name and exact FVG/stop rules are
  unconfirmed.
- No r/algotrading or GitHub repository with a reproducible gold SMC backtest and statistics was located.

## 5. Previous-day high/low and round-number ($10/$50/$100) rejection scalps: rules, evidence, quality?

### Takeaway
Academic work finds statistical "psychological barrier" effects at round gold prices (numbers ending in 0 and 00), but nobody
has published a tested rule showing that fading those levels, or the previous day's high/low, makes money intraday after costs;
the closest tests (generic sweep-and-reclaim of prior extremes) are negative or negligible on gold.

### Cited Findings
- Aggarwal & Lucey (2007, Review of Financial Economics) examined psychological barriers in daily and intraday gold series and
  report that round-number levels affect the conditional mean and variance of gold returns near them (snippet; pre-2022
  source). — [EconPapers](https://econpapers.repec.org/RePEc:wly:revfec:v:16:y:2007:i:2:p:217-230)
- O'Connor & Lucey (2016, Finance Research Letters), London AM/PM fixes 1975-2015: "support for barriers at numbers ending in
  0 and 00 for gold", none for silver (snippet; pre-2022 source). — [UCC research portal](https://research.ucc.ie/en/publications/mind-the-gap-psychological-barriers-in-gold-and-silver-prices/)
- Rule definition in common use: a wick through the prior day's high or low followed by a 15m close back inside the range is
  treated as a stop-hunt rather than a breakout (snippet). — [LuxAlgo library](https://www.luxalgo.com/library/indicator/0uAmOgGD-pdh-pdl-liquidity-reversal-15m-confirmed-close)
- The GBB Silver Bullet test includes previous-day high/low among its sweep levels and lost after costs on GC and the index
  futures in all hour-market combinations. — [TradingView, GoodBadBitcoin](https://id.tradingview.com/script/teL2dDvS-Silver-Bullet-GBB/)
- Breakout side of the same level (GBP/USD 1h previous-day high/low breakout, 10 years): -65.6%. — [Backtrex](https://backtrex.com/en/backtests/ict-kill-zone-fvg-gbp-usd)
- Generic prior-extreme sweep (N-bar high/low, H1): significant only on EURUSD/USDJPY, with expectancy of +0.01 to +0.04R at a
  3R target; XAUUSD not among the supported results. — [forge.mql5.io Warrior_EA](https://forge.mql5.io/aron3/Warrior_EA/blame/branch/main/research/test_liquidity.py)
- Schuch: breakout and fade are mirror images, so "the two sides together cost about two spreads"; a level where the breakout
  loses does not imply the fade wins. — [MQL5 blog, Schuch](https://www.mql5.com/en/blogs/post/779464)

### Inferences
- Evidence quality: HIGH for the existence of round-number clustering/barrier effects in gold (peer-reviewed, though old and
  based on fixes and daily data); none (no evidence) for a tradable 5m/15m rejection rule.
- A barrier effect in return moments does not tell us the sign or size of a tradable reversal. At $4,000+ gold a $10 level
  occurs every 0.25% of price, i.e. several are crossed inside one daily ATR of about $75, so "$10 levels" are effectively
  noise; only $50 and $100 levels are sparse enough to be distinct events.
- The project's own 5m data (sibling note) found previous-day-high sweep-and-reclaim shorts and previous-day-low reclaim longs
  had mean forward moves between -$2.18 and +$0.14 over 15-120 minutes: nothing after costs.
- Codeable template: level L in {previous-day high, previous-day low, nearest multiple of $50}; signal = 15m bar trades
  through L by <= 0.5 x ATR(14) and closes back on the origin side; enter next open; stop = bar extreme +/- 0.1 x ATR; target
  2R (variant: 1R); time stop 12 bars; first touch of each level per day only; 02:00-11:00 NY.

### Gaps
- No intraday study of reversal frequency conditional on proximity to gold round numbers was found, and nothing post-2016.
- No published gold statistic of the "previous-day high swept and closed back inside X% of the time" type.

## 6. Opening-range fade / failed-breakout reversal: rules, evidence, quality?

### Takeaway
The best direct evidence is negative: across 12 symbols and 91,943 trades per variant (May 2025 - Oct 2026) every range-fade
variant lost after costs, including one that won 63.1% of the time; and for gold futures specifically the first-hour New York
range is broken on only one side about 79% of the time, which works against fading a break to the far side.

### Cited Findings
- Schuch breakout/fade test: 12 FTMO symbols, May 2025 - Oct 2026, range = previous 1-hour candle, trades replayed on M5 with
  each bar's median spread, 91,943 trades per variant. Fade with stop 1 range and target the middle: 63.1% wins, -0.051R, 0 of
  12 symbols positive. Fade with stop 1 range, target other edge: 49.3%, -0.044R, 1 of 12. Fade with stop 0.25 range, target
  1R: 45%, -0.24R, 0 of 12. Breakout with stop at other edge, target 1R: 48.6%, -0.057R; breakout with stop at middle: 43.6%,
  -0.211R. The 63% fade lost because "the losses were larger than the wins". Calibrating 8,064 filter/exit combinations per
  market on the first 60% of data "found nothing that held across markets". — [MQL5 blog, Schuch](https://www.mql5.com/en/blogs/post/779464)
- Edgeful (vendor stats), GC initial balance 09:30-10:30 ET, last 6 months: single break 79.23%, double break 13.08%, no break
  7.69%; "nearly 8 out of 10 times" GC breaks one side and does not come back to test the other. Their continuation algo
  (1% retracement entry after the break, stop at a 60% retrace into the range, targets 0.25x and 0.5x the range, 5m chart)
  claims 65.76% wins and profit factor 1.935 over 12 months on a TradingView backtest; trade count and costs not stated. — [Edgeful](https://www.edgeful.com/blog/posts/gc-trading-strategy-initial-balance-algo)
- Edgeful blog posts report double-break frequencies that vary by instrument and drift over time: ES nearly two-thirds over a
  recent 6 months, YM 48%, and ES falling from 81% in Q1 2024 to 50% in Q4 2024 (snippets; exact post attribution not
  verified). — [Edgeful ORB post](https://www.edgeful.com/blog/posts/the-opening-range-breakout-orb-trading-strategy); [Edgeful, changing conditions](https://www.edgeful.com/blog/posts/adapting-to-changing-market-conditions); [Edgeful YM IB](https://www.edgeful.com/blog/posts/ym-initial-balance-strategy)
- Edgeful: over the last 6 months GC did not make a new high during the last hour of trading 85% of the time (snippet). — [Edgeful power hour](https://www.edgeful.com/blog/posts/power-hour-breakout-trading-strategy)
- Schuch: opening-range breakout was weak everywhere (best US100 30-minute range +3.9 bp, t 1.35) and the London 4 pm fix
  fade on 21 FX pairs returned -2.5 bp, "negative in both halves on every pair". — [MQL5 blog, Schuch](https://www.mql5.com/en/blogs/post/779464)

### Inferences
- Evidence quality: MEDIUM for Schuch's negative fade table (independent, large sample, costs included; range definition is
  the prior 1h candle rather than a session opening range; 18-month window); LOW-MEDIUM for Edgeful frequencies (vendor, short
  rolling windows, unstable through time).
- Arithmetic check on the 63.1% fade: target = half the range (0.5R) and stop = one range (1R) gives a gross break-even win
  rate of 66.7%; 0.631 x 0.5 - 0.369 x 1 = -0.054R, almost exactly the reported -0.051R. So the fade had no edge even before
  costs: a 63% hit rate is simply what a random walk delivers for a target half as far away as the stop. This is the central
  warning for a trader attracted to high win rates.
- The tight-stop fade (-0.24R) shows the second trap: at a 0.25-range stop the cost is about 0.14R per trade, versus about
  0.03R for the 1-range stop (gross results -0.10R and -0.014R respectively by the same arithmetic).
- Gold's low double-break rate at the New York first hour (13%) means a "failed breakout, trade to the other side" needs the
  rare case; a fade that only targets the range middle is the 63%-win/negative-expectancy structure above.
- Codeable template: opening range = 09:30-10:00 NY (variants 08:20-08:35 COMEX open, 03:00-03:30 London); failed breakout = a
  5m close outside the range followed within 3 bars by a 5m close back inside; enter next open toward the opposite side; stop
  = extreme of the failed excursion + 0.1 x ATR(14, 15m); target = opposite edge (>= 1.5R, else skip); time stop 12:00 NY; one
  trade per day; skip days with US data at 08:30/10:00 if the range spans the release.

### Gaps
- No gold-specific statistic for "break of the opening range closes back inside" or the expectancy of fading it.
- Edgeful's GC ORB (5/15/30-minute) double-break rates are behind their product; only the 60-minute IB figure is public.

## 7. Overextension fades (N consecutive candles, large-bar exhaustion, distance from EMA in ATR units, intraday RSI divergence): rules, evidence, quality?

### Takeaway
There is almost no quantified evidence for these on intraday gold. The independent multi-market test puts all its
reversion-style M5 scalps at about zero before costs and negative after; the one positive gold result is a self-reported
1-minute z-score bot whose live win rate is only 25%, i.e. it is not a high-win-rate method at all.

### Cited Findings
- Schuch: among 13 families tested out-of-sample after costs, every family's median lost; "streak continuation" was the worst
  (median Sharpe -1.31) and RSI(14) reversion the least bad (-0.15); intraday momentum was negative out-of-sample on 8 of 9
  markets. — [MQL5 blog, Schuch](https://www.mql5.com/en/blogs/post/779464)
- falsifylab "lyra-gold" (Substack, 20 Jun 2026; self-reported): gold futures, 1-minute bars, entry when price deviates beyond
  a z-score threshold from a rolling mean, exit at the rolling mean or a time stop, volatility-adaptive stop; backtest profit
  factor about 2.15 with max drawdown < 2%; live since a sizing fix: 277 trades, 25.3% win rate, profit factor 2.42, max
  drawdown 2.05%; window and threshold undisclosed; the author concedes the fold test "is still in-sample optimization across
  folds, not true out of sample" and that the bot is not designed for trend days. — [falsifylab](https://falsifylab.substack.com/p/strategy-deep-dive-lyra-gold)
- Quantpedia (daily bars, six ETFs incl. GLD, no costs): the number of consecutive down days is the most influential
  parameter; going from 2 to 3 down days lowers Sharpe from 0.95 to 0.78 and halves trade count (2,152 to 1,030); performance
  "degrades sharply" beyond 3; "Commodities and currencies have shorter mean-reversion windows than equities" (offered as an
  explanation, not tested). — [Quantpedia](https://quantpedia.com/?p=44948)
- Vendor heuristic (no statistics): with today's range under about 40% of ADR(20) the day has room to continue; at about
  90-130% it is "mostly spent, with mean reversion odds rising"; beyond 130% only fresh news extends it; big news days reach
  about 200% of ADR. — [MQL5 blog, Nakayama](https://www.mql5.com/en/blogs/post/772224)
- Vendor view on gold mean reversion generally: it earns steadily in long ranges and then "gives back years of small gains in
  weeks" when a trend starts; pullback entries are hit by "news spikes, weekend gaps and liquidity holes" (no numbers). — [MQL5 blog, Sakamoto](https://www.mql5.com/en/blogs/post/774959)

### Inferences
- Evidence quality: LOW throughout (no independent gold test of consecutive-candle, large-bar or EMA-distance fades; the
  lyra-gold numbers are unaudited, parameters hidden, 277 trades).
- "Streak continuation" being the worst family does not make streak reversal profitable: as with breakout/fade, both sides pay
  the spread, and the reversion families also had negative medians.
- The project's own 5m data (sibling note): after big bars (true range > 3 ATR) price drifted up on average whether the bar
  was up or down - selling after big down bars lost $0.55-2.62 gross over 15-120 minutes (so fading them by buying gained
  that much), while fading big up bars lost $0.09-3.27. That is the 2025 bull-market drift again, not a symmetric exhaustion
  effect, and the buy-side gain is under or near the all-in cost for the first 30 minutes.
- Codeable templates: (a) streak fade - after N = 4 consecutive 5m closes in one direction with cumulative move >= 2.5 x
  ATR(14), enter against at next open, stop 1.5 x ATR, target 1.5 x ATR, time stop 6 bars; (b) EMA-distance fade - |close -
  EMA(50, 5m)| >= 3 x ATR(14) and first bar that closes back toward the EMA, stop beyond the extreme + 0.25 ATR, target
  EMA(20); (c) ADR exhaustion filter - allow fades only when the day's range >= 100% of ADR(20) and time is after 11:00 NY;
  (d) RSI divergence - second 15m swing low lower than the first while RSI(14) is higher, enter on close above the high of
  the divergence bar, stop below the swing low, target 2R. All four need the random-entry control.

### Gaps
- No published intraday gold statistics for consecutive-candle exhaustion, large-bar reversal, EMA-distance fades or RSI
  divergence (win rate, expectancy, costs) from any source, independent or vendor.
- The ADR-exhaustion heuristic has never been quantified in the sources found.

## 8. Grid / martingale / averaging-down gold "scalper" EAs: why do the track records look good until they fail, and what blow-ups are documented?

### Takeaway
These systems never realise a loss until a basket recovers, so they show 90-100% winning trades and zero losing months while
carrying open losses that one directional move converts into a margin call; documented cases include a default-settings gold
grid EA taking a $1,000 account to $57 on roughly a 1% gold move, a grid EA with 0 losing months in 89 and a 91% relative
equity drawdown, and a vendor survey in which about one in five popular gold EAs blew up over 2015-2026.

### Cited Findings
Mechanism
- Grid and martingale EAs do not close losers; they "add another one" as price moves against them and close the basket when
  it recovers; warning signs: no stop loss on orders, several same-direction trades on one symbol, inputs named step /
  distance / lot multiplier / max orders / recovery (multiplier > 1.0 = martingale), win rate above 90% with average loss many
  times the average win, balance drawdown much smaller than equity drawdown, drawdown protection off by default. — [MQL5 blog, Arribas Lopez (vendor of non-grid EAs)](https://www.mql5.com/en/blogs/post/778258)
- Illustrative arithmetic for gold, 0.01 lot start, $5 steps: after 10 steps ($50 adverse) a flat grid holds 0.10 lot with $275
  floating loss, a 2x martingale holds 10.23 lots with $10,180 floating loss; a 90%-win strategy with $10 average win and
  $120 average loss has expectancy -$3 per trade. — [MQL5 blog, Arribas Lopez](https://www.mql5.com/en/blogs/post/778258)
- Forum view: martingale gains "disguise, counter, and hide the losing trades", which is why such EAs backtest best; grids are
  quick to code and "simply assume that markets range most of the time"; "most EAs that show amazing backtests on gold rely
  on some form of martingale or grid logic" (snippets). — [MQL5 forum](https://www.mql5.com/en/forum/502291)
- Myfxbook community thread: most martingale/grid systems are "destined to blow up accounts or result in unrecoverable
  drawdown"; red flags are a short account life and equity curves that only go up (snippet). — [Myfxbook community](https://www.myfxbook.com/community/new-traders/fallacy-martingalegrid-systems/3130769,1)
- EA Gold Stuff review: lot multiplication with each added position typically 1.5x the previous; extended one-way moves can
  trigger cascading losses (snippet). — [NYC Servers](https://newyorkcityservers.com/blog/ea-gold-stuff-review)

Documented failures and stress events
- "Quantum Queen X" (gold grid EA) on default settings: a new $1,000 account fell to $57 on "a drop of about one percent" in
  gold, after 1,589 winning baskets in a row; date not stated. — [MQL5 blog, Arribas Lopez](https://www.mql5.com/en/blogs/post/778258)
- "GOLD KING" (grid-type EA, the seller's own published backtest, M1, 2019-2026): 0 losing months out of 89 and +6,177.7%, with
  maximal equity drawdown 42.8% (91.27% in relative terms per a 26 Oct 2026 correction) and a longest single holding time of
  2,608 hours (about 108 days). — [MQL5 blog, Sakamoto](https://www.mql5.com/en/blogs/post/777882)
- 43 popular paid gold EAs (free demos, factory defaults, MetaQuotes XAUUSD data Jan 2015 - Jul 2026, $10,000, 1:500): 19% of
  measurable EAs blew up with equity drawdowns of 60-102%; the most expensive ($1,999, 100+ reviews) had profit factor 0.23 and
  a 99% drawdown; every account-killer "had strong recent months and one severe drawdown earlier in the history"; review
  counts were not predictive; the 1-minute OHLC model flatters tight-target scalpers. Author sells competing EAs. — [MQL5 blog, Sakamoto](https://www.mql5.com/en/blogs/post/773167)
- 30 January 2026: spot gold fell about 9.5-9.8% (roughly $520-540) in one day from an all-time high near $5,595 the day
  before, described via Reuters as the largest one-day percentage fall since 1983; CME raised gold margins the same day and
  selling continued on Monday 2 February. Straight-line arithmetic for a $10,000 account starting at 0.01 lot: a $10-step grid
  is wiped by a move of about $442 (flat lots), $199 (1.2x), $126 (1.5x) or $90 (2.0x); a $20-step grid by $622, $330, $221 or
  $160; "any lot multiplier wiped the account after a 2-6% move". The author notes this is arithmetic, not a test of a real EA. — [MQL5 blog, Lan Tran Hoang](https://www.mql5.com/en/blogs/post/778166)
- Schuch's tournament: martingale grids were positive out-of-sample in 39% of cases. — [MQL5 blog, Schuch](https://www.mql5.com/en/blogs/post/779464)
- Top-selling gold EAs with high win rates and large stops (CyNera, AI Golden Jet Fighter GTX, AI Gen XII; Dec 2024): one
  loss can erase "6, 7, or even 10" prior wins; drawdowns "potentially over 50%" at large lot sizes; praise in early reviews
  followed by reports of significant losses. Author sells other EAs; pre-2025 source. — [MQL5 blog, Kortarla](https://mql5.com/en/blogs/post/760211)
- Forum dissent: some averaging systems have been "constantly making profits since years" and a hard equity stop that
  triggers "less than 2 times in a year" can leave the system profitable; no verified records were posted; a "90% chance of
  blowing your account" figure in the thread title is unsourced. — [MQL5 forum](https://www.mql5.com/en/forum/512226)
- Regulators: France's AMF has warned the public about fraudulent investment offers made through trading robots and about
  unauthorised automated-forex offers; the UK FCA has warned about an unlicensed gold (XAUUSD) trading bot site (snippets). — [AMF](https://www.amf-france.org/en/news-publications/news-releases/amf-warns-public-about-fraudulent-investment-offers-through-trading-robots); [anwalt24 on FCA warning](https://www.anwalt24.de/fachartikel/kapitalmarktrecht/62557)

### Inferences
- Evidence quality: the arithmetic is verifiable (HIGH as logic); the case studies are LOW-MEDIUM (vendor-authored blog posts
  with competing products, but describing reproducible strategy-tester runs); no regulator or journalist account of a specific
  named gold grid EA collapse with audited figures was found.
- Why the record looks good: realised P&L only records closed baskets, so win rate, monthly returns and balance curve exclude
  the open loss; a public track record is also survivorship-filtered because wiped accounts are deleted or restarted.
- For a $100 account the arithmetic is far harsher than the $10,000 examples: a flat grid adding 0.01 lot every $5 has a
  floating loss of $5 x N(N+1)/2 after N steps, i.e. $105 after 6 steps - the whole account is gone on a $30 adverse move,
  less than half of one average daily range (about $75), before margin stop-out is even considered. Any lot multiplier makes
  it faster.
- The same negative-skew logic applies to any "no stop, wait for it to come back" discretionary averaging, and to
  single-position scalpers with a stop many times the target.

### Gaps
- No Myfxbook/FXBlue-verified gold grid account with a dated collapse and audited numbers was retrieved; the named cases are
  strategy-tester or author-reported.
- No Monetary Authority of Singapore or CFTC advisory specific to gold EAs was found in this search.

## 9. Which sessions and hours favour mean reversion in gold versus trend, and what statistics exist?

### Takeaway
There is no published statistical proof that any gold session is mean-reverting enough to trade; what is documented is
directional drift by session (Asia hours up, US hours carrying the 2026 sell-off), a coin-flip London reaction to the Asian
range, one-sided breaks of the New York first-hour range, and a spread that doubles around the 17:00 NY rollover.

### Cited Findings
- StoneX (David Scutt, 16 Nov 2026): gold's cumulative return by session, since the start of September / 2026 year-to-date:
  Asia (09:00 Tokyo to the London open) +2.7% / +3.4%; Europe (08:00 London to 08:00 New York) -2.5% / -0.9%; US (08:00-17:00
  New York) -12.2% / -28.1%; "Asia buys the dip, Europe and particularly the US sell the rip"; the pattern "hasn't been
  consistent every month". — [StoneX](https://www.stonex.com/en-gb/news-and-analysis/gold-outlook-asia-buys-the-dip-us-hammers-the-rip-2026-11-16/)
- Schuch: the only gold rule that survived his cost-inclusive screen is a time-of-day drift, not a fade: buy XAUUSD at 18:00
  NY, sell at 03:00 NY, Monday-Thursday evenings; 2,489 trades Jan 2011 - Oct 2026; +2.74 bp per trade after costs and swap
  (t 2.86), +4.44 bp before swap; first 60% of history +0.07 bp (t 0.06), last 40% (mid-2020 on) +5.49 bp (t 3.57); Wednesday
  negative (-1.07 bp); "about $1.10 per 0.01 lot" per night; the effect "appears from about 2019" and depends on one exact
  hour; a 2% stop turned +$1,136 into -$83 in an earlier tester run. — [MQL5 blog, Schuch](https://www.mql5.com/en/blogs/post/779464)
- XAUUSD spread by hour (7.6 million ticks, 20 days, GMT broker): "about 15 points for most of the day, but 28 to 35 points
  around the daily rollover". — [MQL5 blog, Schuch](https://www.mql5.com/en/blogs/post/779464)
- London vs Asian range, 2008-2026: reversal after a London break 48.9-50.0%; day closes back inside the Asian range 46%. — [MQL5 blog, Karakanchev](https://www.mql5.com/en/blogs/post/778873)
- GC first-hour New York range (09:30-10:30 ET): single-sided break 79.23% of days, double break 13.08%, no break 7.69%
  (6 months, vendor). — [Edgeful](https://www.edgeful.com/blog/posts/gc-trading-strategy-initial-balance-algo)
- Academic intraday momentum (positive, i.e. trend rather than reversal, into the close): the first half-hour return predicts
  the last half-hour return in the S&P 500 ETF 1993-2013 (Gao, Han, Li, Zhou; snippet) — [Alpha Architect summary](https://alphaarchitect.com/2014/08/attention-prop-traders-the-first-half-hour-of-trading-predicts-the-last-half-hour/).
  Jin, Kearney, Li & Yang (2020, Journal of Futures Markets) find "the first half-hour return positively predicts the last
  half-hour return across all four futures" for Chinese copper, steel, soybean and soybean meal (not gold), strongest after
  high-volume/high-volatility first sessions — [IDEAS/RePEc](https://ideas.repec.org/a/wly/jfutmk/v40y2020i4p632-650.html).
  Search summaries also pointed to papers reporting the same sign in Chinese gold/silver futures and in gold/silver/oil ETFs,
  but I could not match those claims to a specific opened paper, so treat them as unverified.
- Practitioner description without statistics: Tokyo is thin and builds a range; London's "loud part" is its first three
  hours; a lull follows in the early European afternoon; New York is gold's "center of gravity" where trend days travel; US
  releases land at 08:30 and 10:00 NY; spreads widen into the rollover. — [MQL5 blog, Nakayama](https://www.mql5.com/en/blogs/post/772224)
- Vendor result on kill-zone timing for sweep reversals: 53.2% wins / PF 1.68 inside London and New York kill zones vs 47.1%
  / PF 1.21 across all hours (costs unstated). — [Backtrex](https://backtrex.com/en/blog/liquidity-sweep-strategy-backtest-results)
- Counter-finding: "special" ICT hours perform no better than equally active hours once costs are a smaller share of wider
  stops. — [TradingView, GoodBadBitcoin](https://id.tradingview.com/script/teL2dDvS-Silver-Bullet-GBB/)

### Inferences
- Evidence quality: HIGH for StoneX's descriptive session returns (named analyst, recent, but only 2026 and not a trading
  test); MEDIUM for the 18:00-03:00 NY drift (independent, cost-inclusive, but concentrated after 2019-2020 and
  single-hour-sensitive); LOW for all "Asia ranges, London trends" folklore.
- The project's own 5m data (sibling note) puts variance ratios at 0.90-1.03 in every session: London hours lean slightly
  mean-reverting, Asia and the New York morning very slightly trending - the opposite of the folklore, and too small to trade.
- Practical reading for a reversal trader: (1) in Asia hours the documented effect is an upward drift, so only the long side
  of a fade is aligned with it (buy dips 18:00-03:00 NY = 07:00-16:00 SGT winter); selling Asian-session rallies fights it;
  (2) US hours carried the 2026 decline, so buying dips 08:00-17:00 NY has been the costliest fade; (3) avoid 16:00-19:00 NY
  where the spread is about double; (4) the quiet-hour advantage of narrow ranges is offset by cost being a larger fraction
  of the move.
- For the Singapore user, the Asia-hours window is the daytime one, which is convenient but is also the lowest-range window;
  targets there will be small in dollars, which worsens the cost ratio.

### Gaps
- No published variance-ratio/autocorrelation study of XAUUSD by session was found (only our own).
- StoneX quotes support $3,870 and resistance $3,920 on 16 Nov 2026, which sits below the "around $4,050" in the brief; the
  current price level should be re-checked before position sizing.
- No statistics on the "lunch lull" (11:30-13:30 NY) as a mean-reversion window for gold.

## 10. Which filters are reported to matter most (higher-timeframe trend, news avoidance, volatility regime, ADX)?

### Takeaway
The filters with any support are: require a liquidity sweep (rather than time-of-day alone), trade in the direction of the
higher-timeframe bias/drift, keep reward at or above 1.5-2R, and stand aside on trend/news days; but no filter has been shown
out-of-sample to turn a losing gold fade into a winner, and one large calibration (8,064 combinations per market) found none
that held.

### Cited Findings
- The liquidity sweep was "the only rule that consistently added edge" in the 25,000-configuration Silver Bullet study; the
  15-minute bias and market-structure-shift filters "caused performance to crater"; looser, higher-frequency versions survived
  better than textbook versions. — [gist.ly summary](https://gist.ly/youtube-summarizer/i-backtested-25000-ict-silver-bullet-trades)
- In a per-concept attribution of 47 AI-discretionary ICT trades, only higher-timeframe directional bias had a 95% interval
  above zero (+0.01 to +1.32R); liquidity sweep -0.10 to +1.24R; NY AM killzone -0.48 to +1.15R. — [Offbeat Forex](https://offbeatforex.com/is-ict-strategy-profitable/)
- Vendor parameter study: kill-zone filter +6 points of win rate; displacement candle body >= 70% of range cut false signals
  23%; minimum 1:1.5 reward:risk added 0.31 to profit factor; the losing year (2022) was "false sweeps during high macro
  volatility". — [Backtrex](https://backtrex.com/en/blog/liquidity-sweep-strategy-backtest-results)
- N-bar sweep test: 1R targets were negative, 2R and 3R positive. — [forge.mql5.io Warrior_EA](https://forge.mql5.io/aron3/Warrior_EA/blame/branch/main/research/test_liquidity.py)
- VWAP fade regime filters (unverified): skip when ADX(14, 5m) > 25, on major US releases, or when the opening-hour range is
  > 2x its 20-day average; claimed win rate 55-65% with filters vs about 45% without. — [CrossTrade](https://crosstrade.io/learn/trading-strategies/vwap-reversion)
- Range-size filter on the Asian range (0.30%-1.60% of price) used to avoid false breakouts in very narrow ranges
  (continuation system; no before/after numbers). — [MQL5 blog](https://www.mql5.com/en/blogs/post/777540)
- Long/short asymmetry on gold: long profit factor 1.96 vs short 1.14 in a spread-adjusted 10-minute gold script (snippet). — [TradingView](https://in.tradingview.com/script/LxrgnsTO-XAUUSD-10-Minute-Strategy)
- Negative result on filters: 8,064 filter and exit combinations per market calibrated on the first 60% of the data for the
  breakout/fade set-up "found nothing that held across markets"; in the tournament, the best in-sample setting was positive
  out-of-sample only 49% of the time. — [MQL5 blog, Schuch](https://www.mql5.com/en/blogs/post/779464)
- Testing-window advice (vendor): distrust gold backtests that start after 2022 because the 2023-2026 uptrend flatters
  buy-side logic; include 2013, 2020 and 2022; be wary of narrow hour-specific filters, which "can decay quickly and depend on
  broker timezone details"; favour wide ATR-based stops over tight stops and thin scalps. — [MQL5 blog, Sakamoto](https://www.mql5.com/en/blogs/post/774275)

### Inferences
- Ranking by support: (1) reward >= 1.5-2R (three sources, including one independent); (2) higher-timeframe
  trend/drift alignment (two weak sources plus our own data); (3) requiring an actual sweep of a prior extreme (two sources, but
  contradicted on gold by Schuch); (4) news/trend-day avoidance and ADX < 25 (asserted, never measured); (5) time-of-day
  "killzones" (vendor-positive, independently refuted as special).
- Our 5m/15m data covers only Jan 2025 - May 2026, a bull run plus the start of the correction; any trend filter fitted there
  will look better than it is. The 1h data (2019 - Sep 2026) should be used to check that the filter direction is not just
  "long gold".
- Filters reduce trade count; with a 16-month sample a filtered rule may leave fewer than 100-200 trades, too few to
  distinguish +0.05R from -0.05R.

### Gaps
- No gold-specific measurement of how news-window exclusion or an ADX threshold changes fade expectancy.
- No source tests a volatility-regime switch (e.g. daily ATR percentile) for intraday gold mean reversion.

## 11. Typical win rate versus reward:risk, profit per trade in $/oz, and does it survive a $0.30-0.50/oz round-trip cost?

### Takeaway
Honest mechanised reversal tests show 25-52% winners when targets are 1.5-2R and about 63% winners when the target is half the
stop, with gross expectancy within a few hundredths of R of zero in every case; at 5m scale a $0.30-0.50 cost is 0.05-0.20R
(and our measured all-in cost of about $0.75-0.80 is double that), which is larger than any independently verified edge.

### Cited Findings
- Win rate / pay-off pairs from cost-inclusive or against-interest tests: Silver Bullet with >= 1.5R targets, about 25% wins,
  negative in all 92 hour-market combinations — [TradingView, GoodBadBitcoin](https://id.tradingview.com/script/teL2dDvS-Silver-Bullet-GBB/);
  FVG kill-zone 1:2 bracket, 33.89% wins, PF 0.80 — [Backtrex](https://backtrex.com/en/backtests/ict-kill-zone-fvg-gbp-usd);
  mechanical ICT bot, 29.6% wins with +1.63R average winner, PF 0.81 — [Offbeat Forex](https://offbeatforex.com/is-ict-strategy-profitable/);
  range fade to the middle with a 1-range stop, 63.1% wins, -0.051R; fade to the other edge, 49.3%, -0.044R; tight-stop fade,
  45%, -0.24R — [MQL5 blog, Schuch](https://www.mql5.com/en/blogs/post/779464)
- Profitable survivors in the 25,000-configuration study clustered at a 52% win rate, top performers 34-48%; the few near 70%
  took small profits about 20 times a year. — [gist.ly summary](https://gist.ly/youtube-summarizer/i-backtested-25000-ict-silver-bullet-trades)
- Cost levels: 0.7-1.6 bp per trade (1.5x live spread plus commission) across nine FTMO markets; XAUUSD spread about 15 points
  most of the day and 28-35 points at rollover; M5 reversion scalps net -0.2 to -2.0 bp per trade out-of-sample and about zero
  gross. — [MQL5 blog, Schuch](https://www.mql5.com/en/blogs/post/779464)
- Vendor claim for comparison: XAUUSD sweep reversal 53.7% wins, PF 1.75 (costs unstated). — [Backtrex](https://backtrex.com/en/blog/liquidity-sweep-strategy-backtest-results)
- A fixed-SL/TP practitioner view from the MQL5 forum: "never found a strategy with fixed SL and TP and profit factor above
  1.5 - 1.7". — [MQL5 forum](https://www.mql5.com/en/forum/512226)
- Fixed-spread backtests overstate gold results: "A Sharpe ratio of 2.5 in a fixed-spread backtest on XAUUSD can turn into
  near-breakeven in live"; the author's backtest used an 18-point fixed spread while live spread around the 13:30 UTC news
  window reportedly reached 60, 90 and sometimes 140 points for 3-5 minutes, and went from 22 to 108 points in under a minute
  at the March 2022 NFP. Author sells gold MT5 tools (1 Jun 2026). — [MQL5 blog, Hoai Nam Trinh](https://www.mql5.com/en/blogs/post/770488)

### Inferences
- Break-even win rate with stop S, target T and round-trip cost c (all $/oz): p = (S + c) / (S + T). Worked cases at c = $0.40
  (brief) and c = $0.80 (our measured Dukascopy all-in median, sibling note):
  - T $1 / S $2 ("many small wins"): gross 66.7%; 80.0% at $0.40; 93.3% at $0.80.
  - T $2 / S $4: gross 66.7%; 73.3%; 80.0%.
  - T $3 / S $3: gross 50.0%; 56.7%; 63.3%.
  - T $5 / S $5: gross 50.0%; 54.0%; 58.0%.
  - T $9 / S $6 (1.5R): gross 40.0%; 42.7%; 45.3%.
  - T $10 / S $5 (2R): gross 33.3%; 36.0%; 38.7%.
  - T $20 / S $10 (2R, 15m-scale): gross 33.3%; 34.7%; 36.0%.
- Cost in R terms is c / S: with a $2 stop it is 0.20R ($0.40) or 0.40R ($0.80); $4 stop 0.10R / 0.20R; $6 stop 0.07R / 0.13R;
  $10 stop 0.04R / 0.08R. The largest independently observed gross expectancies in this family are about 0.00 to +0.04R
  (Warrior_EA split-halves; Schuch's "about zero before costs"). So no verified reversal edge covers even the cheapest cost
  case on 5m-scale stops; only stops of roughly $10+ bring cost down to the size of the best-case edge.
- In price terms, $0.30-0.50 is 0.74-1.23 bp at $4,050 and $0.80 is about 2.0 bp. Schuch's M5 scalps lost 0.2-2.0 bp net.
  The one surviving gold effect (overnight Asia drift) earns about 2.7 bp ($1.11/oz) per trade net over 9 hours - the same
  order as one round-trip cost - which shows how small real intraday gold edges are.
- Our own 1h RSI(2) result fits the pattern: profit factor 1.09 gross with 60% winners became 0.82 net over 2,066 trades.
- High-win-rate designs do not create edge, they move it: a 63% win rate with a half-size target is the random-walk outcome
  (see section 6). The cost burden is heaviest precisely on the small-target designs the user finds attractive, because the
  cost is a fixed dollar amount subtracted from a small win and added to a larger loss.
- On a $100 account at the 0.01-lot minimum, a $5 stop is 5% of the account per trade and a $10 stop is 10%; stops wide enough
  to make cost small in R terms are too large for sensible risk per trade unless the broker offers smaller sizes (e.g. 0.001
  lot / micro-ounce contracts).

### Gaps
- No source reports average profit per trade in $/oz for a 5m/15m gold reversal system net of realistic costs, other than our
  own tests.
- Sources rarely state stop distances in dollars, so most cost-in-R conversions above are mine.

## 12. What are the known failure modes, and which single reversal-style method is the least-bad candidate to backtest and then trade at minimum size?

### Takeaway
All reversal-style methods share negative skew on trend and news days (2022's false sweeps, the 9.5-9.8% one-day fall on 30 Jan
2026, the US-session-led 2026 decline), and none has independent positive evidence on intraday gold after costs. If one must be
chosen, a trend/drift-aligned "sweep and reclaim" of a prior extreme with a structural stop and a target of at least 1.5-2R is
the least-bad candidate, because the sweep is the only component with any repeated support and the wider stop keeps cost near
0.05-0.10R; it should be tested against a random-entry control and expected to show 35-50% winners, not 70%.

### Cited Findings
- Trend-day failure of fades: VWAP reversion "fails badly" on strong trend days, on economic releases, in the first 30
  minutes, and on Friday afternoons. — [CrossTrade](https://crosstrade.io/learn/trading-strategies/vwap-reversion)
- Regime failure: the vendor sweep system lost in 2022 (-8.1%, 46.5% wins) on false sweeps in high macro volatility, with a
  longest losing streak of 8 and a -14.3% drawdown at 1% risk. — [Backtrex](https://backtrex.com/en/blog/liquidity-sweep-strategy-backtest-results)
- Gold mean reversion "gives back years of small gains in weeks" when a trend starts; pullback entries get filled far beyond
  the stop in news spikes, weekend gaps and liquidity holes. — [MQL5 blog, Sakamoto](https://www.mql5.com/en/blogs/post/774959)
- Tail event: gold fell about 9.5-9.8% on 30 Jan 2026 (about $520-540) and kept falling on 2 Feb; stops limit loss only if
  they fill near their price, and models with fixed spreads and perfect fills "look safer than they were". — [MQL5 blog, Lan Tran Hoang](https://www.mql5.com/en/blogs/post/778166)
- Session-specific risk in 2026: US hours account for -28.1% year-to-date versus +3.4% in Asia hours. — [StoneX](https://www.stonex.com/en-gb/news-and-analysis/gold-outlook-asia-buys-the-dip-us-hammers-the-rip-2026-11-16/)
- Adverse selection on limit entries: 70-76% of unfilled Silver Bullet limit setups would have reached target, while about 73%
  of filled trades hit the stop. — [TradingView, GoodBadBitcoin](https://id.tradingview.com/script/teL2dDvS-Silver-Bullet-GBB/)
- Negative skew of high-win-rate gold systems: one loss erasing 6-10 wins; a 90% win rate with $10 wins and $120 losses is
  -$3 per trade. — [MQL5 blog, Kortarla](https://mql5.com/en/blogs/post/760211); [MQL5 blog, Arribas Lopez](https://www.mql5.com/en/blogs/post/778258)
- Overfitting and decay: the best in-sample setting is positive out-of-sample 49% of the time; hour-specific effects have
  "only worked strongly for about five years" and depend on one exact hour. — [MQL5 blog, Schuch](https://www.mql5.com/en/blogs/post/779464)
- The sweep is the one component with repeated support: "only rule that consistently added edge" (NQ/ES) — [gist.ly summary](https://gist.ly/youtube-summarizer/i-backtested-25000-ict-silver-bullet-trades);
  positive at 2-3R on EURUSD H1 with tiny expectancy — [forge.mql5.io Warrior_EA](https://forge.mql5.io/aron3/Warrior_EA/blame/branch/main/research/test_liquidity.py);
  vendor XAUUSD PF 1.75 — [Backtrex](https://backtrex.com/en/blog/liquidity-sweep-strategy-backtest-results); but contradicted on XAUUSD M15
  (-0.051R vs random +0.004R) — [MQL5 blog, Schuch](https://www.mql5.com/en/blogs/post/779464)

### Inferences
- Ranking of the eight families by strength of evidence for a positive expectancy after costs on 5m/15m gold (all weak):
  1. Sweep-and-reclaim of a prior extreme with >= 1.5-2R target, drift/trend aligned (mixed: two supportive non-gold tests, one
     vendor-positive gold test, one independent gold test at about zero/slightly negative).
  2. Trend-filtered dip buying (Bollinger/RSI long-only in a higher-timeframe uptrend, or Asia-hours long-only): supported
     mainly by drift, least-bad in our own data, fails when the trend flips.
  3. Asian-range London fake-out fade: coin flip on 18 years of data.
  4. Opening-range / prior-range fade: negative with 92k trades per variant.
  5. VWAP fade: zero gross, negative net.
  6. Round-number / previous-day-level rejection: no tradable evidence.
  7. Overextension fades: no evidence.
  8. Grid/martingale/averaging: negative skew by construction; exclude.
- Suggested single test specification (reversal-style candidate): 15m bars; levels = previous-day high/low and Asian range
  (20:00-00:00 NY) high/low; bias = 1h close vs 1h 200-SMA (take only reclaim longs at swept lows in an uptrend and reclaim
  shorts at swept highs in a downtrend); signal = 15m bar exceeds the level by <= 0.5 x ATR(14) and closes back inside; market
  entry at next open (avoid limit-retrace entries because of adverse selection); stop = sweep extreme +/- 0.1 x ATR; target
  2R (also report 1.5R and 3R); time stop 16 bars; windows 02:00-05:00 and 07:00-11:00 NY (15:00-18:00 and 20:00-00:00 SGT in
  winter); no entries 16:00-19:00 NY or within 10 minutes of 08:30/10:00 NY data; one trade per level per day, max two per
  day. Report against a random-entry control with identical stop/target/time rules, split-half stability, and cost at both
  $0.40 and $0.80/oz.
- Pre-registered expectation from the literature: win rate 35-50%, gross expectancy between -0.05R and +0.05R, net negative
  to flat. A result much better than that on 16 months of data should be treated as sample luck or bull-market drift until it
  holds on the 1h data back to 2019 and in forward demo trading.
- The user's goal (high win rate, small wins, $100, 5m) conflicts with every finding here: small targets maximise the cost
  share, high win rates come only with stops larger than targets (negative skew), and the minimum 0.01-lot size makes a
  cost-efficient stop 5-10% of the account. The report should state this plainly whichever method is picked.

### Gaps
- No verified live track record (Myfxbook/FXBlue, 12+ months, no grid/martingale) of a 5m/15m gold reversal system was found;
  the search surfaced only vendor signals and self-reports.
- No independent test of the trend-aligned sweep-and-reclaim specifically on XAUUSD with a random-entry control exists other
  than Schuch's (which did not publish its sweep definition or trend filter), so the candidate above is untested as specified.
- QuantifiedStrategies, Quantpedia (intraday), Robot Wealth, Alvarez, Kevin Davey and r/algotrading yielded no gold intraday
  reversal backtests with usable statistics in this search; absence of evidence here may partly reflect paywalls.
