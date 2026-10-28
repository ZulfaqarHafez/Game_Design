# goldlab: a TradingView-style backtester and auto-trader for gold

Backtest XAUUSD strategies with the same fill rules as TradingView's Strategy Tester,
keep a permanent journal of every strategy you try, check whether a result can be trusted,
then run the same code on a paper account and later a broker.

Research behind every design choice: [`../reports/TradingView gold backtest and automation.md`](../reports/TradingView%20gold%20backtest%20and%20automation.md)

## Why not scrape TradingView?

TradingView's Terms of Use (section 3) license its data for display only. They ban automated
collection, "non-display" use including automated trading, and reverse engineering, and TradingView
bans accounts that break this. Its intraday history is also capped at 5k–40k bars depending on plan,
which is only days to weeks of 1-minute gold. So goldlab copies what TradingView **documents** (its
broker emulator rules and metric formulas) and never its data:

| Piece | TradingView | goldlab |
|---|---|---|
| Fill rules | Pine broker emulator | `goldlab/engine/broker.py` (same rules, tested) |
| Metrics | Strategy report | `goldlab/engine/metrics.py` (same definitions) |
| Chart | Lightweight Charts (Apache-2.0) | used as-is in the HTML report |
| Data | proprietary feeds | Dukascopy bid/ask (free, 2003→), Yahoo, your CSVs |
| Strategy language | Pine Script | YAML strategy cards → exported to Pine v6 for cross-checking |
| Alerts | webhooks | `goldlab webhook` receiver (optional) |

## Quick start

```bash
pip install -e .            # numpy, pandas, requests, pyyaml
python -m goldlab list      # the example strategies
python -m goldlab backtest ema_trend_4h --report
python -m goldlab validate donchian_breakout_4h --grid entry_len=40,55,70 exit_len=15,20,30
python -m goldlab pine london_breakout_15m --out london.pine   # paste into TradingView to compare
```

Sample gold data is included in `data/sample/`, so this works offline:

| File | Covers | Notes |
|---|---|---|
| `XAUUSD_1h.csv.gz` | Jan 2019 – Sep 2026 | Dukascopy bid prices with real bid/ask spread; also builds 2h, 4h, daily and weekly bars |
| `XAUUSD_15m.csv.gz` | Jan 2025 – 3 May 2026 | built from Dukascopy 1-minute bid prices; spread taken from the hourly bid/ask data |
| `XAUUSD_5m.csv.gz` | Jan 2025 – 3 May 2026 | same source as the 15m file |

`python -m goldlab data --tf 1h --start 2024-01-01` refreshes data from Dukascopy. The server throttles
hard (HTTP 429, and sometimes refuses connections for a while), so downloads are slow, cached under
`data/cache/`, and resume where they stopped when you run the command again.

## Trade it by hand first: bar replay

If you trade by eye, the website can capture what you do and turn it into a strategy:

1. Press **Replay**, pick a start date (or click a candle). Everything after it is hidden.
2. Step forward bar by bar (→ key or **Next bar**) or press **Play**. Add indicators and draw lines as you go.
3. **Buy** or **Sell** with a lot size, a stop and a target, and note why. Drag the stop and target lines to move them.
   Fills follow the backtester's rules exactly: you act at the bar's close, stops and targets trigger along
   TradingView's in-bar path, with the same spread, commission, slippage and swap.
4. **Finish and review** re-runs your trades on the server and shows the full Strategy Tester report.
5. **Build strategy** (from 3 trades; 10 or more per side works better) checks about 60 chart conditions
   (trend, momentum, breakouts, candle patterns, sessions) at your entries and at the bars you passed on,
   picks the few that best reproduce your entries, takes your usual stop (in ATRs) and target (in R), and writes
   a strategy card. It tells you how many of your entries the card repeats and how it did on all the data.

Also in replay:

- **Size by risk**: pick "Risk % of balance" and the lot size follows your stop distance. Stop presets in ATRs,
  target presets in R.
- **Coach**: "Show the strategy's trades" overlays what the selected strategy did on the same bars, as they are revealed.
- **Report card** after Finish: a grade from your average R, the numbers that matter, and habits worth noticing
  (trades without a stop, stops widened after entry, losers held longer than winners), plus how the strategy
  did over the same bars.
- **All trades** in My sessions is your journal across sessions, with notes, exportable as CSV.
- On a phone the chart stays in view with Sell / Buy / Ticket / Next pinned to the bottom; the order ticket
  opens as a sheet.

How the recording, review and learning fit together: [docs/replay-architecture.md](docs/replay-architecture.md).

Sessions are saved in your browser (**My sessions**). Export one and turn it into a card in the repo:

```
python -m goldlab learn "Replay_1h_from_2025-06-02.json" --name "My pullback setup"
python -m goldlab validate my_pullback_setup.yaml
```

## The analyst: an outlook with its reasoning

The **Outlook** tab is written by an AI analyst (Claude Opus 5.5) from free public data gathered on each run:

- spot gold (gold-api.com) and daily technicals from COMEX gold futures (Yahoo Finance): trend regime, distance to
  the 20/50/200-day EMAs, RSI, ATR, 20-day and 52-week ranges;
- macro drivers from the Federal Reserve's FRED data: 10-year real and nominal yields, inflation breakevens, the broad
  dollar index, VIX, WTI oil, the Fed funds target;
- what every strategy card on the site is doing right now on live bars;
- the last two days of headlines (Google News) on gold, the Fed, central banks and geopolitics.

It answers with a direction, a calibrated confidence, the drivers it weighed (for and against), the news that mattered,
risks, what would change its mind, levels and a plan sketch. Every call is stored and scored against what gold did over
its horizon, so the tab shows a track record. Until `ANTHROPIC_API_KEY` is set, a transparent fixed-weight stand-in
scores the same drivers so the page still works.

Running it: `GET /api/outlook` serves the latest view (and makes one if none exists); `POST /api/outlook?refresh=1`
makes a new one, allowed once an hour by anyone or any time with `Authorization: Bearer $CRON_SECRET` (or `$GSL_PIN`).
A Vercel cron calls it daily. Storage is Vercel Blob on the site (`BLOB_READ_WRITE_TOKEN`) and `data/cache/outlook/`
locally. Optional `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` send a message when the direction changes.
Code: `goldlab/fundamentals.py` (data), `goldlab/analyst.py` (prompt, schema, storage, scoring), `api/outlook.py`.

Not financial advice: the analyst reasons from public data and shows its working so you can disagree.

## Capturing your strategies

Every strategy is a **card**: a short YAML file you can read like a trading plan.

```bash
python -m goldlab new "My London pullback" --tf 15m     # creates strategies/my_london_pullback.yaml
python -m goldlab backtest my_london_pullback --report
```

```yaml
name: My London pullback
timeframe: 15m
params: {fast: 20, slow: 50, atr_mult: 2.0, target_r: 2.0}
vars:
  trend_up: ema(close, slow) > ema(close, slow)[4]
  london: in_session("07:00-11:00", "Europe/London")
long:
  when: london and trend_up and crossover(close, ema(close, fast))
  sl_dist: atr_mult * atr(14)       # stop distance from the fill price
  tp_r: target_r                    # target = 2x the risk
settings: {qty_type: risk_percent, qty_value: 0.5}
```

Every backtest is written to `journal/` automatically:

- `journal/strategies/<name>/<version>.yaml`: every version of every strategy, so you can see how an idea changed
- `journal/runs.jsonl`: one line per run, with the parameters, data range, costs, metrics and monthly returns
- `journal/runs/<id>/`: trades and equity curve
- `python -m goldlab journal` lists strategies; `python -m goldlab journal <slug>` shows a strategy's history
- `python -m goldlab import-tv trades.csv --name "..."` records a strategy you ran on TradingView
  (export it from the Strategy report → List of trades → Download)

Commit `journal/` to git and nothing you tried is ever lost. Counting every trial also matters
statistically: see Validation below.

### Card reference

| Section | Meaning |
|---|---|
| `params` | numbers you may tune (`--grid` sweeps them) |
| `vars` | named expressions, computed once over all bars |
| `long` / `short` | `when` (condition at bar close), `order` (market, stop, limit, stop_limit), `price`, `sl` / `tp` (prices), `sl_dist` / `tp_dist` (distances), `tp_r` (multiple of risk), `trail_dist`, `trail_trigger`, `lots` |
| `exit` | `long_when`, `short_when`, `when` (close at market), `max_bars` |
| `cancel_when` | cancel resting entry orders |
| `oca_entries: true` | when one resting entry fills, cancel the other |
| `settings` | sizing (`qty_type`: lots, units, cash, percent_of_equity, risk_percent) and costs |

Functions follow Pine: `sma ema rma wma hma rsi atr tr stdev highest lowest change roc cci stoch
bb_upper bb_lower bb_mid kc_upper kc_lower macd macd_signal macd_hist adx plus_di minus_di supertrend
supertrend_dir vwap crossover crossunder cross barssince valuewhen abs min max nz`.
Time: `in_session("07:00-11:00", "Europe/London")`, `session_high(...)`, `session_low(...)` (the last
completed range), `hour(tz)`, `weekday(tz)` (Mon=0), `new_day()`.
Higher timeframe: `security("1d", "atr(14)")` uses the last completed daily bar, so it never repaints.
`x[1]` is the previous bar. Live state: `is_flat`, `is_long`, `is_short`, `position`, `bars_in_trade`,
`trades_today`, `entry_price`, `open_profit`.

Expressions are parsed with a whitelist: no imports, attributes or arbitrary code. Negative indexes
(`close[-1]`, which would peek into the future) are rejected.

Anything a card can't express can be written as a Python class (see `goldlab/strategy.py`), using
`self.entry()`, `self.exit()` and `self.close_position()` the way Pine uses `strategy.entry` and friends.

## How fills work (TradingView's rules)

- The strategy runs at each bar's **close**; its orders fill on the **next** bar. Market orders fill at the next open.
- Inside a bar, price is assumed to go open → nearer extreme → other extreme → close. Stops and targets
  fill in the order that path touches them, so an entry and its exit can happen in the same bar.
- A gap through an order's price fills at the open. Slippage (in ticks) applies to market and stop fills, never to limits.
- `--preset tradingview`: no spread or costs, like a default `strategy()`. Use it to compare numbers with TradingView.
- `--preset realistic` (default): real bid/ask spread from the data (buys on the ask, sells on the bid),
  $3.50 per lot per side commission, $0.05 slippage, overnight swap (−$40 per lot long, −$5 short, triple on Wednesday)
  and 5% margin. Swap alone can turn a swing strategy from profit to loss.
- `--magnifier` resolves fills on lower-timeframe bars (TradingView's "Bar detalization").
- `intrabar: pessimistic` assumes the stop is always hit before the target (used in validation).

## Validation: is it ready to automate?

`python -m goldlab validate <strategy> [--grid ...]` runs these checks and writes a report:

| Check | Pass rule |
|---|---|
| Enough trades | ≥ 100 closed trades |
| Profitable after costs | profit factor ≥ 1.2 with spread, commission, slippage and swap |
| Account size fits | no signals skipped for being under 0.01 lot |
| Survives 1.5× costs | still profitable |
| Pessimistic fills | still profitable when stops always fill first |
| Recent out-of-sample | the last 30% keeps ≥ 50% of the earlier profit rate |
| Monte Carlo | 5th percentile of 5,000 reshuffled trade orders still ends above the start |
| Parameter stability | ±20% on each parameter keeps ≥ 70% of the profit |
| No look-ahead | orders on each bar are identical when later bars are deleted |
| Walk-forward | efficiency ≥ 0.5 and ≥ 60% of test windows profitable |
| Deflated Sharpe | ≥ 0.95 after counting every variant in the journal (Bailey & López de Prado 2014) |
| Overfitting (PBO) | ≤ 0.05 across recorded variants (Bailey et al. 2017) |
| Enough history | years of data ≥ the minimum backtest length for the number of trials |

The verdict is never "go live". At best it's "ready for paper trading".

## Automating: paper first

```bash
cp live.example.yaml live.yaml           # edit risk limits; secrets come from env vars
python -m goldlab paper ema_trend_4h     # paper account, prices from Yahoo (no account needed)
python -m goldlab paper ema_trend_4h --broker oanda   # OANDA practice account (export OANDA_TOKEN=...)
```

The live runner replays the **same strategy code** through the backtest engine at every bar close and
mirrors what it wants to the broker: market entries, resting stop/limit orders, the stop and target of the
open trade (including trailing), and exits. A rehearsal test replays historical bars through the runner and
a paper account and checks it takes the same trades at the same prices as the backtest.

Safety rails (in `live.yaml`): maximum lots, maximum daily loss (flattens and stops for the day), orders per
day, maximum spread, trading window, news blackout list (`news_blackout.yaml`), a broker-side stop on every
entry, and a kill switch (`touch KILL` flattens and blocks new orders). Every decision is logged to
`journal/live/<strategy>/audit.jsonl`. Live accounts are refused until you set
`i_understand_this_trades_real_money: true`.

Brokers:
- **OANDA v20** (`--broker oanda`): REST, works on Linux, free practice account. A good first choice for a
  Singapore resident (OANDA Asia Pacific is MAS-licensed). Confirm your account has API access and XAU_USD.
- **MetaTrader 5** (`--broker mt5`): most gold CFD brokers. Needs Windows and the MT5 terminal running (a Windows VPS).
- **TradingView alerts** (`python -m goldlab webhook`): keep your Pine strategy on TradingView and let alerts
  drive the broker. It needs a paid TradingView plan with 2FA, HTTPS on port 443, and this alert message:

  ```json
  {"secret": "<GOLDLAB_WEBHOOK_SECRET>", "id": "{{strategy.order.id}}-{{time}}", "time": "{{timenow}}",
   "action": "{{strategy.order.action}}", "target_position": {{strategy.position_size}}}
  ```

  The receiver answers within TradingView's 3-second limit, accepts only TradingView's four IP addresses,
  rejects stale or duplicate alerts, and trades toward the target position, so one lost alert corrects itself.

Suggested path: backtest → validate → paper trade 4–8 weeks and compare with the backtest →
OANDA practice → smallest live size.

## Website

`python -m goldlab site --out public` builds a static site: an index of every strategy card
(yours in `strategies/` first, then the examples), a full report page per strategy with its readiness
checklist, and the research report. It's deployed on Vercel from this repo (`../vercel.json`). Each
deploy runs `scripts/vercel_build.sh`, which rebuilds the site with Python. If that fails, Vercel serves
the copy committed in `public/`, so run `python -m goldlab site` before you commit to keep it current.

`python -m goldlab serve` previews the site with a working backtest API on http://localhost:8000.

The backtester page has TradingView-style chart tools:

- **Indicators**: SMA, EMA, WMA, Bollinger Bands, Keltner and Donchian channels, VWAP, Supertrend on the price;
  RSI, MACD, Stochastic, ATR, ADX/DMI, CCI and volume in their own panes. `web/ta.js` mirrors
  `goldlab/indicators.py`, and a test checks they agree to 1e-9.
- **Drawing**: trend line, ray, horizontal and vertical lines, rectangle, Fibonacci retracement, long and short
  position (risk/reward) and text. Drag points to adjust, Delete to remove, Ctrl+Z to undo, magnet to snap to
  candle prices. Drawings are pinned to time and price, so they stay in place across timeframes.
- **Replay** and **My sessions**: see "Trade it by hand first" above.
- **Share link** (under Rules): the whole strategy card travels in the URL, so a link opens the same rules anywhere.
- **Theme** button in the header: follows your device, or light / dark.
- **?** opens every shortcut. On a phone, add the page to your home screen: it opens full-screen and the chart
  library and fonts stay cached (`web/sw.js`, `web/manifest.json`).

Speed: a result carries the last 3,000 bars as integer deltas (about 25 KB compressed); older bars load as
you scroll left. `tests/e2e/run.cjs` has a speed test with budgets.

### Testing the website

```
python -m pytest                                   # engine, rules, live trading and API (every strategy × timeframe × cost model)
node tests/e2e/run.cjs                             # every feature of the page in a real browser, phone and desktop, light and dark
ONLY=mobile,a11y node tests/e2e/run.cjs            # just the tests whose name contains these words
BASE=https://gold-strategy-lab-eight.vercel.app/ node tests/e2e/run.cjs   # the live site
```

The browser tests need Node and Playwright with Chromium. They check results against the API, keyboard
use, screen-reader landmarks (axe-core), 44px tap targets, error and empty states, and page speed.

## The example strategies

| Card | TF | Evidence |
|---|---|---|
| `tsmom_daily` | 1d | Peer-reviewed: time-series momentum (Moskowitz, Ooi & Pedersen 2012) |
| `ema_trend_4h`, `donchian_breakout_4h` | 4h | Trend family, peer-reviewed for futures portfolios; gold parameters unproven |
| `asia_session_drift_1h` | 1h | Documented time-of-day effect, but cost sensitive |
| `london_breakout_15m`, `ny_orb_5m` | 15m / 5m | Folklore and blog backtests only |
| `rsi2_mean_reversion_1h` | 1h | No gold-specific evidence |

They are templates to learn the format, not recommendations. Several lose money after realistic costs, which is the point of checking.

## Layout

```
goldlab/
  data/        dukascopy.py (bid/ask download + cache), yahoo.py, csv_io.py (TradingView CSV), resample.py
  engine/      broker.py (TradingView fill rules), backtest.py, metrics.py
  indicators.py  Pine ta.* equivalents          rules.py   strategy cards
  strategy.py    Python strategy base class      pine.py    card -> Pine v6
  journal.py     strategy and run history        validate.py  checks above
  manual.py      replayed manual trades          learn.py     manual trades -> strategy card
  fundamentals.py  free macro, price and news data  analyst.py   the outlook (Claude), storage, scoring
  report.py      HTML report (Lightweight Charts)
  webapi.py      the website's API (backtest, validate, pine, bars, manual, learn)
web/           the backtester page: app.js, ta.js (indicator maths), indicators.js, draw.js, replay.js
  live/        runner.py, risk.py, webhook.py, brokers/ (paper, oanda, mt5)
strategies/    your cards (examples/ holds the templates)
journal/       everything you've tried (commit it)
tests/         python -m pytest; e2e/run.cjs drives the website in a browser
```

Not financial advice. Leveraged gold CFDs can lose more than you expect; in Singapore, brokers must put
you through a Customer Knowledge Assessment before you can trade them.
