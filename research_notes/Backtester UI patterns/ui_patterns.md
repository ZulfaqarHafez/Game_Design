# Backtester UI patterns for a gold (XAUUSD) web backtester

Research date: 25 Oct 2026. Sources are cited inline. Vendor pages describe their own products, and competitor claims are flagged as such. Reddit was unreachable from this environment, so user feedback in section 5 comes from Trustpilot, reviews and reader comments.

## 1. TradingView strategy report (formerly Strategy Tester)

- **July 2026 changes.** The release notes rename the Strategy Tester to the "strategy report".
  - A new **Script execution** menu, and a **Bar detalization** menu that replaces Bar Magnifier. Both sit in Settings/Properties and at the top of the report.
  - New dropdowns for "Limit order execution", "Order execution delay" and Long/Short leverage.

  https://www.tradingview.com/pine-script-docs/release-notes/
- **Placement.** The report docks in the bottom panel and opens automatically when a strategy is added. Only one strategy runs per chart. https://www.tradingview.com/support/solutions/43000764138-tradingview-strategy-report-how-to-start/
- **Structure.** Icons in the top-left switch between **Metrics** and **Trades**. Metrics has five sections:
  - **Key stats:** P&L, max drawdown, profitable trades, profit factor, plus an equity chart.
  - **Return details:** Returns, Benchmarking and Risk-adjusted sub-tabs.
  - **Trades analysis:** results for all, long and short trades.
  - **Equity run-ups and drawdowns.**
  - **Capital efficiency.**

  **Properties** appears only on published strategies, with collapsible Date range, Symbol info, Inputs and Properties sections. https://www.tradingview.com/pine-script-docs/concepts/strategies/
- **The help centre describes extra sub-views.** Breakdown, Periodical, Benchmarking, Growth and decline, a return histogram, Streaks, and **Time patterns** by hour, weekday or month. List-of-trades columns: #, Type, Date/Time, Signal, Price, Size, Net P&L, Run-up, Drawdown, Cumulative P&L. https://www.tradingview.com/support/solutions/43000764138-tradingview-strategy-report-how-to-start/
- **Legacy tabs.** Overview, Performance, Trades analysis, Risk/performance ratios and List of trades survive in the Replay Trading panel. https://th.tradingview.com/support/solutions/43000691889/
- **Trade-to-chart link.** Hovering an entry or exit cell shows **"Show on chart"**, which scrolls the chart to that bar. It is unavailable in Deep Backtesting. https://www.tradingview.com/pine-script-docs/concepts/strategies/
- **Date range.** A **"Testing period"** menu tops the Metrics tab. Picking any non-default period switches on Deep Backtesting (pink icon); users then press **Update report** after edits and **Reset to chart session** to leave it.
  - Deep Backtesting results show only in the report, not on the chart, and need Premium or above.
  - Otherwise the report keeps only the latest 9,000 trades.

  https://www.tradingview.com/support/solutions/43000666265-how-deep-backtesting-works/
- **Settings dialog.** Tabs are Inputs, Properties, Style and Visibility. Inputs use `group` headers, `inline` rows, `tooltip` "?" icons, `confirm` (prompt when the strategy is added) and `active` (dims a dependent field). https://www.tradingview.com/pine-script-docs/concepts/inputs/
- **Mobile.** No official doc covers the report in the phone apps. Third-party guides say mobile has Bar Replay but not the full tester (unverified). https://finestel.com/blog/how-to-backtest-on-tradingview/

## 2. TradingView Bar Replay

- **Controls.**
  - Start point: "Select bar" (a blue line with a scissors cursor), "Select date…", first available day, or "Random bar".
  - Playback: Play/Pause (Shift+↓), Forward one step (Shift+→), a speed menu.
  - Exit: "Jump to real-time chart", or close with X.
  - Sessions are restored on re-entry, and multi-chart layouts stay time-synced.

  https://www.tradingview.com/support/solutions/43000712747-bar-replay-how-and-why-to-test-a-strategy-in-the-past/
- **Replay interval (Feb 2025).** A selector next to the speed menu sets the data added per tick, for example 1-minute steps on a 1h chart. https://www.tradingview.com/blog/en/intervals-in-bar-replay-50381
- **Trading in replay.**
  - Setup: set capital, currency and commission before Play.
  - Order entry: Buy/Sell at the top-left of the chart, the "+" menu, or the Order Ticket. Market, limit, stop and stop-limit orders are supported.
  - On the chart: drag TP/SL brackets, use the close and reverse buttons, see arrows at executions and P/L inside the position.
  - Results: an end-of-session popup and report. **Results are not saved.**

  https://th.tradingview.com/support/solutions/43000691889/
- **Plan limits.** Intraday depth depends on the plan, and older start points show "Data point unavailable". https://chartwatch.tv/tradingview-bar-replay
- **Mobile.** Bar Replay is in the phone app (slider icon → Bar Replay → tap a start point). https://optimusfutures.com/blog/master-the-bar-replay-tool-on-tradingview-mobile-tradingview-mobiletrading-trading/

## 3. Manual-backtesting products

- **FX Replay.**
  - Navigation: go-to buttons for the next day's open, a session, a price level, a news event or a position close.
  - Order panel: risk % of the initial or current balance, SL/TP toggles, estimated P/L. Analytics: P&L curve, win rate, by-hour stats, calendar, Monte Carlo. https://www.fxreplay.com/campaigns/backtest
  - SL/TP lines: ghost SL (orange) and TP (green) lines appear after an order. While dragging they show live $, pips and %; releasing locks the level with a toast. https://support.fxreplay.com/articles/how-to-drag-and-place-stop-loss-take-profit-on-the-chart
  - Hotkeys: Alt+1 play/pause, Ctrl+Space next candle, Alt+2/3 speed. https://support.fxreplay.com/articles/available-hotkeys-for-fx-replay
  - Journal: tied to the session, opened from a button. https://support.fxreplay.com/articles/trades-and-logging
- **TradeZella.**
  - Session setup: symbols, balance, date range, and an attached Strategy that auto-tags trades.
  - Playback: Space play/pause, **arrow keys step forward and back**, Go-To a date, candle or session.
  - Orders: "Advanced Order" sizes the position from risk % or $ and the stop distance. SL/TP are set by price, $ or %, or dragged. Auto-breakeven triggers at R, and partial closes are 25/50/75%.
  - Journal: setup and mistake tags, notes. https://www.tradezella.com/blog/backtest-with-tradezella
  - Competitor claim: FX Replay's journal opens in a separate window, while TradeZella's sits in a column beside the chart. https://www.tradezella.com/blog/fx-replay
- **TradesViz.** One chart or 4 charts, an in-chart order box, draggable orders, and flatten/reverse/double buttons. Live P&L sits under Buy/Sell, a trades table sits below the chart, and every trade is journaled. https://www.tradesviz.com/blog/all-simulators-guide/
- **Forex Tester Online.** "New Order" on the top panel, a "jump to" control, and Analytics at the bottom-left. https://forextester.com/blog/how-to-use-forex-tester-online/

## 4. Rule-based backtest UIs

- **TrendSpider.**
  - Inputs: entry/exit conditions, an AI builder, and "AI Explain" for results. https://help.trendspider.com/kb/strategy-tester/what-is-the-strategy-tester
  - The **Group Strategy Tester** pairs a config panel (strategies × timeframes × symbols) with a variant table where **each column is heat-mapped** (drawdown inverted), plus R/R-vs-Win% bubble charts with a "no-go" zone. https://help.trendspider.com/kb/strategy-tester/strategy-variance-explorer
- **QuantConnect results page.**
  - A stats banner and toggleable Equity, Drawdown, Benchmark and Exposure charts that share 1m/3m/1y/All zoom.
  - Tabs: Overview (overall and rolling stats), Orders, Trades, Logs, Code, Report.
  - Backtests can be renamed or cloned. https://www.quantconnect.com/docs/v2/cloud-platform/backtesting/results
- **QuantConnect optimization.** Equity curves of every run are overlaid. Results plot as a scatter for 1 parameter, a **heatmap for 2** and 3D for 3, where similar-coloured neighbouring cells mean stable parameters. Clicking a table row opens that run. https://www.quantconnect.com/docs/v2/cloud-platform/optimization/results
- **Composer (no-code).** Preview stats in the editor, a 1-year default window, "Add Benchmarks" under the chart, and detailed metrics below it. https://help.composer.trade/article/215-7-how-do-backtests-work-in-composer
- **MetaTrader 5.** 2D/3D optimization graphs and a forward-test split. https://www.metatrader5.com/en/automated-trading/strategy-tester
- **Choosing parameters.** Pick from the middle of a plateau, not the best single cell. https://www.luxalgo.com/library/concept/parameter-stability/

## 5. User praise and complaints

- **TradingView.**
  - Deep-backtest trades never reach the chart and don't match the chart's trades. https://www.tradingview.com/support/solutions/43000670566-why-are-the-results-of-deep-backtesting-not-shown-on-the-chart/
  - Readers cite bar limits by plan, no easy risk-% sizing, and inflated win rates from unclosed-bar logic. https://finestel.com/blog/how-to-backtest-on-tradingview/
  - There is no built-in optimizer, so third-party add-ons fill the gap. https://addons.mozilla.org/en-US/firefox/addon/strategy-optimizer/
  - Replay trades aren't saved. https://chartwatch.tv/tradingview-bar-replay
- **FX Replay.** Praised for its "Trading View look and feel" and journaling. Criticised for lag, freezes and price. https://www.trustpilot.com/review/fxreplay.com?page=9
- **Forex Tester.** 2026 reviews report a weak chart, crosshair bugs and freezes, which the company acknowledged. https://ca.trustpilot.com/review/forextester.com
- **Mobile.** Multi-timeframe setups and many filters are hard to read on phones, and builders are "optimized for desktop". https://backtrex.com/en/blog/free-backtesting-app-android-mobile

Takeaways: link every trade to the chart, persist sessions, size from risk %, and design phone-first.

## 6. Legal caution (brief, not legal advice)

- **US copyright.** Menu hierarchies are an unprotectable "method of operation" (*Lotus v. Borland*). https://en.wikipedia.org/wiki/Lotus_Development_Corp._v._Borland_International,_Inc. Look and feel is analysed element by element, with generic ideas filtered out (*Apple v. Microsoft*). https://law.justia.com/cases/federal/appellate-courts/F3/35/1435/605245/
- **EU copyright.** An original GUI can be protected (CJEU C-393/09). https://www.fieldfisher.com/en/insights/graphical-user-interfaces-can-be-protected-by-copyright-rules-european-court
- **Trade dress.** Unregistered design trade dress needs secondary meaning and must be non-functional. https://bannerwitcoff.com/media/_docs/library/articles/TradeDressCases.pdf
- **What this means.** Reusing generic patterns (a results dock, tabs, KPI tiles, draggable SL/TP) is low risk. Copying pixel layouts, icons, colours, exact wording or brand names/logos is not.
- **Lightweight Charts.** Apache 2.0, plus the NOTICE attribution and a visible link to tradingview.com; the `attributionLogo` option satisfies the link. https://unpkg.com/lightweight-charts@5.0.7/README.md

## 7. Recommended UI spec

**Desktop (≥1024px)**
- **Top bar.** XAUUSD label, timeframe toggle (5m/15m/1h/4h/1D), date range (6M/1Y/3Y/All/custom), mode **Backtest | Replay**, **Run** button, run status.
- **Left rail (~300px).** Strategy cards. The selected card expands into a parameter form:
  - Groups: Entry, Exit & stops, Risk, Filters, Costs.
  - Paired fields on one row (fast/slow EMA), with steppers, units, "?" tooltips and reset.
  - Fields that depend on an off toggle are dimmed.
- **Centre.** The chart shows candles, overlays and trade markers. The selected trade gets entry, SL, TP and exit lines plus a shaded holding span. Attribution is always visible.
- **Bottom dock (resizable, collapsible), results tabs:**
  1. **Overview:** KPI tiles (net profit $/%, max DD, win rate, PF, trades, avg trade, Sharpe/Sortino), equity curve with underwater drawdown, buy-and-hold toggle, readiness badge.
  2. **Performance:** All/Long/Short table (gross P/L, costs, expectancy, avg R, largest win/loss, bars held).
  3. **Trades analysis:** R histogram, streaks, hour × weekday heatmap with Asia/London/NY bands.
  4. **Monthly:** year × month returns heatmap with year totals.
  5. **Trades:** sortable, filterable list (#, side, entry/exit time and price, lots, $, R, MAE/MFE, cumulative) with CSV export.
  6. **Readiness:** pass/warn/fail cards (cost stress, walk-forward, Monte Carlo, sensitivity, minimum trades), each with a reason and details.
  7. **Properties:** a frozen snapshot of the run settings for reproducibility.

**Mobile (<768px)**
- Header with scrollable timeframe chips and a range chip. The chart takes about 45% of screen height.
- Results live in a **bottom sheet** with snap points (KPI strip / half / full). Tabs become chips: Overview, Trades, Monthly, Readiness, More.
- Trades show as **cards** (side, date, R, $).
- Strategy editing opens a full-screen sheet with a sticky **Run** button.
- Bottom nav: Chart · Results · Strategy · Replay · Runs.
- Targets ≥44pt/48dp (https://api.flutter.dev/flutter/flutter_test/iOSTapTargetGuideline-constant.html). Landscape switches to chart + side panel.

**Key interactions**
- Tapping a trade (row, card or chart marker) zooms the chart to entry→exit, draws its levels and highlights it. ←/→ or swipe moves to the previous or next trade.
- Tapping an equity point jumps to that trade. Tapping a month cell filters Trades.
- Editing a parameter marks results **stale**: a banner reads "Results are for previous settings — Run".
- Runs are auto-saved. Pin one as the **baseline** and KPI tiles show the change against it.
- Replay controls: jump (date / random / next session open), play-pause, step ±1 bar, speed 0.5–10x, replay interval, exit.
- Replay order ticket: Buy/Sell, risk %, SL from an ATR multiple or by dragging, TP chips (1R/2R/3R), computed lots and $ risk, breakeven at xR.
- Replay chart and stats: drag SL/TP lines with a live $/R readout. A session strip shows balance, P&L, win rate, avg R and DD.
- Replay journal: setup, mistake and session tags plus notes. Sessions auto-save and feed the same tabs, marked "manual".
- On mobile, replay controls sit in the bottom thumb zone.

**Must have vs later**
- **Must:** timeframe, range and Run controls; grouped parameters with the stale banner; chart markers; the six core tabs plus Properties; trade→chart jump; mobile sheet and cards; saved runs; CSV export; attribution.
- **Later:**
  - Run comparison.
  - A 2-parameter optimization heatmap.
  - Replay mode (MVP: play, step, speed, jump, risk ticket, draggable SL/TP, session save).
  - Journal screenshots, step-back, keyboard shortcuts, Monte Carlo fan chart, share links.
