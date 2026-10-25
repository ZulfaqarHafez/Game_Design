# Backtest validation methodology, Python backtesting frameworks, and evidence on retail gold (XAUUSD) strategies

Research date: 2026-10-25. Scope: (1) validation/anti-overfitting methods with concrete thresholds, (2) intraday FX/metals data and lookahead biases, (3) open-source Python backtesting frameworks and fill models compared with TradingView, (4) the evidence on common gold strategies, (5) risk and position-sizing norms for XAUUSD.

Evidence labels used below: **[PEER]** = peer-reviewed journal; **[WP]** = working paper or thesis (not peer-reviewed); **[PRACT]** = practitioner or asset-manager research; **[DOCS]** = official software docs or registry metadata; **[BLOG/VENDOR]** = self-published or marketing material (weakest).

---

## 1. Overfitting and validation: how to make a backtest trustworthy (IS/OOS, walk-forward, Monte Carlo, plateaus, DSR, PBO, Harvey–Liu haircuts, trade counts, counting trials)

### Takeaway
The peer-reviewed literature (Bailey, Borwein, López de Prado and Zhu; Harvey and Liu) is clear on one point: **the number of variants tried (N) is the key input for judging a backtest.** A Sharpe ratio only means something once it is deflated for N, the sample length, and the skew and kurtosis of returns. A journal that records every run is therefore the core control, not a nice-to-have. The concrete published thresholds are:
- DSR ≥ 0.95.
- PBO ≤ 0.05, the paper's suggested Neyman–Pearson cut-off.
- MinBTL: with 5 years of data, at most about 45 independent configurations.
- Harvey–Liu haircut: marginal Sharpe ratios (below 0.4) lose more than 50%, while strong ones (above 1.0) lose at most about 25%.

Walk-forward efficiency, Monte Carlo and plateau checks are practitioner tools. Their thresholds are rules of thumb, not published results.

### Cited Findings

**Deflated Sharpe Ratio (DSR) and Probabilistic Sharpe Ratio (PSR)**
- [PEER] The DSR paper is Bailey & López de Prado, "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality", *Journal of Portfolio Management* (2014). It states: "Not controlling for the number of trials involved in a particular discovery leads to" inflated performance. The paper also lists Minimum Track Record Length and Minimum Backtest Length as keywords — [SSRN 2460551](https://papers.ssrn.com/abstract=2460551); [PDF](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)
- [PEER] The DSR is a PSR whose rejection threshold is set to the *expected maximum* Sharpe ratio across N independent unskilled trials. That expected maximum is computed from the variance of the trials' Sharpe ratios V[{SR_n}], N, the Euler–Mascheroni constant (≈0.5772) and the inverse normal CDF. PSR itself takes the sample length T and the skewness and kurtosis of the selected strategy's returns. In the paper's words, "DSR is a PSR where the rejection threshold is adjusted to reflect the multiplicity of trials" — [DSR paper](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)
  - Standard formulas, reproduced for implementers; the PDF math did not extract cleanly, so check the symbols against the paper:
    - `SR0 = sqrt(V[SR_n]) * ((1-γ)*Φ⁻¹(1-1/N) + γ*Φ⁻¹(1-1/(N·e)))`
    - `DSR = Φ( (SR̂ - SR0)*sqrt(T-1) / sqrt(1 - skew*SR̂ + (kurt-1)/4 * SR̂²) )`
    - All SRs are non-annualised, at the frequency of the observations.
- [PEER] Worked example from the paper: a 5-year daily backtest (T=1250) with an annualised SR of 2.5 is selected among many trials and has fat-tailed, negatively skewed returns. The investor finds only "a 90% chance that the true SR … is greater than zero" and declines. Had the strategist run "only N=46 independent trials", DSR "would have been 0.9505, above the 95% confidence level". With Normal returns, the threshold would only have been breached "after N=88 independent trials" — [DSR paper](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)
- [PEER] Appendix A.3, "Estimating the number of independent trials": M correlated trials must be reduced to an "implied independent" N̂ using the average correlation between trials. "Using M instead of N will overstate E[max SR]" — [DSR paper](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)
- [PEER] "When should we stop testing?": the paper recommends planning trials in advance and says "Investment theory, not computational power, should motivate what experiments are worth conducting." As a stopping rule it suggests the 1/e (secretary-problem) law. Sample about 37% of the theoretically justified configurations at random, then keep testing until one beats all previous ones, and stop there — [DSR paper](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)
- [DOCS] The R package quantstrat implements DSR as a function taking `nTrials` and `varTrials` (the variance of the trials' Sharpe ratios). So the journal must store each trial's SR, not just a count — [quantstrat deflatedSharpe](https://www.rdocumentation.org/packages/quantstrat/versions/0.16.7/topics/deflatedSharpe)

**Minimum Backtest Length (MinBTL)**
- [PEER] Bailey, Borwein, López de Prado & Zhu, "Pseudo-Mathematics and Financial Charlatanism", *Notices of the AMS* (2014), Theorem 3.1:
  - MinBTL in years ≈ (expression in N)/E[max_N]², with the upper bound **MinBTL < 2·ln(N)/E[max_N]²**.
  - "If only 5 years of data are available, no more than 45 independent model configurations should be tried, or we are almost guaranteed to produce strategies with an annualized Sharpe ratio IS of 1, but an expected Sharpe ratio OOS of zero."
  - MinBTL is "a necessary, non-sufficient condition to avoid overfitting."
  - Correlated trials should be reduced to independent N, e.g. by PCA.
  - [paper PDF](https://carmamaths.org/jon/backtest.pdf); [record](https://scholarworks.wmich.edu/math_pubs/40/)
- [PEER] Harvey & Liu summarise the López de Prado result: "only seven trials are needed to obtain a spurious two-year backtest that has an in-sample realized Sharpe ratio of more than 1.0, while the expected out-of-sample Sharpe ratio is zero" — [Harvey & Liu 2015](https://people.duke.edu/~charvey/Research/Published_Papers/P120_Backtesting.PDF)

**Probability of Backtest Overfitting (PBO) via CSCV**
- [PEER] Bailey, Borwein, López de Prado & Zhu, "The Probability of Backtest Overfitting", *Journal of Computational Finance* 20(4), 2017, DOI 10.21314/jcf.2016.322. It is a model-free, non-parametric method called combinatorially symmetric cross-validation (CSCV) — [Risk.net](https://www.risk.net/journal-of-computational-finance/2471206/the-probability-of-backtest-overfitting); [eScholarship](https://escholarship.org/uc/item/4w1110bb)
- [PEER] The CSCV algorithm, from the paper:
  1. Build a T×N matrix M of returns, one column per tried configuration.
  2. Split it by rows into an even number S of blocks.
  3. For every combination of S/2 blocks as the training set, with the complement as the test set:
     - pick the best in-sample configuration n*;
     - compute its relative out-of-sample rank ω̄ = rank/(N+1);
     - record the logit λ = ln(ω̄/(1−ω̄)).
  4. PBO is the share of combinations with λ ≤ 0, i.e. the in-sample winner falls below the out-of-sample median.
  - [PBO paper PDF](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf)
- [PEER] Recommended settings and outputs:
  - The paper recommends **S = 16**. It says this gives "12,780 combinations"; note that C(16,8) is actually 12,870, a typo in the paper. With about 4 years of daily data, S = 16 roughly equals quarterly blocks, which preserves serial correlation.
  - Decision rule: "a customary approach would be to reject models for which PBO is estimated to be greater than 0.05."
  - Diagnostics: OOS performance degradation (regression of OOS on IS Sharpe ratios), OOS probability of loss, and stochastic dominance against random selection.
  - Example results: a PBO of 74% for an overfit strategy versus 0.04% for a real one.
  - [PBO paper PDF](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf)
- [DOCS] An R implementation exists: CRAN package `pbo`, which uses the Omega ratio by default — [CRAN pbo README](https://ftp.fau.de/cran/web/packages/pbo/readme/README.html)

**Harvey & Liu multiple-testing haircut**
- [PEER] Harvey & Liu, "Backtesting", *Journal of Portfolio Management*, Fall 2015. The method converts SR to a t-ratio, adjusts the p-value for multiple testing (Bonferroni, Holm, BHY, or their average), then converts back to a "haircut Sharpe ratio" — [Harvey & Liu 2015](https://people.duke.edu/~charvey/Research/Published_Papers/P120_Backtesting.PDF)
- [PEER] Worked example (independent tests): 20 years of monthly data (T=240) and an annual SR of 0.75 give a single-test p-value of 0.0008. With N=200 tests, pM = 0.15, which implies an adjusted SR of 0.32. That is **a ≈60% haircut** — [Harvey & Liu 2015](https://people.duke.edu/~charvey/Research/Published_Papers/P120_Backtesting.PDF)
- [PEER] The haircut is non-linear: "the haircut is almost always more than and sometimes much larger than 50% when the annualized Sharpe ratio is less than 0.4. On the other hand, when the Sharpe ratio is greater than 1.0, the haircut is at most 25%." So the usual 50% rule of thumb "is too lenient for relatively small Sharpe ratios (< 0.4) and too harsh for large ones (> 1.0)" — [Harvey & Liu 2015](https://people.duke.edu/~charvey/Research/Published_Papers/P120_Backtesting.PDF)
- [PEER] Further examples from the paper:
  - An autocorrelation-corrected SR of 0.912 becomes 0.438 under BHY, a 52.0% haircut.
  - Profit hurdle: for 20 years, 10% volatility, 300 tests and average correlation 0.4, the strategy needs a mean return of 0.621%/month (BHY) or 0.670%/month (average of methods) to be significant at 5%.
  - Harvey, Liu & Zhu document "at least 316 factors" tested in equity research. A single-test t-ratio of 3.0 "may not be" significant once this is accounted for.
  - [Harvey & Liu 2015](https://people.duke.edu/~charvey/Research/Published_Papers/P120_Backtesting.PDF)
- [DOCS] R ports exist: `Haircut_SR` and `profitHurdle` in quantstrat — [rdocumentation profit.hurdle](https://www.rdocumentation.org/link/profit.hurdle); [Haircut_SR source](https://rdrr.io/github/marsanul/quantstrat/src/sandbox/Harvey_Liu_Backtesting/50a170e4e37da951ea1192888418c82a/Haircut_SR%20with%20sample_random_multests.R)

**Walk-forward analysis and cross-validation**
- [PRACT/secondary] Pardo's walk-forward efficiency (WFE) is the annualised OOS return (or mean) divided by the annualised IS return of the preceding optimisation window. WFE ≥ 0.5 is cited as the robustness benchmark, i.e. the strategy keeps at least half its IS edge OOS. Pardo's book was not reached directly, so this is second-hand — [quantammsim WFA tutorial](https://quantammsim.readthedocs.io/en/latest/tutorials/walk_forward_analysis.html); [Investing.com PSAR WFA report](https://investing.com/analysis/psar-walk-forward-test-report-124495)
- [PRACT] Other bands, such as ≥0.7 excellent, 0.5–0.7 good and <0.3 likely overfit, circulate without a Pardo citation. Treat them as heuristics — [quantammsim WFA tutorial](https://quantammsim.readthedocs.io/en/latest/tutorials/walk_forward_analysis.html)
- [PRACT/academic book] Purged and embargoed CV and CPCV (López de Prado, *Advances in Financial Machine Learning*, 2018, ch. 7):
  - Purging drops training observations whose label windows overlap the test fold.
  - An embargo drops observations right after each test fold.
  - CPCV yields many OOS paths, so a *distribution* of OOS Sharpe ratios, where single-path walk-forward gives one estimate.
  - Embargo sizes quoted online (1%, 5%) are illustrative, not canonical.
  - [Wikipedia: Purged cross-validation](https://en.wikipedia.org/wiki/Purged_cross-validation); [fynance CPCV docs](https://fynance.readthedocs.io/en/latest/generated/fynance.data.combinatorial_purged_cv.html)
- [PEER] The PBO paper argues that standard hold-out techniques "tend to be unreliable" for investment backtests, which motivates CSCV — [Risk.net abstract](https://www.risk.net/journal-of-computational-finance/2471206/the-probability-of-backtest-overfitting)

**A gold-specific cautionary example of parameter sweeps**
- [WP] Urquhart, Batten, Lucey, McGroarty & Peat (SSRN 2652637) tested **66,297** moving-average rules on 5-minute spot gold and silver:
  - Standard literature parameters generated "significant negative payoffs".
  - Parameter sweeps found profitable gold rules.
  - In the in-sample/out-of-sample test, "only the SMA rule for gold generates significant profits in the in-sample as well as the out-of-sample period. All of the other best rules in the in-sample period generate either insignificant or negative payoffs in the out-of-sample period."
  - [Urquhart et al. PDF](https://c.mql5.com/forextsd/forum/174/does_technical_analysis_beat_the_market__evidence_from_high_frequency_trading_in_gold_and_silver.pdf)

### Inferences
- **Journal design implication.** Each strategy family needs a trial ledger storing:
  - parameter hash, data range and timeframe;
  - the per-bar or per-day return series, needed for PBO/CSCV and the correlation-based effective N;
  - SR, skew and kurtosis.
  
  Without the return series you cannot compute PBO or the effective N, and without the SRs you cannot compute V[SR] for the DSR. Re-running a deleted variant should *not* reset the counter. N should be cumulative per hypothesis family and should include manual "eyeballing" runs.
- **Minimum trade count (derived, not from a single source).** For per-trade returns with mean μ and SD σ, t ≈ (μ/σ)·√n. To reach t = 2 you need n ≈ 4/(μ/σ)²; for t = 3, n ≈ 9/(μ/σ)².
  - Typical retail intraday edge, per-trade μ/σ ≈ 0.1: about 400 trades for t = 2, about 900 for t = 3.
  - Per-trade μ/σ ≈ 0.2: about 100 and 225 respectively.
  - A floor of about 100 trades is a *minimum* sanity check, not proof. The Harvey–Liu logic argues for t ≥ 3 once many variants have been tried.
- **Plateau check (heuristic, no published threshold found).** Perturb each parameter by about ±10–25% and/or take a 3×3 (or 5×5) neighbourhood on the optimisation heatmap. Flag the result if the neighbourhood median metric falls below about 70% of the peak, or if any neighbour is negative. backtesting.py's `return_heatmap` output supports this directly (see section 3).
- **Monte Carlo (heuristic).** Bootstrap or reshuffle the trade sequence 1,000–10,000 times. Reshuffling leaves total P&L unchanged but changes drawdown; bootstrapping changes both. Size positions from the 95th-percentile max drawdown, not the historical one, and require the 5th-percentile terminal equity to be above the starting equity. Also randomise entry by ±1 bar and costs by ±50% to test execution sensitivity. Block bootstrap preserves volatility clustering, which matters for gold.
- **Final holdout.** Reserve the most recent 20–30% of data, untouched until a single final evaluation. Log the holdout's use in the journal; any further tuning after looking at it turns it into in-sample data.

### Gaps
- Pardo's original WFE threshold wording and walk-forward window recommendations could not be read directly; the 0.5 benchmark is second-hand.
- No peer-reviewed numeric threshold was found for parameter-plateau checks or Monte Carlo drawdown percentiles; those above are engineering heuristics.
- The DSR formula symbols were reconstructed (PDF math was garbled in extraction); verify against the paper. The numerical example's input values beyond T=1250 (N, V[SR], skew, kurtosis) were not legible in the extracted text.
- Minimum Track Record Length (Bailey & López de Prado 2012, "The Sharpe Ratio Efficient Frontier") was not fetched this session.

---

## 2. Lookahead and data biases specific to intraday FX and metals (same-bar close trading, timezone/session misalignment, spread, data-source effects)

### Takeaway
The main ways to fool yourself on XAUUSD intraday data are:
- filling on the close of the same bar that generated the signal;
- higher-timeframe values that "see" the unfinished bar;
- intrabar stop/target ordering assumptions;
- session windows defined in the wrong timezone or ignoring daylight saving time;
- ignoring spread and slippage.

The cost point is severe for gold session strategies. In every gold or ORB source found, the gross edge disappeared or shrank sharply net of realistic costs.

### Cited Findings
- [DOCS] TradingView: with `request.security(..., lookahead = barmerge.lookahead_on)` and no offset, the script "will return data from the future on historical bars, which is dangerously misleading". The safe pattern is to offset the expression by `[1]` *and* use `lookahead_on`: "Neither can be removed without compromising the integrity of the function." The future leak appears only on historical bars — [TradingView repainting docs](https://www.tradingview.com/pine-script-docs/concepts/repainting/)
- [DOCS] TradingView: "Historical data does not include records of intermediary price movements on bars". Strategies with `calc_on_every_tick = true` "will most probably not generate the same order executions, and so repaint", and this "also invalidates backtesting results" — [TradingView repainting docs](https://www.tradingview.com/pine-script-docs/concepts/repainting/)
- [DOCS] backtesting.py: by default, market orders fill at the **next bar's open**. `trade_on_close=True` fills "with respect to the current bar's closing price instead of the next bar's open", which is optimistic if the signal uses that close — [backtesting.py API docs](https://kernc.github.io/backtesting.py/doc/backtesting/backtesting.html)
- [DOCS] vectorbt warns: "make sure that your signaling logic happens at the very end of the bar". For signals built from close, it suggests shifting them (`signals.vbt.fshift(1)`) and to "make sure to use a price that comes after the signal". Stop signals have priority within a bar, and if `open/high/low` are not provided they are approximated from `close` — [vectorbt Portfolio API](https://vectorbt.dev/api/portfolio/base/)
- [WP] Example of correct timezone handling for gold (CBS thesis, COMEX GC 5-min data 2001–2018):
  - converted data "from GMT to New York time";
  - rebuilt each trading day to start at 17:00 NY so each row holds the 23-hour GC session;
  - dropped weekends and US holidays;
  - forward-filled empty bid/ask intervals, acknowledging the sampling error this introduces.
  - [Donati & Jung, CBS thesis PDF](https://research-api.cbs.dk/ws/portalfiles/portal/59803241/651553_Thesis_Contract_13383.pdf)
- [PEER/press] The London gold fixing took place at 10:30 and 15:00 London time, i.e. in local time, which shifts against UTC with UK daylight saving — [Mail & Guardian](https://mg.co.za/business/2014-03-03-gold-fix-study-indicates-a-decade-of-manipulation/). In March 2015 it was replaced by the ICE-administered LBMA Gold Price — [UWA research impact](https://researchimpact.uwa.edu.au/research-impact-stories/tag/gold/)
- Costs wipe out gross edges in gold and intraday strategies:
  - [WP] Gold intraday-seasonality strategies reach "Sharpe ratios as high as 1.61" without costs, but "when taken into account, trading strategies underperform the market" — [CBS thesis](https://research-api.cbs.dk/ws/portalfiles/portal/59803241/651553_Thesis_Contract_13383.pdf)
  - [BLOG] An ORB replication on NQ/SPX/Dow/DAX/FTSE CFDs (2015–2026) reproduced the paper gross (+0.131R on NQ). After costs, "no market is distinguishable from zero, four of five are negative"; the original paper charged commission but no spread or slippage — [MQL5 blog replication](https://www.mql5.com/en/blogs/post/776235)
  - [PRACT] For the GLD overnight effect, almost all gains come close-to-open, but the raw edge is probably not tradable after costs — [Quantified Strategies](https://quantifiedstrategies.substack.com/p/a-quantitative-look-at-the-gold-overnight)
- [PRACT] Quantpedia warns about relying on OHLC open prices, using the "overnight drift" in the GDX gold-miners ETF as a case study (official open prints may not be achievable fills). Only the title and snippet were reviewed — [Quantpedia](https://quantpedia.com/dangers-of-relying-on-ohlc-prices-the-case-of-overnight-drift-in-gdx-etf/)
- [PEER] Blose & Gondhalekar: investors "should not enter market buy orders when the market is closed to be executed at the price of the first trade", because gold tends to open high — [Applied Economics Letters 2014](https://ideas.repec.org/a/taf/apeclt/v21y2014i18p1269-1272.html)
- [BLOG] An Asian-range gold breakout backtest was run on two brokers' real-tick data and gave somewhat different results. Feed choice matters for XAUUSD CFDs — [MQL5 London breakout on gold](https://www.mql5.com/en/blogs/post/777540)

### Inferences
- **Engine defaults to build in:**
  - Signals are computed on bar t's close and filled at bar t+1's open plus half-spread plus slippage.
  - Stop and limit orders fill at the level, or at the open if the market gapped through it.
  - "Trade on close" is an explicit, logged opt-in.
- **Store all timestamps in UTC.** Derive session windows (Asia, London open, NY open, LBMA fixes at 10:30/15:00 London, COMEX 17:00 ET daily break) with `zoneinfo` (`Europe/London`, `America/New_York`). US and UK switch DST on different dates (2–3 week gaps in March and Oct/Nov), so a fixed-UTC "London open" is wrong for part of the year. Also log the bar-timestamp convention of each data source (open-time vs close-time).
- **Bid-only charts.** XAUUSD retail charts (MT4/MT5 and many CFD feeds on TradingView) usually plot the **bid**. Long entries then need the ask (bid + spread), and longs' stops trigger on the bid. Spreads also widen around the 17:00 NY rollover and news releases. Model spread as time-of-day-dependent, or at least use a conservative constant plus a widening multiplier in the rollover hour. This is general market knowledge, not verified from a source this session.
- **"Survivorship-like" biases in FX/metals** come from the data rather than delisting:
  - broker-specific CFD feeds and synthetic history before a broker existed;
  - continuous-futures roll method for GC (back-adjusted vs unadjusted);
  - forward-filled gaps;
  - choosing a backtest start date after seeing the chart.
- **Unit test for lookahead:** compute signals on data truncated at t, then on the full dataset. Signals at times ≤ t must be identical.

### Gaps
- No authoritative source was fetched on XAUUSD retail spread profiles by hour, or on spread widening at rollover; this needs broker data.
- Quantpedia's GDX OHLC article was not read in full.

---

## 3. Open-source Python backtesting frameworks (status Oct 2026, licences, strengths, fill models vs TradingView)

### Takeaway
As of October 2026:
- **backtesting.py** (AGPL-3.0) and **vectorbt** (Apache-2.0 + Commons Clause) are both active and are the closest analogues to a TradingView-style bar backtester.
- **NautilusTrader** (LGPL-3.0) is the most production-grade, with backtest/live parity. Version 2.0 was in release candidate.
- **backtrader** (GPLv3) has had no PyPI release since April 2023; treat it as unmaintained.
- **zipline-reloaded** (Apache-2.0) and **LEAN** (Apache-2.0) are active.

Licence matters for a product. AGPL and Commons Clause restrict commercial distribution or hosting.

### Cited Findings

**Status and licences**

| Framework | Licence | Latest release (PyPI) | Notes / source |
|---|---|---|---|
| backtesting.py | AGPL-3.0-or-later | 0.6.6, uploaded 2026-07-22; Python ≥3.9 | [DOCS] [PyPI](https://pypi.org/project/backtesting/) |
| vectorbt (open-source) | Apache 2.0 with Commons Clause | 1.2.0, uploaded 2026-10-19; Python 3.11–3.14 | [DOCS] Commons Clause: no right to "Sell", including hosting/consulting "whose value derives, entirely or substantially, from the functionality of the Software". [PyPI](https://pypi.org/project/vectorbt/); [LICENSE.md](https://github.com/polakowo/vectorbt/blob/master/LICENSE.md) |
| backtrader | GPLv3+ | 1.9.78.123, uploaded 2023-04-19 | [DOCS] No release in ~3.5 years, so effectively unmaintained (outdated). [PyPI](https://pypi.org/project/backtrader/) |
| NautilusTrader | LGPL-3.0-or-later | stable 1.231.0; latest upload 2.0.0rc7 (2026-10-15); Python 3.12–3.14 | [DOCS] [PyPI](https://pypi.org/project/nautilus-trader/); [LICENSE](https://github.com/nautechsystems/nautilus_trader/blob/develop/LICENSE) |
| zipline-reloaded | Apache-2.0 | 3.2.0, uploaded 2026-10-18; Python 3.11–3.14 | [DOCS] [PyPI](https://pypi.org/project/zipline-reloaded/) |
| LEAN / QuantConnect | Apache 2.0 (engine) | `lean` CLI 1.0.230, uploaded 2026-10-15 | [DOCS] [LEAN LICENSE](https://github.com/QuantConnect/Lean/blob/master/LICENSE); [lean CLI PyPI](https://pypi.org/project/lean/) |
| bt (portfolio-level) | MIT | 1.4.1, uploaded 2026-10-10 | [DOCS] [PyPI](https://pypi.org/project/bt/) |

**Fill models**
- [DOCS] backtesting.py `Backtest` parameters:
  - `trade_on_close` (default False, so next-bar open);
  - `spread`, a constant relative bid–ask rate ("0.0002" approximates forex);
  - `commission`, "applied twice: at trade entry and at trade exit", which can be a rate, a (fixed, relative) tuple or a callable;
  - `margin` (0.02 = 50:1);
  - `hedging`; `exclusive_orders`; `finalize_trades`.
  - SL/TP are contingent stop-market and limit orders.
  - `optimize()` supports exhaustive or randomised `grid` and model-based `sambo` search, `max_tries`, `constraint`, `return_heatmap` and `random_state`, and maximises Van Tharp's SQN by default.
  - The docs reviewed did not say how SL and TP hit in the same bar are resolved.
  - [backtesting.py API](https://kernc.github.io/backtesting.py/doc/backtesting/backtesting.html)
- [DOCS] vectorbt `from_orders`/`from_signals`:
  - `price` "Defaults to `np.inf`", which in vectorbt resolves to the bar close (inference from library convention; the excerpt did not spell it out).
  - Missing `open/high/low` are approximated from close.
  - Stop signals execute "before other signals within the same bar".
  - The event-driven `from_order_func` is described as having "less risk of exposure to the look-ahead bias".
  - [vectorbt Portfolio API](https://vectorbt.dev/api/portfolio/base/)
- [DOCS] NautilusTrader's backtesting docs have dedicated sections on "deterministic matching behavior", "bars, OHLC sequencing, and bar timing", "slippage and probabilistic fills", and matching data granularity to venue `book_type`. The subpages were not retrieved, so specifics are unverified — [Nautilus backtesting docs](https://nautilustrader.io/docs/latest/concepts/backtesting/)
- [DOCS] TradingView broker emulator, for comparison:
  - The earliest fill is "on the next available tick". With default settings, orders from bar t fill at bar t+1's open.
  - Intrabar path: if the open is closer to the high, it assumes open→high→low→close; if closer to the low, open→low→high→close.
  - It assumes no gaps inside a bar for price-based orders. A level crossed in a gap between bars fills at the next bar's open, not at the level.
  - A limit order at a worse-than-market price fills on the next tick.
  - "Bar Magnifier" (`use_bar_magnifier = true`, Premium/Ultimate plans) uses lower-timeframe OHLC, capped at 200,000 intrabar bars, so early history falls back to the heuristics.
  - [TradingView strategies docs](https://www.tradingview.com/pine-script-docs/concepts/strategies/)

### Inferences
- **Matching TradingView in our engine:**
  1. next-bar-open market fills;
  2. the "open-nearest-extreme first" intrabar heuristic for SL/TP;
  3. gap-through fills at the open;
  4. an optional lower-timeframe "magnifier" mode using M1 data.
  
  Also add a **pessimistic mode** (if SL and TP both lie inside the bar, assume SL first) and report both. A strategy whose verdict flips between modes is too sensitive to intrabar ordering, which is common for tight-stop scalps on XAUUSD M1–M15.
- **What to borrow from each:**
  - backtesting.py: compact API, heatmap and optimisation constraints, but AGPL.
  - vectorbt: vectorised parameter sweeps for fast PBO matrices.
  - NautilusTrader: an event-driven core and backtest/live parity for later automation.
  
  Given the licences, writing our own small engine (MIT/Apache) and borrowing *ideas* avoids AGPL/Commons-Clause obligations if the tool is ever distributed or hosted. Not legal advice.
- For TradingView parity checks, run the same strategy in Pine and in our engine on identical data and compare trade lists one-to-one. Most differences come from bar-timestamp convention, the session template, commission/slippage settings and the intrabar path.

### Gaps
- vectorbt PRO's 2026 status, pricing and licence were not checked this session.
- NautilusTrader's exact bar→tick conversion and `FillModel` parameters were not verified (subpage 404).
- QuantConnect LEAN's fill model for CFDs/XAUUSD was not reviewed.
- GitHub stars and commit activity could not be fetched (the GitHub API was blocked in this environment); status is based on PyPI release dates.

---

## 4. Evidence on common retail gold strategies (trend/TSMOM, MA crossovers, breakouts, mean reversion, session/time-of-day effects)

### Takeaway
- **Best evidenced:** slow time-series momentum / trend following on daily-to-monthly horizons. It is peer-reviewed and gold is in the sample, though gold-only statistics were not broken out in what was reviewed.
- **Documented session effects:**
  - overnight positive / daytime negative COMEX returns (peer-reviewed, weakening over time);
  - Asian-hours strength / Western-hours weakness (thesis-level evidence 2001–2018, plus 2026 H1 market data);
  - informed trading around the old London PM fix (peer-reviewed; that mechanism ended in 2015).
- **Intraday MA crossovers:** mixed, with heavy data-mining risk.
- **ORB:** some evidence on equities/ETFs and a crude-oil working paper, but nothing gold-specific, and replications show it is net-zero after costs.
- **Asian-range / London-open breakout and RSI/Bollinger mean reversion on gold:** **folklore**. No peer-reviewed evidence was found.

### Cited Findings

**Trend following / time-series momentum (best evidence)**
- [PEER] Moskowitz, Ooi & Pedersen, "Time Series Momentum", *Journal of Financial Economics* 104 (2012): "We document significant 'time series momentum' in equity index, currency, commodity, and bond futures for each of the 58 liquid instruments we consider." GOLD is one of the commodity futures in their Table 1 sample (1965–2009) — [JFE paper PDF](https://pages.stern.nyu.edu/~lpederse/papers/TimeSeriesMomentum.pdf); [SSRN](https://papers.ssrn.com/abstract=2089463)
- [WP] A CBS thesis notes that the MOP results "do not, however, account for costs associated with strategy execution" — [Bojesen CBS thesis](https://research-api.cbs.dk/ws/portalfiles/portal/60699508/815971_Masters_thesis_final_Magnus_Bojesen.pdf)
- [PEER/PRACT] Hurst, Ooi & Pedersen (AQR), "A Century of Evidence on Trend-Following Investing":
  - an equal-weighted combination of **1-, 3- and 12-month** time-series momentum signals;
  - each market volatility-scaled; the portfolio targets **10% annualised ex-ante volatility**;
  - net of estimated transaction costs and 2-and-20 fees;
  - the 2017 update covers 67 markets (29 commodities) from 1880–2016.
  - [Hurst et al. PDF](https://fairmodel.econ.yale.edu/ec439/hurst.pdf); [AQR page](https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing)
- [PRACT/secondary] Positive net returns in every decade since 1880, with an average Sharpe of about 0.4 after 2/20 fees — [CXO Advisory summary](https://www.cxoadvisory.com/momentum-investing/trend-following-with-intrinsic-momentum-over-the-very-long-run)
- Caveat: these are **diversified portfolio** results. A single-market gold trend system will have a much lower Sharpe ratio and long flat or losing periods. No gold-only Sharpe figure was found in the sources reviewed — [search notes on MOP](https://papers.ssrn.com/abstract=2089463)

**Moving-average crossovers (intraday)**
- [WP] Urquhart et al. (5-min spot gold):
  - standard MA parameters produce significant *losses*;
  - out of 66,297 swept rules, only the SMA family for gold stayed significant out of sample;
  - "longer run averages should be used … on intraday data".
  
  This is a strong data-mining warning. Applying the DSR logic to N = 66,297, survival of one family is weak evidence on its own — [Urquhart et al. PDF](https://c.mql5.com/forextsd/forum/174/does_technical_analysis_beat_the_market__evidence_from_high_frequency_trading_in_gold_and_silver.pdf)
- [PEER, general] Allen & Karjalainen (1999) concluded that technical trading rules do not generate abnormal profits over buy-and-hold after fees. That result comes from the search summary for equities, not gold — [cited in Muruganandan, IJEF 2020](https://iiu.edu.pk/wp-content/uploads/2021/02/IJEF-2020-1-2-02.pdf)

**Session and time-of-day effects**
- [PEER] Blose & Gondhalekar, "Overnight gold returns", *Applied Economics Letters* 21(18), 2014. On COMEX front-month gold, 1985–2012, the overnight return is positive and the daytime return negative. The asymmetry "has weakened substantially over the years" but is still present — [IDEAS/RePEc](https://ideas.repec.org/a/taf/apeclt/v21y2014i18p1269-1272.html)
- [PEER] Blose, Gondhalekar & Kort, "Overnight versus day returns in gold and gold related assets", *Journal of Economics and Finance* 42(3), 2018. The pattern extends to the London fix, gold miners and gold funds/ETFs, "consistent with gold price being (too) high at the opening" — [IDEAS/RePEc](https://ideas.repec.org/a/spr/jecfin/v42y2018i3d10.1007_s12197-017-9403-0.html)
- [WP] Donati & Jung (CBS master's thesis), COMEX GC 5-min, 2001–2018:
  - a "hat-shaped intraday seasonality, with gold appreciating during eastern trading hours in a robust way and depreciating for the rest of the day";
  - "in the years of alleged manipulation gold prices drop around the London fixing times";
  - strategies reach SR up to 1.61 gross but underperform net of costs.
  - [CBS thesis PDF](https://research-api.cbs.dk/ws/portalfiles/portal/59803241/651553_Thesis_Contract_13383.pdf); [CBS record](https://research.cbs.dk/en/studentProjects/gold-price-dynamics-around-the-clock/)
- [PRACT/press, current] H1 2026 (through June 26) gold returns by session: **Asia +12.97%, Europe −1.32%, U.S. −15.08%**. The chart credits Bloomberg, ICE Benchmark Administration and the World Gold Council, and attributes Asian gains to "robust exchange-traded fund inflows". This is one half-year of data, descriptive rather than a tested strategy — [Caixin Global, 2026-07-03](https://www.caixinglobal.com/2026-07-03/analysis-gold-caught-in-a-tug-of-war-between-asian-bulls-and-a-hawkish-fed-102460438.html)
- [PRACT] CME reports growing APAC-hours volume in COMEX gold, with GC trading costs during Asian hours "on a comparable level" to the full day. Only the snippet was reviewed — [CME Group](https://www.cmegroup.com/education/articles-and-reports/comex-gold-futures-and-options-a-look-at-apac-liquidity)
- [PEER] Caminschi & Heaney, "Fixing a leaky fixing", *Journal of Futures Markets* 34(11), 2014, pp. 1003–1039:
  - around the old London PM gold fix, trading volume and volatility in GC futures and GLD rose sharply right after the fix started;
  - there were significant return advantages in the first ~4 minutes;
  - early trades predicted the fix direction, "in some cases exceeding 90%";
  - nothing significant happened after publication.
  
  The fix was replaced by the LBMA Gold Price in March 2015, so this specific leak is **historical** — [IDEAS/RePEc](https://ideas.repec.org/a/wly/jfutmk/v34y2014i11p1003-1039.html); [UWA impact page](https://researchimpact.uwa.edu.au/research-impact-stories/tag/gold/)
- [WP/press] Abrantes-Metz & Metz (2014 draft) reported frequent price spikes around the 3 p.m. London afternoon call from 2004 onward. It was a draft at the time of coverage; its later publication status is unverified — [Mail & Guardian](https://mg.co.za/business/2014-03-03-gold-fix-study-indicates-a-decade-of-manipulation/)
- [PEER] For Chinese gold and silver futures there is a 2025 *Global Finance Journal* paper on the "night effect" of intraday trading. Only metadata was seen — [IDEAS/RePEc](https://ideas.repec.org/a/eee/glofin/v64y2025ics1044028325000110.html)

**Opening range breakout (ORB) / intraday momentum**
- [PEER] Gao, Han, Li & Zhou documented intraday momentum in SPY, 1993–2013: the first half-hour return predicts the last half-hour return, and the effect is stronger on volatile, high-volume and macro-news days. This is equity evidence, not gold — [Alpha Architect summary](https://alphaarchitect.com/2014/08/attention-prop-traders-the-first-half-hour-of-trading-predicts-the-last-half-hour/)
- [PEER, attribution uncertain] A study of Chinese metal futures reportedly found that first-half-hour predictability *disappears* in the day session but appears in the night session. The search snippet did not clearly map this to a specific paper; candidates are [Pacific-Basin Finance Journal 2023](https://ideas.repec.org/a/eee/pacfin/v80y2023ics0927538x2300152x.html) and [Finance Research Letters 2023](https://ideas.repec.org/a/eee/finlet/v58y2023ipas154461232300394x.html). No gold-futures return-predictability study was found.
- [WP] Zarattini & Aziz (2023), "Can Day Trading Really Be Profitable?", tested a 5-minute ORB on QQQ; a later Zarattini, Barbon & Aziz paper tested "Stocks in Play". These are equities, not gold — [CXO Advisory](https://www.cxoadvisory.com/?p=44210)
- [BLOG] Independent replication on index CFDs: gross results reproduced, but zero or negative net of spread and slippage — [MQL5 blog](https://www.mql5.com/en/blogs/post/776235)
- [PRACT] Quantified Strategies concludes ORB strategies "don't work well anymore" — [Quantified Strategies](https://quantifiedstrategies.substack.com/p/opening-range-breakout-trading-strategies)
- [WP] Holmberg, Lönnbark & Lundström (Umeå WP 845, 2012), "Assessing the profitability of intraday opening range breakout strategies": they report ORB returns "significantly higher than zero". Keywords include crude oil futures; the market and sample were not confirmed from the abstract page, and no gold result was found — [S-WoPEc](https://swopec.hhs.se/umnees/abs/umnees0845.htm)

**Asian range / London-open breakout on gold**
- [BLOG] The only reasonably detailed source was a self-published MQL5 backtest:
  - about 3.7 years of real-tick XAUUSD data;
  - profit factor ≈1.38 and max drawdown ≈17%, similar on a second broker's feed;
  - a 2026 OOS slice with PF 1.61 on only 157 trades;
  - what failed: tight stops inside the range, no range-size filter, holding overnight.
  
  No peer-reviewed or audited evidence was found — [MQL5 blog](https://www.mql5.com/en/blogs/post/777540)
- [VENDOR] Expert Advisor marketplace listings (e.g. "London Gold Breakout", "AurumBreak Pro") show unverified backtests. This is marketing — [MQL5 market](https://www.mql5.com/en/market/product/176885)

**Mean reversion (RSI, Bollinger) on gold**
- No gold- or GLD-specific published RSI/Bollinger mean-reversion study was found. Practitioner pages test equity ETFs such as SPY and SMH, not gold, behind paywalls — [Quantified Strategies mean-reversion catalogue](https://www.quantifiedstrategies.com/product-category/mean-reversion-strategies/)
- A Quantra forum user noted that a GLD–GDX spread looked "more trending than mean reverting" — [Quantra forum](https://quantra.quantinsti.com/community/t/mean-reverting-bollinger-band/25699)
- [PEER, general] RSI evidence in equities is mixed:
  - the RSI rule failed even before costs on India's Sensex (Muruganandan 2020) — [IJEF 2020](https://iiu.edu.pk/wp-content/uploads/2021/02/IJEF-2020-1-2-02.pdf);
  - other markets show some significant RSI(21,50) results (Chong et al., per the same search summary).

### Inferences
- **Evidence ranking for templates:**
  1. Daily/weekly trend/TSMOM (peer-reviewed, cross-asset; gold included).
  2. Session/overnight effect (peer-reviewed for COMEX, weakening; thesis and 2026 data consistent; cost-sensitive).
  3. Donchian/MA trend on H4–D1 (family of 1; specific parameters not separately evidenced for gold).
  4. NY-open ORB (equity evidence only; replications net-zero).
  5. Asian-range/London breakout (folklore plus a single blog).
  6. RSI/Bollinger mean reversion (folklore for gold).
  
  The journal should display this evidence tier on each template so users don't confuse "popular" with "proven".
- Gold's documented edges sit mostly at **slow horizons** (trend) or in **session drift** that costs consume. For a retail XAUUSD trader paying roughly $0.15–$0.40 per ounce in spread (typical figure, unverified here), intraday templates should be cost-stressed before anything else.
- Session-effect results are **non-stationary**. The overnight effect weakened over 1985–2012, the fix-related pattern belongs to a pre-2015 regime, and the 2026 Asia/US split is a single half-year. Walk-forward with year-by-year breakdowns is essential.

### Gaps
- No gold-only Sharpe ratio for TSMOM was found in the sources reviewed (MOP figures are per-instrument t-stat charts, not extracted).
- No peer-reviewed study of the Asian-range/London-open breakout, of a NY-open ORB on gold, or of RSI/Bollinger mean reversion on gold was found.
- Practitioner research from Man Group or CME education specific to gold trend following was not retrieved: the Man backtesting page and CME backtesting PDF appeared in results but were not reviewed ([Man Group](https://www.man.com/insights/backtesting); [CME PDF](https://www.cmegroup.com/content/dam/cmegroup/education/files/backtesting.pdf)).
- The findings of the 2025 Chinese gold "night effect" paper were not accessible.

---

## 5. Risk management norms (risk per trade, ATR stops, XAUUSD lot sizing)

### Takeaway
The sizing formula is well established: **lots = (equity × risk%) / (stop distance in $ × ounces per lot)**, with 1 standard XAUUSD lot = 100 oz, so a $1 move = $100 per lot. Broker contract specs vary, especially "pip" definitions. Common practitioner risk levels of 0.5–2% per trade and ATR-multiple stops are conventions, not peer-reviewed findings. The institutional benchmark is volatility targeting (AQR: 10% annualised for a diversified portfolio).

### Cited Findings
- [BLOG/DOCS-ish] On TradingView guides, 1 standard XAUUSD lot = 100 ounces — [TradingView idea: XAUUSD lot size](https://fr.tradingview.com/chart/XAUUSD/j8BFjYVq-How-to-Calculate-Lot-Size-for-Trading-XAUUSD-on-TradingView)
- [BLOG] Lot Size = Risk Amount / (Stop Loss in pips × Pip Value per Lot). One open-source TradingView gold lot calculator uses a $0.10 move as a "pip" ($10 per standard lot). Broker pip definitions differ, so dollar-distance formulas are safer — [TradingView Lot Size Calculator (Gold)](https://in.tradingview.com/script/yiWmzF7p-Lot-Size-Calculator-Gold)
- [PEER/PRACT] Institutional trend following sizes each market by volatility and targets a constant ex-ante portfolio volatility (10% annualised in Hurst/Ooi/Pedersen) — [Hurst et al. PDF](https://fairmodel.econ.yale.edu/ec439/hurst.pdf)
- [PEER] Harvey & Liu caution that "Sharpe ratios do not necessarily control for risk", e.g. option-like negative-skew strategies. Strategies with tight targets and wide stops (common in gold scalping) need skew-aware evaluation, which supports DSR's skew/kurtosis terms — [Harvey & Liu 2015](https://people.duke.edu/~charvey/Research/Published_Papers/P120_Backtesting.PDF)

### Inferences
- **Position sizing for the engine:**
  - `lots = floor_to_step( (equity * r) / (|entry − stop| * contract_oz), lot_step )`
  - `contract_oz = 100` by default, configurable per broker;
  - `lot_step = 0.01` by default;
  - enforce min/max lot and a margin check (`lots * contract_oz * price / leverage ≤ free margin`).
  
  Example: $10,000 equity, 1% risk, $12 stop gives 100 / (12 × 100) = 0.083, which rounds down to 0.08 lots.
- **ATR stop convention** (practitioner, e.g. the "Turtle" N-unit approach; not verified here): stop = k × ATR(14 or 20) on the signal timeframe.
  - k ≈ 1.5–3 for intraday breakout templates;
  - k ≈ 2–3 for daily trend templates.
  
  Combining an ATR stop with fixed-fractional sizing gives volatility-normalised risk per trade.
- **Default risk** of 0.5% per trade (max 1%) for automated retail templates, plus portfolio guards:
  - daily loss limit (e.g. 2–3R);
  - max concurrent risk;
  - a kill-switch when live drawdown exceeds the Monte Carlo 95th-percentile drawdown.
  
  These are engineering defaults, not literature thresholds.

### Gaps
- No peer-reviewed source was retrieved for specific "1–2% risk per trade" norms or ATR multiples; these are practitioner conventions.
- Kelly-criterion literature was not reviewed this session.
- Broker-specific XAUUSD contract specifications (contract size, tick size, swap, margin) need to be read from the user's broker.
