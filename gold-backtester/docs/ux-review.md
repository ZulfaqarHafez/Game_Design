# UI/UX review: Gold Strategy Lab backtester

Reviewed 25 Oct 2026 on the live site at desktop (1366–1440px) and phone (390px) widths, light and dark mode.
Methods: design critique, WCAG 2.1 AA audit, axe-core 4.10 scan, keyboard walk-through, 200% zoom, contrast maths.

## Design critique

**Overall:** the layout reads as a trading terminal and the chart rightly draws the eye first. The main weakness is
on phones: the result numbers sit below the chart, the equity chart is hard to read, and many controls are too
small to tap reliably.

### Usability

| Finding | Severity | Fix |
|---|---|---|
| On phones the key results (net profit, win rate, drawdown) are below the fold; the first screen is only the chart | 🔴 | Compact result strip above the chart on phones |
| Equity chart: buy & hold (up to $40k) squashes the strategy curve flat; drawdown bars overlap it | 🔴 | Drawdown in its own pane; buy & hold as an opt-in toggle; `$` axis without decimals |
| No visible loading state: chart and tiles go blank while a run is in progress | 🟡 | "Running backtest…" overlay and dimmed results with `aria-busy` |
| A failed run leaves the previous results looking current | 🟡 | Error banner, previous results dimmed and labelled |
| Inputs show raw code names (`atr mult`, `exit len`) | 🟡 | Plain-language labels from the strategy card |
| Changing the `#strategy` part of the URL does nothing until reload | 🟡 | React to `hashchange` |
| Zero-trade runs give a page of `n/a` with no explanation | 🟡 | Empty-state message with what to try |
| Tabs overflow on phones with no cue that they scroll | 🟢 | Edge fade on the tab bar |
| Default EMA strategy stops trading after Sep 2025: 1% risk on $10k is under the 0.01-lot minimum at today's gold price, and the only hint was small grey text | 🔴 | Notice above the equity chart with the count, the last trade date and a "Trade 0.01 lots instead" button |
| Phone toolbar: the pinned Settings button let the next chip show through on its right | 🟢 | Settings sits outside the scrolling chip row, which fades at its edge |

### Visual hierarchy and consistency

| Element | Issue | Fix |
|---|---|---|
| Stat tiles | 7 tiles leave an empty cell; captions truncated ("9.42% (TradingView …") | 8 tiles, shorter captions that wrap |
| Segmented controls | Timeframe uses radios, range and cost use pressed buttons | One pattern: pressed buttons in labelled groups |

## Accessibility audit (WCAG 2.1 AA)

| # | Issue | Criterion | Severity | Fix |
|---|---|---|---|---|
| 1 | Gold text and "caution" chips 3.7:1, long/short chips and footer link under 4.5:1 (light mode) | 1.4.3 | 🔴 | Darker light-mode gold, green and red |
| 2 | Input borders 1.35:1 | 1.4.11 | 🟡 | Borders ≥ 3:1 |
| 3 | 44 controls under 44×44px on phones (chips 31px, summaries 28px) | 2.5.5 | 🟡 | 44px minimum on touch layouts |
| 4 | Inputs at 13.5px make iOS Safari zoom on focus | usability | 🟡 | 16px inputs on phones |
| 5 | Tabs lack arrow-key support and tabpanel roles | 2.1.1, 4.1.2 | 🟡 | ARIA tabs pattern with roving focus |
| 6 | Closed settings sheet (phone) is still focusable off-screen; no Escape | 2.4.3 | 🟡 | `inert` when closed, Escape closes, focus moves into the sheet |
| 7 | Scrollable trade list and Pine code not keyboard-scrollable | 2.1.1 | 🟡 | `tabindex="0"` with labels |
| 8 | No level-one heading; toolbar outside a landmark | 1.3.1 | 🟢 | `h1` in the header; toolbar in a labelled region |
| 9 | Results update silently for screen readers | 4.1.3 | 🟢 | Polite live region announcing each run |
| 10 | Heatmap corner header empty | 1.3.1 | 🟢 | "Day" header |

Passed: 200% zoom without horizontal scroll, visible focus rings, labelled form fields, Escape closes the
Pine dialog, reduced-motion respected, dark-mode contrast (all key pairs ≥ 5.6:1).

## Verification

`tests/e2e/run.cjs` checks every item above automatically (axe scan with zero serious/critical issues,
tap-target sizes at 320, 390 and 768px, keyboard tabs, sheet focus, empty, error and skipped-signal states)
along with every feature of the page, locally and against the live site. `tests/test_webapi.py` runs every
strategy on every timeframe with both cost models and checks the numbers agree with each other.

Found while testing and fixed:

- The local preview server answered `GET ?op=backtest` with 400 while the live site answered 405; both now share one set of request rules.
- Runs with no trades reported a Sortino ratio of −1 and dropped the long/short trade counts; they now show n/a and 0.
- Strategy report pages: "info" chips at 4.3:1 contrast, scrollable tables not reachable by keyboard, empty table headers, no `main` landmark.
- Phone layout: the page heading was removed for screen readers below 640px; timeframe chips were 42px wide at 320px.
