# TradingView Pine Script Strategy Tester (Broker Emulator): Fill Rules and Metric Formulas

Scope: how TradingView's broker emulator simulates fills, and how the strategy report (formerly "Strategy Tester") computes its metrics, as of October 2026 (Pine Script v6 is current). Primary sources: the Pine Script v6 User Manual (Strategies page, Declaration statements page, Strategies FAQ, v6 migration guide, release notes) and TradingView Help Center articles. All docs were retrieved 2026-10-25. Community claims are labelled as such.

Short URL key, written out in full in every citation:
- Strategies page = https://www.tradingview.com/pine-script-docs/concepts/strategies/
- Declaration statements page = https://www.tradingview.com/pine-script-docs/language/declaration-statements/
- Strategies FAQ = https://www.tradingview.com/pine-script-docs/faq/strategies/

---

## Q1. Order execution timing: when do market orders fill, and what do process_orders_on_close, calc_on_every_tick, calc_on_order_fills, calc_on_every_history_tick and fill_orders_on_standard_ohlc change?

### Takeaway
By default a strategy runs once per bar, at the bar's close. Orders it places there have a one-tick delay, so the earliest fill for a market order is the **open of the next bar**. `process_orders_on_close=true` removes that delay for orders created on the closing tick, so they fill at the same bar's close. The `calc_on_*` options add extra script executions inside bars: realtime ticks, order fills, and (new in July 2026) historical intrabar ticks. Each of these can introduce repainting or lookahead bias.

### Cited Findings
- On historical bars the broker emulator "executes orders on historical bars after a bar closes", using only chart data by default. — [Strategies page, Broker emulator](https://www.tradingview.com/pine-script-docs/concepts/strategies/#broker-emulator)
- "By default, the earliest point at which the broker emulator fills an order is on the next available tick, because creating and filling an order on the same tick is unrealistic. If a strategy uses the default calculation behavior, it updates its calculations only after a bar closes, meaning the next tick on which an order can fill is at the open of the following bar." Worked example: signal on bar 20 → fill at open of bar 21. Close placed on bar 21 → fill at open of bar 22. — [Strategies page, Orders and trades](https://www.tradingview.com/pine-script-docs/concepts/strategies/#orders-and-trades)
- A market order is always executed "on the next available tick". — [Strategies page, Market orders](https://www.tradingview.com/pine-script-docs/concepts/strategies/#market-orders)
- "Unless otherwise specified, a strategy script executes strictly once per closed bar, regardless of whether a bar is part of the historical dataset or a new bar from the realtime data feed... each new order in the strategy's simulation has a one-tick delay by default." — [Strategies page, Altering calculation behavior](https://www.tradingview.com/pine-script-docs/concepts/strategies/#altering-calculation-behavior)
- **process_orders_on_close**: "If the value is true, the broker emulator can fill orders created on a bar's close immediately, on the same tick, rather than waiting for the next available tick. If the value is false (the default), the earliest point... is on the next tick, at the open of the following bar." It "does not affect the execution of orders that a strategy places before a bar's closing tick". The UI control is now the "Order execution delay" dropdown, where "None" means zero delay. — [Strategies page, process_orders_on_close](https://www.tradingview.com/pine-script-docs/concepts/strategies/#process_orders_on_close)
- `strategy.close()` and `strategy.close_all()` take an `immediately` parameter. When it is true, the closing market order fills on the same tick the command is called, without changing how other orders are handled. — [Strategies page, process_orders_on_close](https://www.tradingview.com/pine-script-docs/concepts/strategies/#process_orders_on_close); [Strategies FAQ](https://www.tradingview.com/pine-script-docs/faq/strategies/#why-are-my-orders-executed-on-the-bar-following-my-triggers)
- Help Center description of the same option: when "On bar close" is on, the strategy makes "an additional attempt to execute orders after a bar closes and strategy calculations are completed. If the orders are market orders, the broker emulator executes them before the next bar's open. If the orders are price-dependent, they will only be filled if the price conditions are met." — [Help Center: Strategy properties](https://www.tradingview.com/support/solutions/43000628599-strategy-properties/)
- **calc_on_every_tick** (default false) makes the script execute on every realtime tick. It "does not affect the behavior of strategies on historical bars". Because historical bars carry no tick data after a reload, the strategy repaints. — [Strategies page, calc_on_every_tick](https://www.tradingview.com/pine-script-docs/concepts/strategies/#calc_on_every_tick); [Help Center: Strategy properties](https://www.tradingview.com/support/solutions/43000628599-strategy-properties/)
- **calc_on_order_fills** (default false) adds an extra execution "on each tick where the broker emulator fills an order", on both historical and realtime bars. On historical bars, `high`, `low`, `close` and `volume` already hold the bar's final values during those intrabar executions. The doc's example shows how this creates lookahead bias: exits land "at the bar's exact high". The report shows a warning banner when this setting is active. — [Strategies page, calc_on_order_fills](https://www.tradingview.com/pine-script-docs/concepts/strategies/#calc_on_order_fills)
- **calc_on_every_history_tick** (new parameter, July 2026) makes the script "execute once for each available tick in every historical bar". OHLCV built-ins update tick by tick to approximate the developing bar. It is available only on Premium/Ultimate plans and only on standard chart types; `barstate.isconfirmed` stays true on historical bars. When historical detail is set to default (not "High"), each historical bar has 4 ticks along the assumed OHLC path. For example, if the second tick is the high, `ohlc4` = (open+open+high+high)/4 on that tick. — [Strategies page, calc_on_every_history_tick](https://www.tradingview.com/pine-script-docs/concepts/strategies/#calc_on_every_history_tick); [Release notes, July 2026](https://www.tradingview.com/pine-script-docs/release-notes/)
- **fill_orders_on_standard_ohlc**: on Heikin Ashi charts, fills use real OHLC instead of synthetic HA prices. In the UI this is now the "Heikin Ashi mode" → "Standard bars" option. It has no effect on Renko, Kagi, line break, P&F or range charts, because those also distort time. — [Strategies page, Applying a strategy to a chart](https://www.tradingview.com/pine-script-docs/concepts/strategies/#applying-a-strategy-to-a-chart); [Strategies FAQ](https://www.tradingview.com/pine-script-docs/faq/strategies/#why-is-backtesting-on-heikin-ashi-and-other-non-standard-charts-not-recommended)
- A market order can be cancelled only within the same script execution that placed it. By the next execution it has already filled at the next bar's open. — [Strategies page, strategy.cancel()](https://www.tradingview.com/pine-script-docs/concepts/strategies/#strategycancel-and-strategycancel_all)
- Strategy `alert()` calls fire only at bar close by default. Order-fill alerts fire immediately, whatever the execution settings. — [Strategies page, Strategy alerts](https://www.tradingview.com/pine-script-docs/concepts/strategies/#strategy-alerts)

### Inferences
- Default reproduction rule: evaluate signals on bar *t* using bar *t*'s final OHLC. Market orders (entry, close, close_all, reversals) fill at `open[t+1]`, adjusted by slippage. Price orders (limit/stop/exit brackets) placed on bar *t* become eligible from bar *t+1*, starting at its open.
- With `process_orders_on_close=true`, market orders placed at bar *t* fill at `close[t]`. Our engine needs a per-strategy flag and a per-call `immediately` flag for close orders.
- `calc_on_order_fills` cannot be reproduced faithfully from OHLC data without copying TradingView's lookahead artefact. Our backtester should either refuse it or flag results as optimistic.

### Gaps
- The docs don't say whether a price order placed with `process_orders_on_close=true` can also be checked against the *next* bar's path in the same pass. Presumably it simply carries over.
- The exact price used for a market order filled "before the next bar's open" under process_orders_on_close is not stated. The docs imply the bar's close.

---

## Q2. Intrabar price-path assumption, resolution of multiple orders inside one bar, and the Bar Magnifier ("Bar detalization")

### Takeaway
Without lower-timeframe data, the emulator assumes the path is open → whichever of high/low is **nearer to the open** → the other extreme → close. Prices inside the bar are continuous, with no gaps. Price-based orders are filled in the order the path reaches them. "High" bar detalization (formerly "Bar Magnifier", `use_bar_magnifier=true`) replaces this assumption with OHLC from a lower timeframe chosen by a fixed table. It requires a Premium or Ultimate plan and covers at most 200,000 lower-timeframe bars.

### Cited Findings
- Path rule: "If the opening price of a bar is closer to the high than it is to the low, the emulator assumes that the market price moved in this order: open → high → low → close. If the opening price of a bar is closer to the low than it is to the high... open → low → high → close." — [Strategies page, Broker emulator](https://www.tradingview.com/pine-script-docs/concepts/strategies/#broker-emulator)
- "When filling price-based orders (all orders except market orders), the emulator assumes that no gaps exist inside each chart bar; it considers any price within the bar's range as a valid level for filling pending orders." — [Strategies page, Broker emulator](https://www.tradingview.com/pine-script-docs/concepts/strategies/#broker-emulator)
- Gaps between bars: if price crosses an order level between one bar's close and the next bar's open, "the emulator fills the order at the opening price of the bar following the gap" rather than at the order price. — [Strategies page, Broker emulator](https://www.tradingview.com/pine-script-docs/concepts/strategies/#broker-emulator)
- Path consequence (doc example): on a bar whose open is nearer the high, a long limit entry triggered on the way down to the low cannot also fill a take-profit above it on that bar, because the assumed path never comes back up. With bar magnifier on, the daily sub-bars show that it did, and both orders fill in the same weekly bar. — [Strategies page, Adjusting historical bar detail](https://www.tradingview.com/pine-script-docs/concepts/strategies/#adjusting-historical-bar-detail)
- Exits can fill on the entry bar if the exit is a price order: "If the entry command also sets stop-loss or take-profit orders to trigger an exit when certain price levels are reached, then the trade can exit during the same bar that it opens." Otherwise an exit condition on the entry bar fills at the next bar's open. — [Strategies FAQ](https://www.tradingview.com/pine-script-docs/faq/strategies/#how-can-i-exit-a-trade-in-the-same-bar-as-it-opens)
- Stop/limit orders "can execute orders partway through a bar... on both realtime and historical data", without `calc_on_every_tick`. — [Strategies FAQ](https://www.tradingview.com/pine-script-docs/faq/strategies/#how-can-i-execute-a-trade-partway-through-a-bar)
- **High bar detail / Bar Magnifier**: "Users with Premium and Ultimate plans can override the broker emulator's chart-based assumptions... select the 'High' option from the strategy's Bar detalization settings... or `use_bar_magnifier = true`." The emulator "retrieves open, high, low, and close prices from the bars on a suitable lower timeframe". — [Strategies page, Adjusting historical bar detail](https://www.tradingview.com/pine-script-docs/concepts/strategies/#adjusting-historical-bar-detail)
- "High historical bar detail is available only to accounts with Premium and Ultimate plans. Lower-tier plans cannot use it, regardless of whether the declaration statement includes use_bar_magnifier = true." — [Declaration statements page, use_bar_magnifier](https://www.tradingview.com/pine-script-docs/language/declaration-statements/#use_bar_magnifier)
- Rename (July 2026): "The former 'Using bar magnifier' checkbox has been changed to a new Bar detalization menu... This menu replaces the Bar Magnifier feature." — [Release notes, July 2026](https://www.tradingview.com/pine-script-docs/release-notes/)
- Lower-timeframe mapping table. Each row covers the chart timeframe listed and everything up to the next row:

  | Chart TF | Intrabar TF |
  |---|---|
  | 1T | 1T |
  | 100T | 10T |
  | 1000T | 100T |
  | 1S | 1S |
  | 30S | 5S |
  | 1 | 10S |
  | 5 | 30S |
  | 10 | 1 |
  | 15 | 2 |
  | 30 | 5 |
  | 60 | 10 |
  | 240 | 30 |
  | 1D | 60 |
  | 3D | 240 |
  | 1W | 1D |

  So a 15m XAUUSD chart is magnified with 2m bars, and 1H with 10m bars. — [Help Center: What is bar magnifier backtesting mode](https://www.tradingview.com/support/solutions/43000669285-what-is-bar-magnifier-backtesting-mode/)
- The magnifier limit is 200,000 lower-timeframe bars. Early chart bars beyond that fall back to the default assumption. A rough first-affected bar is `last_bar_index - (200000 / LTF bars per chart bar)`. — [Help Center: bar magnifier](https://www.tradingview.com/support/solutions/43000669285-what-is-bar-magnifier-backtesting-mode/); [Strategies page](https://www.tradingview.com/pine-script-docs/concepts/strategies/#adjusting-historical-bar-detail)
- On "1T" charts the emulator always uses 1 tick per bar, and on "1S" charts 4 ticks per bar. Bar detalization does not change these. — [Strategies page, Adjusting historical bar detail](https://www.tradingview.com/pine-script-docs/concepts/strategies/#adjusting-historical-bar-detail)
- Within one `strategy.exit()` call, only the first triggered order of a bracket fills and the others are cancelled. All `strategy.exit()` orders share a `strategy.oca.reduce` group. — [Strategies page, Partial and multi-level exits](https://www.tradingview.com/pine-script-docs/concepts/strategies/#partial-and-multi-level-exits)

### Inferences
- Implementation: for each bar, build the tick sequence `[O, near_extreme, far_extreme, C]`, or the concatenated sub-bar sequences when magnifying. Walk each segment as a continuous line. A pending order fills at its level the first time a segment touches it. The exception is the first tick (the open): if the open is already beyond the level, the fill happens at the open (gap rule). Check orders in path order, not code order.
- For a bracket (SL + TP) where both levels lie inside one bar, the order hit first along the assumed path wins. On default detail this depends only on whether the open is nearer the high or the low, not on the close. This is the single biggest source of mismatch versus the magnifier and versus reality.
- When magnifying, apply the same 4-point rule to each sub-bar (the Help Center says the emulator uses "only OHLC values" of the lower timeframe).

### Gaps
- No official rule for when the open is exactly equidistant from high and low. Community lore says open→high→low→close, but I found no primary source for this.
- Not documented: how the trailing stop's trail level updates along the intrabar path (e.g., whether the trail can ratchet on the way to the high and then trigger on the way to the low within one bar). The docs' trailing-stop demo computes the theoretical stop as `high - trail_offset*mintick` per bar, which suggests ratcheting at the high.

---

## Q3. Limit/stop fill prices, gap handling, backtest_fill_limits_assumption, and slippage

### Takeaway
Limit orders fill at the limit price, or at the open if the bar gaps through the level favourably. Stop orders trigger at the stop price, or at the open if the bar gaps through it. A limit placed on the wrong (already-marketable) side fills at the next tick like a market order. `backtest_fill_limits_assumption=N` makes a limit fill only once price trades N ticks beyond the level, but the fill is still at the limit price. Slippage is a fixed number of ticks added in the adverse direction to **market and stop** fills, not limit fills, and it can push fills outside the bar's range.

### Cited Findings
- Limit: "When the market price reaches a limit order's value, or crosses it in the favorable direction, the broker emulator fills the order at that value or a better price. When a strategy generates a limit order at a worse value than the current market price..., the emulator fills the order on the next available tick." — [Strategies page, Limit orders](https://www.tradingview.com/pine-script-docs/concepts/strategies/#limit-orders)
- Stop: activates "when the market price reaches a specific price or a worse value". "If a strategy generates a stop order at a better value than the current market price, it activates the subsequent order without waiting." — [Strategies page, Stop and stop-limit orders](https://www.tradingview.com/pine-script-docs/concepts/strategies/#stop-and-stop-limit-orders)
- Stop-limit: when `strategy.entry()` or `strategy.order()` gets both `stop` and `limit`, the stop's trigger creates a limit order, which fills only if price then returns to the limit. — [Strategies page, Stop and stop-limit orders](https://www.tradingview.com/pine-script-docs/concepts/strategies/#stop-and-stop-limit-orders)
- `strategy.exit()` limits can fill at better prices and stops at worse prices, "depending on the range of values available to the broker emulator". — [Strategies page, strategy.exit()](https://www.tradingview.com/pine-script-docs/concepts/strategies/#take-profit-and-stop-loss)
- Gap rule (applies to stops and limits): fill at the next bar's open when the level was crossed in the gap. — [Strategies page, Broker emulator](https://www.tradingview.com/pine-script-docs/concepts/strategies/#broker-emulator)
- **backtest_fill_limits_assumption** is "the default number of ticks by which the market price must exceed the prices of limit orders before the broker emulator can fill the orders... If the argument is 0 (default), the emulator fills orders as soon as the market price reaches the limit price." — [Declaration statements page](https://www.tradingview.com/pine-script-docs/language/declaration-statements/#slippage-and-backtest_fill_limits_assumption)
- Even with a nonzero value, "the broker emulator still executes verified limit orders at their specified prices... a necessary compromise to preserve the intended fill prices of limit orders without causing lookahead bias", so fill times can be unrealistic. The UI input is now "Limit order execution", with only two options: fill when price *reaches* the level, or when it moves *one tick beyond*. — [Strategies page, Slippage and unfilled limits](https://www.tradingview.com/pine-script-docs/concepts/strategies/#slippage-and-unfilled-limits); [Release notes, July 2026](https://www.tradingview.com/pine-script-docs/release-notes/)
- Older Help Center wording: with a nonzero value, "limit orders can enter a position within the bar only if the market price has exceeded the level of the limit order by the specified number of ticks." — [Help Center: Strategy properties](https://www.tradingview.com/support/solutions/43000628599-strategy-properties/)
- **Slippage**: "the default number of ticks that the strategy applies to the fill prices of all market orders and stop orders... adds the specified number of ticks to the fill prices of long orders and subtracts it from the fill prices of short orders." Default 0. — [Declaration statements page](https://www.tradingview.com/pine-script-docs/language/declaration-statements/#slippage-and-backtest_fill_limits_assumption)
- Help Center: slippage "specifies the value in ticks to be added to the fill price of market or stop orders. It can be used to account for the spread." — [Help Center: Strategy properties](https://www.tradingview.com/support/solutions/43000628599-strategy-properties/)
- "Because the strategy applies constant slippage to all order fills, some orders can fill outside the candle range in the simulation." Limit orders "cannot execute at a worse price". — [Strategies page, Slippage and unfilled limits](https://www.tradingview.com/pine-script-docs/concepts/strategies/#slippage-and-unfilled-limits)
- "Commission paid" excludes slippage, which is embedded in fill prices. — [Help Center: Commission paid](https://www.tradingview.com/support/solutions/43000681703-commission-paid/)

### Inferences
- "Long orders" and "short orders" refer to the order's side (buy vs sell). A long exit is a sell order, so slippage lowers its fill. This applies to stop-loss exits and `strategy.close` exits on a long. That matches "unfavorable direction" in the docs.
- Fill price formulas (price in chart currency, tick = `syminfo.mintick`):
  - Market buy = `open_next + slip*tick`; market sell = `open_next − slip*tick`.
  - Buy stop at S: trigger when the path reaches S; fill = `max(S, open if gapped) + slip*tick`.
  - Buy limit at L: fill = `min(L, open if gapped)`. With a fill-limits assumption of N, the path must reach `L − N*tick`, and the fill is still exactly L (not "better").
- With a gap-through and a nonzero fill-limits assumption, the docs don't say whether the fill is at the open (better) or at L. See Gaps.
- For XAUUSD on OANDA (tick = 0.001), slippage of 1 tick is $0.001/oz, which is negligible. Realistic spread modelling needs hundreds of ticks (e.g., 200 ticks ≈ $0.20).

### Gaps
- Not documented: whether slippage applies to the stop-triggered leg of a stop-limit order (it becomes a limit, so presumably not).
- Not documented: the fill price for a gapped limit when `backtest_fill_limits_assumption > 0`.

---

## Q4. strategy.exit semantics (ticks vs prices, trailing, OCA, partial exits) and strategy.close / close_all

### Takeaway
`strategy.exit()` creates price-based exits: TP (limit), SL (stop) and trailing stop. These can be given as tick distances from the trade's entry price (`profit`, `loss`, `trail_points`, `trail_offset`) or as absolute prices (`limit`, `stop`, `trail_price`). Since v6, if both forms are given, the level expected to trigger first is used. Each call reserves a quantity and joins an implicit OCA "reduce" group. `strategy.close()` and `strategy.close_all()` are market orders that fill on the next tick. Positions close FIFO by default.

### Cited Findings
- `profit`/`loss` "accept relative values representing the number of ticks by which the market price must move away from the entry price". `limit`/`stop` are absolute prices. — [Strategies page, strategy.exit()](https://www.tradingview.com/pine-script-docs/concepts/strategies/#take-profit-and-stop-loss)
- v6: when both relative and absolute are given, "it creates orders only at the levels expected to trigger exits first." In v5 the absolute parameter always won. — [Strategies page](https://www.tradingview.com/pine-script-docs/concepts/strategies/#take-profit-and-stop-loss); [v6 migration guide](https://www.tradingview.com/pine-script-docs/migration-guides/to-pine-version-6/#strategyexit-evaluates-parameter-pairs); [Release notes, Dec 2024](https://www.tradingview.com/pine-script-docs/release-notes/)
- `strategy.exit()` with `limit` and `stop` creates **two** orders (TP and SL). `strategy.entry()` with both creates **one** stop-limit order. — [Strategies page, strategy.exit()](https://www.tradingview.com/pine-script-docs/concepts/strategies/#take-profit-and-stop-loss)
- Trailing stop parameters:
  - `trail_price` is the absolute activation level.
  - `trail_points` is the activation distance in ticks from entry.
  - `trail_offset` is the trailing distance in ticks.
  - It needs `trail_offset` plus `trail_price` or `trail_points`; if both activation forms are given, the one reached first is used.
  - After activation, the stop "increases to maintain a maximum distance of trail_offset ticks from the best value" and never moves backward.
  — [Strategies page, Trailing stops](https://www.tradingview.com/pine-script-docs/concepts/strategies/#trailing-stops)
- Partial exits: use `qty` or `qty_percent`; if both are set, `qty` wins. If the summed exit sizes exceed the position, sizes are reduced automatically. "The orders from each call automatically reserve a portion of the open position. The orders from one strategy.exit() call cannot exit the portion of a position that a previous call already reserved." Reservation follows code order. — [Strategies page, Partial and multi-level exits](https://www.tradingview.com/pine-script-docs/concepts/strategies/#partial-and-multi-level-exits)
- `from_entry`:
  - With an ID, exits apply to trades with that entry ID created on or before the call's bar.
  - With no ID, the call "persists and creates exit orders for all open trades... and it continues to generate exit orders for subsequent entries after that bar until the position closes."
  - If the ID matches no open trade, no orders are created.
  — [Strategies page, Exits for multiple entries](https://www.tradingview.com/pine-script-docs/concepts/strategies/#exits-for-multiple-entries)
- OCA types:
  - `strategy.oca.cancel` cancels the other orders when one fills.
  - `strategy.oca.reduce` shrinks the other orders by the filled qty.
  - `strategy.oca.none` is the default for `strategy.entry()` and `strategy.order()`.
  - All `strategy.exit()` orders belong to a reduce group by default.
  - The same name with a different type counts as a different group.
  — [Strategies page, OCA groups](https://www.tradingview.com/pine-script-docs/concepts/strategies/#oca-groups)
- `strategy.close(id)` and `strategy.close_all()` generate market orders that fill "on the next available tick, irrespective of the price". `close(id)` closes all open trades with that *entry* ID in one transaction. — [Strategies page, strategy.close() and strategy.close_all()](https://www.tradingview.com/pine-script-docs/concepts/strategies/#strategyclose-and-strategyclose_all)
- FIFO is the default: "any exit order closes or reduces the position starting with the first open trade, even if the exit command specifies the entry ID of a different open trade." `close_entries_rule="ANY"` overrides this, and it can be set only in code. — [Strategies page, Closing a market position](https://www.tradingview.com/pine-script-docs/concepts/strategies/#closing-a-market-position); [Declaration statements page](https://www.tradingview.com/pine-script-docs/language/declaration-statements/#close_entries_rule)
- Reversal: a `strategy.entry()` in the opposite direction adds the open position size to the order, so it closes the position and opens the new one in a single transaction. The trade marker shows the combined qty. — [Strategies page, Reversing positions](https://www.tradingview.com/pine-script-docs/concepts/strategies/#reversing-positions)
- `strategy.order()` ignores pyramiding, does not auto-reverse, and nets against the position. — [Strategies page, strategy.order()](https://www.tradingview.com/pine-script-docs/concepts/strategies/#strategyorder)
- Exit and close orders are sized to the trades they apply to, not to `default_qty_*`. — [Declaration statements page](https://www.tradingview.com/pine-script-docs/language/declaration-statements/#default_qty_type-and-default_qty_value)
- `strategy.risk.*` commands (max_drawdown, max_intraday_loss, max_cons_loss_days, max_intraday_filled_orders, max_position_size, allow_entry_in) run on every tick and fill event, and can force-close positions and halt trading. — [Strategies page, Risk management](https://www.tradingview.com/pine-script-docs/concepts/strategies/#risk-management)

### Inferences
- Tick-distance exits resolve to prices per trade: `TP = entry_price ± profit*mintick`, `SL = entry_price ∓ loss*mintick`. Here `entry_price` is the actual fill price (including slippage), because exits are relative to "the entry price". Exits placed on the signal bar with `from_entry` become active as soon as the entry fills, so they can trigger on the entry bar along the remaining path.
- Our engine needs per-trade objects (FIFO list), per-exit-call quantity reservation in code order, and OCA-reduce semantics for exits.

### Gaps
- Not documented: whether tick-based exits are computed from the slippage-adjusted fill price or the pre-slippage price. The inference above assumes the actual fill.
- No primary source on the trailing-stop intrabar update sequence (see Q2 Gaps).

---

## Q5. Position sizing, pyramiding, margin and margin calls, initial capital, currency conversion

### Takeaway
Defaults:
- 1 contract (`strategy.fixed`, value 1)
- initial capital 1,000,000 in the chart's currency
- pyramiding 1
- margin 100% long and short (v6; it was 0% in v5)

Percent-of-equity sizing is `qty = pct/100 × equity / close`, using the signal bar's close and equity that includes open P&L. The size can be constrained by the symbol's minimum tradable quantity. Margin calls liquidate 4× the shortfall quantity. Currency conversion uses the previous day's FX rate.

### Cited Findings
- `default_qty_type` options:
  - `strategy.fixed`: contracts/shares/lots/units.
  - `strategy.cash`: a fixed amount of account currency.
  - `strategy.percent_of_equity`: "a fixed percentage of the strategy's available equity".
  - `default_qty_value` defaults to 1.
  - A non-na `qty` in `entry`/`order` overrides the defaults.
  — [Declaration statements page](https://www.tradingview.com/pine-script-docs/language/declaration-statements/#default_qty_type-and-default_qty_value); [Strategies page, Position sizing](https://www.tradingview.com/pine-script-docs/concepts/strategies/#position-sizing)
- "The calculated values can be subject to constraints due to the minimum tradable quantities for the symbol". Percent of equity is "calculated as a percentage of the available equity when the trade opens." — [Help Center: Strategy properties](https://www.tradingview.com/support/solutions/43000628599-strategy-properties/)
- Engine formula (Help Center): "The number of contracts calculated by the strategy engine is calculated as `qty = (order size * equity / 100) / close`", with `strategy.equity = strategy.initial_capital + strategy.netprofit + strategy.openprofit`. — [Help Center: 'Cannot create an order with negative quantity'](https://www.tradingview.com/support/solutions/43000651235-i-see-cannot-create-an-order-with-negative-quantity-error/)
- `syminfo.mincontract` (new in v6, Nov 2024) is "the smallest number of contracts/shares/lots/units required to trade the current symbol". — [Release notes, Nov 2024](https://www.tradingview.com/pine-script-docs/release-notes/)
- `strategy.default_entry_qty(fill_price)` (Sept 2023) "Calculates the default quantity... if it were to fill at the specified fill_price value." — [Release notes, Sept 2023](https://www.tradingview.com/pine-script-docs/release-notes/)
- Pyramiding: the default of 1 limits how many open trades `strategy.entry()` can add per position. If several price-based `strategy.entry()` orders trigger on the same tick, they can all fill and exceed the limit. — [Strategies page, Pyramiding](https://www.tradingview.com/pine-script-docs/concepts/strategies/#pyramiding)
- Initial capital defaults to 1,000,000 in the chart's quote currency (`currency.NONE`). — [Declaration statements page](https://www.tradingview.com/pine-script-docs/language/declaration-statements/#initial_capital-and-currency); [Help Center: Initial capital](https://www.tradingview.com/support/solutions/43000777193-initial-capital/)
- Margin defaults:
  - v6 `margin_long` and `margin_short` default to 100: "The strategy does not open entries that require more money than is available, and short orders are margin called if too much money is lost."
  - v5 defaulted to 0, which means no funds check.
  - The UI now shows "Long/Short leverage", converted from these margin values.
  — [v6 migration guide](https://www.tradingview.com/pine-script-docs/migration-guides/to-pine-version-6/#default-margin-percentage); [Release notes, July 2026](https://www.tradingview.com/pine-script-docs/release-notes/)
- Margin call trigger: `CurrentEquity <= MarginRequired`, where
  - `CurrentEquity = PriceChange*Direction*PointValue*AbsPositionSize + InitialCapital + NetProfit`
  - `MarginRequired = LastPrice*PointValue*AbsPositionSize*(MarginPercent/100)`
  - Liquidation price: `((InitialCapital+NetProfit)/(PointValue*AbsPositionSize) − Direction*EntryPrice)/(MarginPercent/100 − Direction)`, rounded down for longs and up for shorts.
  — [Help Center: How to simulate trading with leverage](https://www.tradingview.com/support/solutions/43000717375-how-to-simulate-trading-with-leverage-in-pine-script/)
- Liquidation size algorithm, in order:
  1. Money Spent = Qty × Entry Price
  2. MVS = Position Size × Current Price
  3. Open Profit = MVS − Money Spent (×−1 if short)
  4. Equity = Initial Capital + Net Profit + Open Profit
  5. Margin = MVS × Margin Ratio
  6. Available Funds = Equity − Margin
  7. Loss = Available Funds / Margin Ratio
  8. Cover Amount = TRUNCATE(Loss / Current Price), to the minimum position-size precision
  9. Margin Call Size = Cover Amount × 4

  Worked example (TSLA): 682,438 shares at 4.43, 25% margin, price 3.9 → liquidate 111,052. Shorts can be margin-called even at 100% margin. — [Strategies page, Margin and leverage](https://www.tradingview.com/pine-script-docs/concepts/strategies/#margin-and-leverage)
- Margin below 0.2% (over 500:1) is "typically unrealistic", and 0% means infinite leverage. — [Strategies page, Margin and leverage](https://www.tradingview.com/pine-script-docs/concepts/strategies/#margin-and-leverage)
- Currency:
  - If the account currency differs from the chart's, the strategy uses "the previous daily value of a corresponding currency pair from the most popular exchange", or a spread if no direct pair exists.
  - Monetary values are multiplied by that rate.
  - On timeframes above 1D it uses the rate from one day before each bar's close; on realtime bars, the latest confirmed daily rate.
  - `request.currency_rate(syminfo.currency, strategy.account_currency)` reproduces the rate.
  — [Strategies page, Currency](https://www.tradingview.com/pine-script-docs/concepts/strategies/#currency)
- The cost of a position equals the chart price × `syminfo.pointvalue`, which matters for futures. — [Strategies FAQ](https://www.tradingview.com/pine-script-docs/faq/strategies/#why-are-no-trades-executed-after-i-add-the-strategy-to-the-chart)

### Inferences
- Implement percent-of-equity sizing as `qty = floor_to_step(pct/100 × equity_t / (close_t × pointvalue × fx))`. The order is sized at the signal bar's close but fills at the next open, so the realised notional differs from the target.
- The Help Center formula omits `pointvalue` and FX. That is harmless for OANDA:XAUUSD in a USD account (pointvalue presumed 1, no FX), but would matter for COMEX:GC.
- With 100% margin and 100% of equity sizing, a gap up at the next open can make the order cost more than the available equity. TradingView's handling of this (reject vs shrink) is undocumented. Our engine should log such cases.
- `strategy.cash` sizing presumably works the same way: `qty = cash / (close × pointvalue × fx)`. This is not documented explicitly.

### Gaps
- The rounding rule for fractional quantities (floor to `syminfo.mincontract`? to some decimal precision?) is not documented beyond "minimum tradable quantities". The margin-call doc mentions truncation "to the same decimal precision as the minimum position size".
- Unknown whether commission is reserved when computing percent-of-equity size. No source found.
- Unknown whether an entry that exceeds available funds under 100% margin is rejected outright or reduced.

---

## Q6. Commission types and how they are applied

### Takeaway
There are three commission types: `percent` of transaction value, `cash_per_contract`, and `cash_per_order`. Commission is charged on **both entry and exit fills**. It is deducted inside each trade's net P&L, so gross profit and gross loss are already net of commission. The default is 0.

### Cited Findings
- Types: `strategy.commission.percent` (percent of the transaction value), `strategy.commission.cash_per_contract` (per contract/share/lot/unit) and `strategy.commission.cash_per_order` (flat per order). `commission_value` defaults to 0. A value of 1 means 1 unit of account currency per order, 1 per contract, or 1% depending on type. — [Declaration statements page](https://www.tradingview.com/pine-script-docs/language/declaration-statements/#commission_type-and-commission_value); [Strategies page, Commission](https://www.tradingview.com/pine-script-docs/concepts/strategies/#commission)
- "Commission is applied on both entries and exits, and that when a percentage is used, the calculated commission will vary with the value of the transaction." — [Help Center: Strategy properties](https://www.tradingview.com/support/solutions/43000628599-strategy-properties/)
- With `percent` = 1, the emulator "applies a commission of 1% of the transaction size to each filled order". — [Strategies page, Commission](https://www.tradingview.com/pine-script-docs/concepts/strategies/#commission)
- Gross profit: "If a commission value is set... it is automatically deducted from each winning trade before being added to this total." Gross loss: commission "is added to the magnitude of the loss." — [Help Center: Gross profit](https://www.tradingview.com/support/solutions/43000681686-gross-profit/); [Help Center: Gross loss](https://www.tradingview.com/support/solutions/43000681688-gross-loss/)
- "Commission paid" is the total fees, already subtracted from Net P&L, and excludes slippage. — [Help Center: Commission paid](https://www.tradingview.com/support/solutions/43000681703-commission-paid/)
- Per-trade commission is exposed via `strategy.opentrades.commission()` and `strategy.closedtrades.commission()`. — [Strategies page, Individual trade information](https://www.tradingview.com/pine-script-docs/concepts/strategies/#individual-trade-information)
- "Even trades" are trades whose profit after commission and slippage is exactly zero. — [Help Center: Even trades](https://www.tradingview.com/support/solutions/43000773598-even-trades/)

### Inferences
- Per fill: `comm = pct/100 × qty × fill_price × pointvalue × fx` (percent), or `rate × qty` (per contract), or `rate` (per order).
- Trade net P&L = `dir × (exit_px − entry_px) × qty × pointvalue × fx − entry_comm_alloc − exit_comm`.
- When one order closes several trades (FIFO, reversal), per-order commission must be allocated across trades. TradingView's allocation rule is undocumented (see Gaps).
- On a reversal (one transaction of open qty + new qty), per-order commission is presumably charged once on the combined order.

### Gaps
- No primary source on how a `cash_per_order` commission is split between the closing and opening legs of a reversal order, or across several FIFO trades closed by one order.

---

## Q7. Strategy report metric definitions and formulas (2025–2026), and recent changes

### Takeaway
Nearly all trade metrics use **closed trades only** and per-trade P&L net of commission:
- Net P&L = Σ trade P&L.
- Profit factor = gross profit / |gross loss|.
- Win % = winners / all closed trades (break-even trades count in the denominator).
- Average trade = net P&L / number of closed trades.

Max drawdown and max run-up come in two flavours: an *intrabar* version, computed per bar in a position from the bar's low/high against the peak closed-trade equity, and a *close-to-close* version. Sharpe and Sortino use **monthly** returns (always monthly since Aug 2024), an annual risk-free rate (default 2%), and population SD; they are not annualized.

### Cited Findings
**Report structure and recent changes**
- The report (formerly the "Strategy Tester") has "Metrics" and "Trades" tabs. Metrics is split into Key stats, Return details, Trades analysis, Equity run-ups and drawdowns, and Capital efficiency, with All/Long/Short columns. Published strategies also get a Properties tab. Data can be exported as XLSX, and the trade list as CSV. — [Strategies page, Strategy report](https://www.tradingview.com/pine-script-docs/concepts/strategies/#strategy-report)
- July 2026 UI changes:
  - Strategy Tester renamed "strategy report".
  - New Script execution menu.
  - "Bar detalization" replaces the Bar Magnifier checkbox.
  - "Heikin Ashi mode" dropdown added.
  - "Limit order execution" dropdown replaces "Verify price for limit orders".
  - "Order execution delay" replaces the on-close checkbox.
  - "Long/Short leverage" replaces the margin % inputs.
  - `calc_on_every_history_tick` added.
  — [Release notes, July 2026](https://www.tradingview.com/pine-script-docs/release-notes/)
- August 2024: "The Sharpe and Sortino ratios... Previously, the ratios used strategy returns over monthly periods if the trading range was three or more months and daily periods if the range was three or more days but less than three months. Both ratios now always use monthly periods for consistency." — [Release notes, Aug 2024](https://www.tradingview.com/pine-script-docs/release-notes/)
- Pine v6 (Nov 2024):
  - Default margin is 100.
  - In non-Deep mode, the 9000-trade limit now trims the oldest trades instead of raising a runtime error.
  - The `when` parameter was removed.
  - `strategy.exit` evaluates relative and absolute parameter pairs (Dec 2024).
  — [v6 migration guide](https://www.tradingview.com/pine-script-docs/migration-guides/to-pine-version-6/#strategies); [Release notes](https://www.tradingview.com/pine-script-docs/release-notes/)

**Realized P&L metrics**
- Net P&L is "the mathematical sum of all closed trades in the Net PnL column". It excludes open positions. — [Help Center: Net PnL](https://www.tradingview.com/support/solutions/43000681684-net-pnl/)
- Gross profit is the sum of positive trade net P&L; gross loss is the sum of negative trade net P&L. Both are net of commission. — [Help Center: Gross profit](https://www.tradingview.com/support/solutions/43000681686-gross-profit/); [Help Center: Gross loss](https://www.tradingview.com/support/solutions/43000681688-gross-loss/)
- Profit factor: "dividing the absolute value of all winning trades by the absolute value of all losing trades", realized only. — [Help Center: Profit factor](https://www.tradingview.com/support/solutions/43000681698-profit-factor/)
- Winners are trades with P&L > 0 and losers trades with P&L < 0. Even trades (P&L exactly 0) are excluded from both. — [Help Center: Total winners](https://www.tradingview.com/support/solutions/43000681712-total-winners/); [Help Center: Total losers](https://www.tradingview.com/support/solutions/43000681713-total-losers/)
- Percent profitable = winners / total closed trades. Even trades are "excluded from the numerator, though they remain in the denominator". — [Help Center: Percent profitable](https://www.tradingview.com/support/solutions/43000681714-percent-profitable/)
- Total trades counts completed entry+exit cycles only. — [Help Center: Total trades](https://www.tradingview.com/support/solutions/43000681704-total-trades/)
- Average P&L = Expected payoff = Net P&L / number of closed trades. — [Help Center: Average PnL](https://www.tradingview.com/support/solutions/43000681715-average-pnl/); [Help Center: Expected payoff](https://www.tradingview.com/support/solutions/43000772770-expected-payoff/)
- Average profit = total profit of winners / number of winners. Average loss = total loss of losers / number of losers. Avg profit / avg loss = their ratio. — [Help Center: Average profit](https://www.tradingview.com/support/solutions/43000681717-average-profit/); [Help Center: Average loss](https://www.tradingview.com/support/solutions/43000681718-average-loss/); [Help Center: Avg profit/avg loss](https://www.tradingview.com/support/solutions/43000681719-average-profit-average-loss/)
- Largest profit and largest loss come from closed trades only. Two related ratios are reported: largest profit as % of gross profit, and largest loss as % of gross loss. — [Help Center: Largest profit](https://www.tradingview.com/support/solutions/43000681720-largest-profit/); [Help Center: Largest loss](https://www.tradingview.com/support/solutions/43000681722-largest-loss/); [Help Center: Largest profit as % of gross profit](https://www.tradingview.com/support/solutions/43000772909-largest-profit-as-of-gross-profit/)
- Average bars in trades / winners / losers: "The average number of bars that elapsed during trades for all closed trades". — [Help Center: Average bars in trades](https://www.tradingview.com/support/solutions/43000681723-average-bars-in-trades/)
- Open P&L is the unrealized P&L of open positions at current prices, or 0 when flat. — [Help Center: Open PnL](https://www.tradingview.com/support/solutions/43000681701-open-pnl/)

**Drawdown and run-up**
- Max drawdown (intrabar), Help Center algorithm:
  1. Equity_on_Entry = equity before the trade opens (initial capital for the first trade).
  2. Max_Equity = the max of initial capital and the equity after each already-closed trade.
  3. For every bar in the position: long DD = `Max_Equity − Equity_on_Entry + Contracts × (Entry_Price − Current_Low)`; short DD = `... + Contracts × (Current_High − Entry_Price)`.
  4. On the closing bar, respect the intrabar path. "If the trade was closed on the bar's open, Open will be considered both the maximum and the minimum value of that bar."
  5. Max DD = the maximum over all of these values.

  Worked example with UBER: 10000 − 9900.12 + 45 × (35.34 − 31.81) = 258.73. — [Help Center: Max drawdown (intrabar)](https://www.tradingview.com/support/solutions/43000681690-max-drawdown-intrabar/)
- Max run-up (intrabar) mirrors this with Min_Equity: long RU = `Equity_on_Entry − Min_Equity + Contracts × (Current_High − Entry_Price)`; short RU = `... + Contracts × (Entry_Price − Current_Low)`. — [Help Center: Max run-up (intrabar)](https://www.tradingview.com/support/solutions/43000682585-max-run-up-intrabar/)
- Max drawdown (close-to-close): "The largest drop in account equity from a previous closing high to a subsequent closing low". Max run-up (close-to-close) is the counterpart. — [Help Center: Max drawdown (close-to-close)](https://www.tradingview.com/support/solutions/43000773376-max-drawdown-close-to-close/); [Help Center: Max run-up (close-to-close)](https://www.tradingview.com/support/solutions/43000773375-max-run-up-close-to-close/)
- Average drawdown (close-to-close) = Σ(Equity Peak_i − Equity Trough_i) / N_drawdowns, where each drawdown runs from a peak until recovery to that peak. Durations are averaged in calendar days. Average run-up is the counterpart. — [Help Center: Average drawdown (close-to-close)](https://www.tradingview.com/support/solutions/43000772100-average-drawdown-close-to-close/); [Help Center: Average drawdown duration](https://www.tradingview.com/support/solutions/43000772102-average-drawdown-duration-close-to-close/); [Help Center: Average run-up](https://www.tradingview.com/support/solutions/43000772097-average-run-up-close-to-close/)
- "Max drawdown as % of initial capital (intrabar)" expresses max drawdown relative to initial capital. — [Help Center](https://www.tradingview.com/support/solutions/43000772907-max-drawdown-as-of-initial-capital-intrabar/)
- Return of max drawdown = (Net Profit + Open P&L) / Max Drawdown (intrabar). — [Help Center: Return of max drawdown](https://www.tradingview.com/support/solutions/43000772905-return-of-max-drawdown/)

**Risk-adjusted ratios**
- Sharpe: `SR = (MR − RFR) / SD`, where MR is the "average return for a monthly trading period", RFR the risk-free rate ("by default, 2% annually. Can be changed with the risk_free_rate parameter"), and `SD = sqrt( (1/N) Σ (X_i − MR)^2 )`. Example of X_i: equity 100 on Jan 1 and 110 on Feb 1 gives a January return of 10%. — [Help Center: Sharpe Ratio](https://www.tradingview.com/support/solutions/43000681694-sharpe-ratio/)
- Sortino: `SR = (MR − RFR) / DD` with `DD = sqrt( Σ (min(0, X_i − T))^2 / N )`, where T is the "target return". — [Help Center: Sortino Ratio](https://www.tradingview.com/support/solutions/43000681697-sortino-ratio/)
- `risk_free_rate` defaults to 2 (annual %) and can be set only in code, not in the UI. — [Declaration statements page, risk_free_rate](https://www.tradingview.com/pine-script-docs/language/declaration-statements/#risk_free_rate)
- TradingView's **Portfolio** feature, a different product, documents the annual→monthly conversion as "2 / 12 = 0.167%". It uses monthly TWR returns (including a partial final month), population variance (÷N), and no annualization. Example: SR = (0.225 − 0.167)/1.957. — [Help Center: Analysis: Sharpe ratio (Portfolio)](https://www.tradingview.com/support/solutions/43000756107/)

**Benchmark and capital metrics**
- Buy & hold % gain = (Price_end − Price_start)/Price_start × 100, measured "from the moment the strategy's first position was opened until the final bar of the test period". Buy & hold P&L assumes investing "the entire initial capital into the security at the start of the first trade". — [Help Center: Buy and hold % gain](https://www.tradingview.com/support/solutions/43000772912-buy-and-hold-gain/); [Help Center: Buy and hold PnL](https://www.tradingview.com/support/solutions/43000681691-buy-and-hold-pnl/)
- Strategy outperformance = Net Profit − Buy & Hold Return ($), over the same period. — [Help Center: Strategy outperformance](https://www.tradingview.com/support/solutions/43000772915-strategy-outperformance/)
- CAGR (%) = (Final Equity / Initial Capital)^(365 / Duration in days) − 1. — [Help Center: Annualized return (CAGR)](https://www.tradingview.com/support/solutions/43000772911-annualized-return-cagr/)
- Return on initial capital = Total Net Profit / Initial Capital × 100%. — [Help Center: Return on initial capital](https://www.tradingview.com/support/solutions/43000772903-return-on-initial-capital/)
- Account size required = Max Used Margin + |Max Drawdown (Intrabar)|. Return on account size required = Net Profit / Account Size Required × 100. — [Help Center: Account size required](https://www.tradingview.com/support/solutions/43000772918-account-size-required/); [Help Center: Return on account size required](https://www.tradingview.com/support/solutions/43000772917-return-on-account-size-required/)
- Average margin used = the sum of used margin at each bar's close / number of bars. Max margin used = the peak. Margin efficiency = profit per $ of margin. — [Help Center: Average margin used](https://www.tradingview.com/support/solutions/43000772914-average-margin-used/); [Help Center: Max margin used](https://www.tradingview.com/support/solutions/43000772920-max-margin-used/); [Help Center: Margin efficiency](https://www.tradingview.com/support/solutions/43000772921-margin-efficiency/)
- Liquidation volume = Quantity × Trade Close Price, summed over liquidations. — [Help Center: Total liquidated volume](https://www.tradingview.com/support/solutions/43000786636-total-liquidated-volume/)
- The full metric list is in the Help Center folder. — [Help Center: Strategy report metrics folder](https://www.tradingview.com/support/folders/43000599093-strategy-report-metrics/)

**Pine-side metric variables**
- Pine exposes `strategy.netprofit`, `grossprofit`, `grossloss`, `openprofit`, `max_runup`, `max_drawdown`, `wintrades`, `losstrades`, `eventrades`, `avg_trade`, `avg_winning_trade`, `avg_losing_trade` (plus `_percent` variants) and `max_contracts_held_*`. These can be used for in-script cross-checks. — [Strategies page, Using strategy information in scripts](https://www.tradingview.com/pine-script-docs/concepts/strategies/#using-strategy-information-in-scripts)

### Inferences
- Intrabar max drawdown, as documented, uses the **peak of closed-trade equity only**. Unrealized gains in the current trade never raise the peak, so a large give-back of open profit is not counted as drawdown. This differs from a standard mark-to-market peak-to-trough calculation, and an engine copying TradingView must use the documented formula.
- The documented formula ignores commission. Pyramided positions would presumably sum per-trade terms. Both points are unverified.
- Sharpe/Sortino: by analogy with the Portfolio article, compute monthly returns from strategy equity at calendar-month boundaries as `(E_m − E_{m−1})/E_{m−1}`, set `RFR_m = risk_free_rate/12`, use population SD and do not annualize. This is close but unconfirmed for the strategy report; validate against a known TradingView output.
- TradingView's CAGR uses calendar days (365) and Final Equity. Whether final equity includes open P&L is unstated.
- The help articles for CAGR, Account size required and the close-to-close drawdown metrics have formula images timestamped around Nov 2025. That suggests the expanded Metrics tab arrived in late 2025, but I found no announcement post. Treat this date as a weak inference.

### Gaps
- Sortino target T is not specified (0, RFR_m, or MR?).
- Not specified for the strategy report: how partial first/last months are handled, whether monthly equity is marked-to-market (includes open P&L) or closed-trade equity, and whether the annual→monthly RFR conversion is /12 (only the Portfolio article states this).
- Bar-count convention for "Average bars in trades" (exit_bar − entry_bar, or +1) is not documented. Pine's `strategy.closedtrades.entry_bar_index` and `exit_bar_index` are available for empirical checking.
- Not documented: how close-to-close equity is sampled (every bar close with open P&L, or only at trade closes).
- I found no TradingView blog or changelog post announcing the 2025 Metrics-tab redesign. The only dated primary changes are in the Pine release notes (Aug 2024, Nov/Dec 2024, July 2026).

---

## Q8. Known pitfalls that make TradingView backtests misleading (repainting, lookahead, same-bar fills, historical vs realtime, bar/trade limits, Deep Backtesting)

### Takeaway
The main traps:
- Same-bar fills via `process_orders_on_close` or `calc_on_order_fills`.
- `request.security` with `lookahead_on` and no `[1]` offset.
- `calc_on_every_tick` repainting.
- Non-standard charts.
- The default intrabar assumption mis-ordering SL/TP on wide bars.
- Guaranteed limit fills on touch.
- 0% margin (v5 default).
- Results that change as the chart's loaded history window moves.

Regular mode also limits the chart to a fixed number of bars per plan (5k–40k intraday) and keeps detail for only the latest 9000 trades. Deep Backtesting (Premium+) runs on all history but starts indicator warm-up differently.

### Cited Findings
- Lookahead bias sources: "request alternate timeframe data, use repainting variables such as timenow, or alter calculation behavior for intrabar order fills". Remedies:
  - Don't use repainting variables in order logic.
  - "Do not include barmerge.lookahead_on in request.*() calls without offsetting the data series with the history-referencing operator".
  - Avoid current-bar OHLC when "On order fill" is active.
  — [Strategies page, Lookahead bias](https://www.tradingview.com/pine-script-docs/concepts/strategies/#lookahead-bias)
- "To avoid repainting, set the calc_on_every_tick, calc_on_order_fills, and process_orders_on_close parameters to false". Use only confirmed higher-timeframe values. — [Strategies FAQ](https://www.tradingview.com/pine-script-docs/faq/strategies/#why-is-my-strategy-repainting)
- Processing orders on close "might not give accurate results... if an alert occurs at the close of the session's last bar, the actual order can be executed only on the next trading day". — [Strategies FAQ](https://www.tradingview.com/pine-script-docs/faq/strategies/#why-are-my-orders-executed-on-the-bar-following-my-triggers)
- Changing Script execution settings "can cause repainting... because they define different behaviors for historical and realtime bars". — [Strategies page, Altering calculation behavior](https://www.tradingview.com/pine-script-docs/concepts/strategies/#altering-calculation-behavior)
- Non-standard charts (HA, Renko, line break, Kagi, P&F, range) use synthetic prices: "typically produces unrealistic results." — [Strategies page, Applying a strategy to a chart](https://www.tradingview.com/pine-script-docs/concepts/strategies/#applying-a-strategy-to-a-chart)
- History limits: "Strategy results can vary over time depending on where the historical data starts... different TradingView plans provide access to varying amounts of historical bars... natural repainting of strategy results over time." — [Strategies FAQ](https://www.tradingview.com/pine-script-docs/faq/strategies/#why-did-my-trade-results-change-dramatically-overnight)
- Intraday chart bars per plan:

  | Plan | Bars |
  |---|---|
  | Ultimate | 40,000 |
  | Expert | 25,000 |
  | Premium | 20,000 |
  | Essential / Plus | 10,000 |
  | Others | 5,000 |

  Daily and higher timeframes show all data. — [Pine docs: Limitations](https://www.tradingview.com/pine-script-docs/writing/limitations/); [Help Center: Historical intraday data](https://www.tradingview.com/support/solutions/43000480679-historical-intraday-data-bars-and-limits-explained/)
- Trade limit:
  - In regular mode the strategy keeps detail for the latest 9000 trades; older ones are trimmed from the list, CSV and `closedtrades.*` (which return na).
  - Metrics-tab values and other `strategy.*` built-ins are not affected.
  - Deep Backtesting keeps all trades (order limit 1,000,000).
  — [Strategies page, Trade limit](https://www.tradingview.com/pine-script-docs/concepts/strategies/#trade-limit); [Pine docs: Limitations](https://www.tradingview.com/pine-script-docs/writing/limitations/)
- Deep Backtesting:
  - "available for Premium and higher plan users"; up to 2 million bars and 1 million trades.
  - Results appear only in the report, not on the chart.
  - Calculations "start at the beginning of the date range, whereas regular backtesting calculations always begin on the chart's first bar", so EMA/RMA warm-up differs and trades may not match regular mode.
  — [Help Center: How Deep Backtesting works](https://www.tradingview.com/support/solutions/43000666265-how-deep-backtesting-works/); [Help Center: Why regular and Deep Backtesting data don't match](https://www.tradingview.com/support/solutions/43000666266-why-do-the-data-of-the-regular-mode-and-deep-backtesting-not-match/)
- In Deep Backtesting, trade markers, plots, alerts and logs still use only chart data. — [Strategies page, Trade limit](https://www.tradingview.com/pine-script-docs/concepts/strategies/#trade-limit)
- The report needs enough trades; the FAQ suggests "ideally 100 trades or more". — [Strategies FAQ](https://www.tradingview.com/pine-script-docs/faq/strategies/#why-are-no-trades-executed-after-i-add-the-strategy-to-the-chart)
- Margin 0% is "extremely misleading" (infinite leverage). It was the v5 default. — [Strategies page, Margin and leverage](https://www.tradingview.com/pine-script-docs/concepts/strategies/#margin-and-leverage); [v6 migration guide](https://www.tradingview.com/pine-script-docs/migration-guides/to-pine-version-6/#default-margin-percentage)
- Limit orders are by default "guaranteed to fill when the market price reaches their values", which may not hold in real markets. — [Strategies page, Slippage and unfilled limits](https://www.tradingview.com/pine-script-docs/concepts/strategies/#slippage-and-unfilled-limits)
- Bar magnifier coverage is capped at 200k lower-timeframe bars, so early trades use default assumptions. — [Help Center: bar magnifier](https://www.tradingview.com/support/solutions/43000669285-what-is-bar-magnifier-backtesting-mode/)
- Strategies cannot hedge (one direction at a time) and trade only the chart symbol. — [Strategies FAQ](https://www.tradingview.com/pine-script-docs/faq/strategies/#can-you-hedge-in-a-pine-script-strategy)

### Inferences
- A faithful Python reproduction should, by default:
  - disable same-bar fills;
  - start indicator calculation at the same first bar as TradingView's loaded history (or the Deep Backtesting date range start), since EMA/RMA warm-up changes signals;
  - model the 9000-trade list truncation only for display.
- To match a user's TradingView run exactly, the engine must know their plan's bar window (5k–40k intraday bars), whether they used Deep Backtesting (and its range), and whether bar detalization was "High".

### Gaps
- I did not find TradingView documentation on how the 2-million-bar Deep Backtesting limit interacts with the bar magnifier's 200k lower-timeframe cap. A search snippet from TradingView's "Deep Backtesting is out of beta" blog post claimed the magnifier's history depth was increased for Deep Backtesting, but I did not fetch that post, so this is unverified.

---

## Q9. Symbol information that matters for gold (OANDA:XAUUSD and alternatives)

### Takeaway
OANDA:XAUUSD on TradingView is a USD-quoted CFD (type "commodity", typespec "cfd") with `pricescale=1000` and `minmov=1`, so **syminfo.mintick = 0.001**. Its exchange timezone is America/New_York. Point value is presumably 1 (P&L per 1-unit move per unit = $1, where 1 unit = 1 troy oz), but this needs confirming with `syminfo.pointvalue`. Other gold feeds use different tick sizes:
- FOREXCOM, PEPPERSTONE and FX XAUUSD: 0.01
- TVC:GOLD: 0.001
- COMEX:GC1!: 0.1, a futures contract with a large point value

### Cited Findings
- OANDA:XAUUSD metadata from TradingView's public scanner endpoint (undocumented API, queried 2026-10-25): `{"currency":"USD","description":"Gold","exchange":"OANDA","minmov":1,"minmove2":10,"pricescale":1000,"timezone":"America/New_York","type":"commodity"}`. The symbol-search API lists typespecs `["cfd"]`. — [TradingView scanner endpoint (OANDA:XAUUSD)](https://scanner.tradingview.com/symbol?symbol=OANDA:XAUUSD&fields=pricescale,minmov,pointvalue,currency,type,description,minmove2,timezone,exchange&no_404=true); [TradingView symbol search](https://symbol-search.tradingview.com/symbol_search/v3/?text=XAUUSD&exchange=OANDA&lang=en&domain=production)
- Same endpoint for other feeds:
  - FOREXCOM:XAUUSD, PEPPERSTONE:XAUUSD and FX:XAUUSD: `pricescale=100` (tick 0.01).
  - TVC:GOLD: `pricescale=1000`.
  - COMEX:GC1!: `pricescale=10` (tick 0.1), type "futures".
  — [TradingView scanner endpoint (FOREXCOM:XAUUSD)](https://scanner.tradingview.com/symbol?symbol=FOREXCOM:XAUUSD&fields=pricescale,minmov,pointvalue,currency,type&no_404=true); [TradingView scanner endpoint (COMEX:GC1!)](https://scanner.tradingview.com/symbol?symbol=COMEX:GC1!&fields=pricescale,minmov,pointvalue,currency,type&no_404=true)
- PointValue is "the amount of money that a whole number price move signifies. For most symbols, the value is 1, with the main exception being futures, where a change from 100 to 101 may mean that the value changed by 50 USD." — [Help Center: How to simulate trading with leverage](https://www.tradingview.com/support/solutions/43000717375-how-to-simulate-trading-with-leverage-in-pine-script/)
- An order of `1/syminfo.mintick` units makes each tick worth `syminfo.pointvalue` units of chart currency (doc example). Published strategy reports show symbol point value, currency and tick size in their Properties tab. — [Strategies page, Currency](https://www.tradingview.com/pine-script-docs/concepts/strategies/#currency); [Strategies page, Properties tab](https://www.tradingview.com/pine-script-docs/concepts/strategies/#properties-tab)
- `syminfo.mincontract` gives the minimum tradable quantity (v6). — [Release notes, Nov 2024](https://www.tradingview.com/pine-script-docs/release-notes/)

### Inferences
- For OANDA:XAUUSD, qty is in troy ounces (units). P&L = Δprice × qty × 1 USD.
  - A "standard lot" of 100 oz must be entered as qty = 100.
  - Slippage/fill-limit ticks are 0.001 USD each, so 1 pip (0.01) = 10 ticks, matching `minmove2=10`.
  - Commission per contract applies per ounce.
- For the Python engine, store per-symbol `mintick`, `pointvalue`, `mincontract`, `currency` and the session/timezone. Use the same feed as the user's TradingView chart, because tick sizes and OHLC differ between OANDA, FOREXCOM, Pepperstone and TVC.

### Gaps
- The scanner returned `pointvalue: null`, so `syminfo.pointvalue` and `syminfo.mincontract` for OANDA:XAUUSD could not be read directly. Presumed pointvalue = 1 and fractional-unit precision. Verify by running `plot(syminfo.pointvalue)` and `syminfo.mincontract` (or label them) on the chart.
- The COMEX:GC1! point value (expected 100 USD per 1.0 move, from the contract size of 100 oz) was not verified from a TradingView source.
- The session template (daily maintenance break) for OANDA:XAUUSD was not retrieved (`session` came back null).
