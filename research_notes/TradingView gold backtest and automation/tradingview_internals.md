# TradingView internals, open pieces, official integration paths, and ToS/legal constraints (desk research, as of 25 Oct 2026)

Scope note: desk research only. No connection was made to any TradingView private endpoint. Protocol details below come from third-party open-source code and docs, not from TradingView. TradingView publishes no documentation for its websocket.

## Q1. Charting: Lightweight Charts (open source) vs Advanced Charts / Charting Library / Trading Platform

### Takeaway
Lightweight Charts is Apache-2.0, free and usable for personal projects. Its current core release is v5.2.1 (12 Aug 2026), and official plugin packages followed on 16 Sep 2026. It has no built-in indicators, and you push your own data into it. Advanced Charts and Trading Platform are proprietary and kept in a private GitHub repo. TradingView only gives them to companies for public, non-paywalled web projects ("not for personal use, hobbies, studies or testing"), and they pull data through the Datafeed API or the HTTP UDF protocol.

### Cited Findings
**Lightweight Charts (LWC)**
- License is Apache 2.0, and bundled tslib parts are BSD-0. The license "requires specifying TradingView as the product creator". You must include the NOTICE attribution text and a link to tradingview.com in your site or app. The `attributionLogo` chart option can provide that link on the chart. The repo has about 17.7k stars. — [GitHub tradingview/lightweight-charts](https://github.com/tradingview/lightweight-charts)
- Release timeline from the GitHub releases page. The page shows days and months but mostly omits years; the years below are inferred from order and the npm date:
  - v5.0.4 (24 Mar 2025): price-based marker positions `atPriceTop`, `atPriceBottom` and `atPriceMiddle`, plus `MagnetOHLC` crosshair mode.
  - v5.0.5 (27 Mar): marker plugin fix.
  - v5.0.6 (21 Apr): `seriesOrder()` and `setSeriesOrder()`.
  - v5.0.7 (16 May): price-scale visible range and marker `zOrder`.
  - v5.0.8 (26 Jun): expanded Pane API (`addPane`, `addDefaultPane`, stretch factors, `addSeries`/`addCustomSeries` on panes).
  - v5.0.9 (1 Oct): `rightOffsetPixels`, `pop`, screenshot options and marker `autoScale`.
  - v5.1.0 (16 Dec): data conflation for large datasets (`enableConflation`, `CustomConflationReducer`).
  - v5.2.0 (24 Apr 2026): `hoveredSeriesOnTop`, series hit-testing including a custom-series `hitTest()` hook, `defaultVisiblePriceScaleId` and `tickMarkDensity`.
  - v5.2.1 (12 Aug 2026): an "Agent Skill for AI coding assistants", faster crosshair/hover with markers on large datasets, and an Accessibility plugin example.
  - 16 Sep 2026: first official plugin packages. These are `@tradingview/lwc-toolkit` 1.0.0, ten plugins at 1.0.0 (accessibility, brushable area, stacked area, vertical line and others) and `create-lwc-plugin` 0.2.0. They need `lightweight-charts ^5.0.0` as a peer dependency. The page notes that "the library itself is unchanged, and its latest release remains v5.2.1." — [GitHub releases](https://github.com/tradingview/lightweight-charts/releases)
- A third-party npm mirror lists v5.2.0 as published 2026-04-24, which matches the releases page. — [DepScope](https://mcp.depscope.dev/pkg/npm/lightweight-charts)
- v4→v5 breaking changes:
  - `chart.addSeries(CandlestickSeries, opts)` replaces `addCandlestickSeries()`.
  - Series markers moved out of the series into a primitive. `series.setMarkers([...])` became `const m = createSeriesMarkers(series, [...]); m.setMarkers([...])`, and the marker object format is unchanged.
  - Watermark moved to `createTextWatermark(pane, ...)` and `createImageWatermark`.
  - Series types are imported individually for tree-shaking.
  - Plugin typings were renamed (`IPrimitivePaneView`, `IPrimitivePaneRenderer`). — [LWC v4→v5 migration guide](https://tradingview.github.io/lightweight-charts/docs/migrations/from-v4-to-v5)
- TradingView's product comparison calls LWC a "free, open-source client-side library" of about 45 KB with no built-in indicators (you implement them). You supply data directly, and the chart makes no requests. Advanced Charts asks you for data instead. Neither library contains market data. — [Product comparison](https://www.tradingview.com/charting-library-docs/latest/product-comparison)

**Advanced Charts / Trading Platform (proprietary)**
- TradingView does not provide the Advanced Charts and Trading Platform libraries "for personal use, hobbies, studies, or testing". These licenses go only to companies for public web projects or apps. It points personal projects to Lightweight Charts (Apache 2.0). — [TradingView free charting libraries page](https://www.tradingview.com/free-charting-libraries/)
- Advanced Charts is free provided the TradingView attribution stays visible and the deployment is public, meaning not private and not behind a paywall. — [Charting Library docs, Introduction](https://in.tradingview.com/charting-library-docs/latest/introduction/)
- The libraries sit in a private GitHub repo that needs an approved request. Getting the library from third-party services is "strictly prohibited and may lead to legal consequences". The library is not redistributable, and using any part of it in public repositories is prohibited. — [Charting Library docs, Get started](https://ar.tradingview.com/charting-library-docs/latest/quick-start.md)
- A third-party summary (checked Sep 2026) calls Advanced Charts a "proprietary agreement. Free with attribution for approved companies; not open source." — [LuxAlgo comparison](https://www.luxalgo.com/vela/compare/)
- Trading Platform adds trading UI such as `createOrderLine` ("Trading Platform only"). — [Product comparison](https://www.tradingview.com/charting-library-docs/latest/product-comparison)

**Datafeed API / UDF protocol shape**
- UDF is HTTP-based. The library ships a built-in `Datafeeds.UDFCompatibleDatafeed(datafeedURL, updateFrequency=10000ms, limitedServerResponse?)`. It has no real-time streaming out of the box, so for real-time data TradingView recommends implementing the JS Datafeed API instead. — [UDF docs](https://www.tradingview.com/charting-library-docs/latest/connecting_data/UDF/)
- UDF endpoints (same source):
  - `GET /config`
  - `/symbol_info?group=`
  - `/search?query&type&exchange&limit`
  - `/symbols?symbol=`
  - `/history?symbol&from&to&resolution&countback`
  - `/marks` and `/timescale_marks`
  - `/time` (Unix seconds)
  - `/quotes?symbols=` (Trading Platform)
- `/history` rules: `from` is the leftmost bar and `to` is exclusive, both in Unix seconds. `countback` takes priority over `from`.
- `/history` response is "table" style: `{s:"ok"|"error"|"no_data", errmsg?, t:[...], o:[...], h:[...], l:[...], c:[...], v:[...], nextTime?}`. Only `c` is required, prices must be numbers, and daily/monthly bar times should be 00:00 UTC. The adapter converts seconds to milliseconds.
- `/config` must set either `supports_search` or `supports_group_request` to true. Default resolutions are `1,5,15,30,60,1D,1W,1M`. `onReady` is the JS-API counterpart of `/config`. — [UDF docs](https://www.tradingview.com/charting-library-docs/latest/connecting_data/UDF/)
- Free TradingView widgets run on TradingView servers. You cannot connect your own data to them. — [Product comparison](https://www.tradingview.com/charting-library-docs/latest/product-comparison)

### Inferences
- A solo Singapore developer building a private backtester cannot legitimately use Advanced Charts. It is personal or private use, and it is not a company public project. **Lightweight Charts v5.x is the right chart.** Use `createSeriesMarkers` for trade entry/exit arrows, panes for indicator sub-panes, custom series and primitives for things like SL/TP boxes, and `enableConflation` for long M1 gold histories. Keep the NOTICE file and `attributionLogo` on.
- Even with LWC, design the Python data API around the UDF `/history` shape (`s,t,o,h,l,c,v`, Unix seconds, `countback`). This shape is well understood, maps one-to-one onto LWC bar arrays (seconds → `time`), and keeps a path open to Advanced Charts if the project ever becomes a public company product.

### Gaps
- No primary page was found stating a minimum browser or ES target for LWC v5.
- The full plugin list in the 16 Sep 2026 bundle was not enumerated.
- I could not fetch the Datafeed API method signatures (`resolveSymbol`, `getBars(symbolInfo, resolution, periodParams{from,to,countBack,firstDataRequest}, onResult, onError)`, `subscribeBars`, `unsubscribeBars`). The fetched UDF page confirmed only `onReady`, so check those signatures in the docs.
- The private repo and access process (application form, approval time) were not documented publicly in the pages fetched.

## Q2. Data transport: how tradingview.com gets live and historical bars (websocket protocol, auth, history limits)

### Takeaway
The web app streams bars over a websocket. Open-source clients connect to `wss://data.tradingview.com/socket.io/websocket` (despite the path, this is not standard Socket.IO). Messages are framed `~m~<len>~m~<json>`, with heartbeats `~h~<n>` that the client must echo back. JSON commands have the shape `{"m":method,"p":[params]}`. Clients create a `chart_session` and a `quote_session`, call `resolve_symbol`, then call `create_series(n_bars)`, and read bars from `timescale_update`/`du` packets until `series_completed`. Auth is an `auth_token` from the logged-in user (anonymous clients use `"unauthorized_user_token"`). History depth is capped by plan: 5k/10k/20k/25k/40k intraday bars, with daily intervals unlimited.

### Cited Findings
**Endpoint, framing and command sequence (from the tvDatafeed source code)**
- The source uses WS URL `"wss://data.tradingview.com/socket.io/websocket"` with a 5-second timeout and header `Origin: https://data.tradingview.com`. — [rongardF/tvdatafeed main.py](https://raw.githubusercontent.com/rongardF/tvdatafeed/main/tvDatafeed/main.py)
- Login is a POST of username, password and `remember:"on"` to `https://www.tradingview.com/accounts/signin/` with Referer `https://www.tradingview.com`. The token is read from `response.json()['user']['auth_token']`. Without it, the token falls back to `"unauthorized_user_token"` and the code logs that data may be limited. — [main.py](https://raw.githubusercontent.com/rongardF/tvdatafeed/main/tvDatafeed/main.py)
- Framing: the payload is `json.dumps({"m": func, "p": param_list}, separators=(",",":"))` with `~m~<len>~m~` prepended. — [main.py](https://raw.githubusercontent.com/rongardF/tvdatafeed/main/tvDatafeed/main.py)
  - Example I computed (length 54): `~m~54~m~{"m":"set_auth_token","p":["unauthorized_user_token"]}`
- Send sequence used for history:
  1. `set_auth_token [token]`
  2. `chart_create_session [cs, ""]`
  3. `quote_create_session [qs]`
  4. `quote_set_fields [qs, ...23 fields such as "ch","lp","volume","rtc"]`
  5. `quote_add_symbols [qs, symbol, {"flags":["force_permission"]}]`
  6. `quote_fast_symbols [qs, symbol]`
  7. `resolve_symbol [cs, "symbol_1", '={"symbol":..., "adjustment":"splits", "session":"regular"|"extended"}']`
  8. `create_series [cs, "s1", "s1", "symbol_1", interval, n_bars]`
  9. `switch_timezone [cs, "exchange"]` — [main.py](https://raw.githubusercontent.com/rongardF/tvdatafeed/main/tvDatafeed/main.py)
- Intervals and limits in that client: interval strings `"1","3","5","15","30","45","1H","2H","3H","4H","1D","1W","1M"`. The docstring gives `n_bars` max as 5000 (default 10).
- Parsing in that client: frames are concatenated, the `"s":[...]` block is matched by regex, and each bar is `[ts, o, h, l, c, v]` at split indices 4–9. Non-numeric volume becomes 0.0. It stops reading when a frame contains `"series_completed"`. — [main.py](https://raw.githubusercontent.com/rongardF/tvdatafeed/main/tvDatafeed/main.py)

**Heartbeats and session types (other unofficial clients)**
- Heartbeat packets are `~h~<number>`, and the client must echo them back. There is also a one-time "hello" handshake. The adapter describes the chart-session flow as: open a chart container, bind a symbol key to a market pair, then request N bars with `create_series`. It handles historical candles plus live bar updates. — [tradingview-api-adapter 2.0.0 README](https://unpkg.com/tradingview-api-adapter@2.0.0/README.md); [adapter type defs](https://app.unpkg.com/tradingview-api-adapter@2.0.0/files/dist/internal.d.ts)
- One websocket message can carry several back-to-back `~m~` frames. — [tradingview-api-adapter](https://unpkg.com/tradingview-api-adapter@2.0.0/README.md)
- tradingview-ws (unofficial) supports real-time data, candles, and authorization via a session ID taken from browser cookies. — [endenwer/tradingview-ws](https://github.com/endenwer/tradingview-ws)
- Mathieu2301/TradingView-API authenticates with the `sessionid` and `sessionid_sign` browser cookies. Without them you get "shorter intraday history, no Pine studies, and possibly delayed feeds". Its low-level API supports multiple charts and studies on one connection, replay mode and raw packets. — [Mathieu2301/TradingView-API](https://github.com/Mathieu2301/TradingView-API)
- tradingview-scraper needs a "TradingView WebSocket JWT token" (`websocket_jwt_token`) for streaming indicator data. — [tradingview-scraper on PyPI](https://pypi.org/project/tradingview-scraper/)

**History depth by plan (official)**
- Intraday history is 5,000 bars at the base level, 10,000 for Essential and Plus, 20,000 for Premium, 25,000 for Expert, and a maximum of 40,000 for Ultimate. Extra bars are added back to the start of the week, month or year. The limits "cannot be extended for now due to technical reasons." Daily-based intervals show "all available data." — [TradingView Help: Historical intraday data limits](https://www.tradingview.com/support/solutions/43000480679)
- Deep Backtesting runs on "all data available in TradingView's data storage" up to 2 million bars per calculation (the most recent 2M bars if the range is longer). Intraday storage is still limited. — [TradingView Help: Deep Backtesting data](https://www.tradingview.com/support/solutions/43000668210/)
- Bar Replay: Premium, Expert and Ultimate can replay all stored data, while Essential and Plus have time-based windows. — [TradingView Help: Bar Replay data](https://www.tradingview.com/support/solutions/43000692816)
- TradingView states that displayed prices for some feeds are "derived data". It "executes a 2-factor derivation process to produce the displayed price" for non-professional clients, and "at no point is raw data accessible by any client, nor can said data be reverse-engineered in any manner." — [TradingView Terms of Use §11](https://www.tradingview.com/policies/)

### Inferences
- **What a "TradingView-like" backtester has to replicate:**
  - A bar store with a UDF-like query (`symbol, resolution, from, to, countback`).
  - A streaming layer that pushes bar updates. The TradingView pattern updates the *last* bar in place until it closes. LWC's `series.update()` has the same semantics.
  - Symbol metadata: session, timezone, pricescale/minmov.
- **A scraped TradingView feed is a poor research base for XAUUSD.** Unofficial pulls are capped at about 5k bars per request (tvDatafeed) and 5k–40k intraday bars per plan, which is roughly 3.5–28 trading days of M1 gold. Some displayed prices may also be "derived" rather than raw. Deep M1 or tick history for gold should come from a broker or vendor such as OANDA, Dukascopy or the broker the user will execute on.
- Parsing tips if one ever reads such packets:
  - Split frames on `~m~` and echo `~h~` frames back.
  - Bars arrive as `{"i":idx,"v":[time,o,h,l,c,v]}` arrays under a series key. This structure is inferred from the tvDatafeed index positions.

### Gaps
- Alternate hosts (e.g. `prodata.tradingview.com` for paid accounts, `widgetdata.tradingview.com`) and URL query params (`?from=chart/&date=...&type=chart`) are commonly reported. I could not verify them this session, because the Mathieu2301 `src/client.js` path returned 404 after the repo moved to TypeScript (`src/client/`, `src/protocol/`).
- Exact method names for packet types (`timescale_update`, `du`, `symbol_resolved`, `protocol_error`, `critical_error`, `qsd`) were not confirmed from a fetched source in this session. Only `series_completed` was confirmed.
- How the newer JWT-style token is minted, and whether the cookie-session route has changed in 2026, is undocumented.
- Which feeds are subject to the §11 "derived data" process is not stated.
- Plus/Premium figures on the live pricing page were not directly confirmed. The Essential "10K historical bars" figure appears on [pricing](https://www.tradingview.com/pricing/) per search snippet.

## Q3. Open-source projects that reverse engineer TradingView: maintenance and reported bans, captchas and breakage (2025–2026)

### Takeaway
The ecosystem is alive but fragile. The best-maintained projects are Mathieu2301/TradingView-API (Node/TS, ~5.7k stars, v4 release-candidate in progress, now includes a backtest API) and tradingview-scraper (Python, v0.4.21 on 18 Sep 2026). The rongardF fork of tvDatafeed sees occasional activity (v2.2.0, ~Dec 2025) but has a history of captcha login failures. tradingview-ta has had no release since Oct 2022. Captcha (`recaptcha_required`) on username/password login is the most common breakage, so projects moved to pasting browser cookies or tokens.

### Cited Findings
- **Mathieu2301/TradingView-API** (npm `@mathieuc/tradingview`):
  - About 5.7k stars, 1.0k forks, 301 commits and 76 open issues. CI badge passes, and there is a "v4 RC preparation report" with remaining release gates.
  - Features: candles, quotes, screeners, indicator values, Pine studies (account required), strategy reports, and replay. It now has a Backtest API that "rejects look-ahead, fills at the next open, applies fees and slippage, in-sample/out-of-sample splits, random-entry baseline".
  - Requires Node 20+. It states it is not affiliated with or endorsed by TradingView, and tells users to check data-provider terms. It does not mention bans. The README also promotes a commercial hosted AI-agent service.
  - Source is now TypeScript with folders `backtest, chart, client, data, http, indicators, protocol, quote`.
  - — [GitHub repo](https://github.com/Mathieu2301/TradingView-API); [src tree](https://github.com/Mathieu2301/TradingView-API/tree/main/src)
- **rongardF/tvdatafeed** (the main Python fork of StreamAlpha's original tvDatafeed). Issue history:
  - #62 "Token is None even when providing username and password due to recaptcha_required" (7 Dec 2024, 20 comments).
  - #63 "tv.get_hist() stopped working?" (11 Dec 2024).
  - #66 "getting driver error" (Jan 2025).
  - #72 time-zone issue (Jul 2025, 7 comments).
  - #74 splits/dividends adjustment (Sep 2025).
  - #80 "Login attempt with new v2.2.0 blew up in my face" (14 Dec 2025).
  - #84 "Daily settlement as close on daily interval" (17 Mar 2026).
  - No maintainer replies were visible in the list view. — [tvdatafeed issues](https://github.com/rongardF/tvdatafeed/issues)
- **tradingview-scraper** (Python, MIT): v0.4.21 released 18 Sep 2026, previous v0.4.20 on 6 Dec 2025, with signed provenance.
  - Covers ideas, news, indicators, OHLCV over websocket, screener, fundamentals and calendars. Status is "2 - Pre-Alpha".
  - Docs say TradingView may show captchas when scraping Ideas pages, and the workaround is copying your browser cookie into `.env` as `TRADINGVIEW_COOKIE`. — [PyPI tradingview-scraper](https://pypi.org/project/tradingview-scraper/)
- **tradingview-ta** (Python): latest 3.3.0 on 5 Oct 2022, one maintainer. It returns TA summaries (BUY/NEUTRAL/SELL) and indicator values for many symbols per request, and has no rate-limit warnings. — [PyPI tradingview-ta](https://pypi.org/project/tradingview-ta/)
- Other unofficial clients: tradingview-api-adapter 2.0.0 (TypeScript) — [unpkg](https://unpkg.com/tradingview-api-adapter@2.0.0/README.md); tradingview-ws — [GitHub](https://github.com/endenwer/tradingview-ws)
- A third-party integrator warns that these tools rely on private, undocumented endpoints that "are not sanctioned, not stable", that using them "likely violates TradingView's terms of service", and that they can change "at any time without notice". — [TradersPost: TradingView API](https://blog.traderspost.io/article/tradingview-api); [TradersPost: data export](https://blog.traderspost.io/article/tradingview-data-export)

### Inferences
- If you use these at all, use them only for low-volume, manual-scale spot checks, e.g. to cross-check that your own engine's indicator values match TradingView's on a few bars. Do not build a production data pipeline on them. Breakage reports cluster around login and captcha changes (Dec 2024) and releases (Dec 2025).
- Authenticated use (cookies or token) ties scraping activity to the user's own TradingView account. That account is what gets banned (see Q4), so a paid plan is put at risk.

### Gaps
- No primary-source report was found of a named individual account banned specifically for using tvDatafeed or TradingView-API. Ban evidence is TradingView's own policy page, not incident reports.
- The last-commit date for Mathieu2301 and whether v4 final has shipped could not be read from the page.
- Status of the original StreamAlpha/tvdatafeed repo was not checked.

## Q4. Terms of Use: scraping, automated access, reverse engineering, redistribution, and enforcement

### Takeaway
TradingView's ToS licenses content and market data for display only and explicitly bans non-display use, which includes "automated trading, automated order generation". It forbids decompiling, reverse engineering and commercial use of its services or APIs. Its support site says automated collection ("scripts, APIs, screen scraping, data mining, robots") gets the account banned: temporary at first, permanent on repeat. The ToS is governed by New York law. The main enforcement on record is account bans, plus exchange or data-provider contracts that TradingView must pass down. I found no reported lawsuit against an individual scraper.

### Cited Findings
- §3, Ownership and display-only license: content and market data "are licensed for exclusive display-only use", and TradingView "explicitly prohibits any form of non-display usage". Examples include "automated trading, automated order generation, price referencing, order verification". — [Terms of Use](https://www.tradingview.com/policies/)
- §3 also covers "any machine-driven processes that do not involve the direct, human-readable display of such data". — [Terms of Use](https://www.tradingview.com/policies/)
- §3, Data Provider pass-through: "our agreements with Data Providers strictly forbid the sublicensing, assigning, transferring, selling, loaning…". Distributing "TradingView content, including market data, for any form of compensation" is prohibited. — [Terms of Use](https://www.tradingview.com/policies/)
- §3, Reverse engineering and commercial use: users may not, without prior written consent of TradingView and the relevant Data Providers, engage in "translating, decompiling, disassembling or creating derivative works". Also, "we do not permit commercial usage of any of our services or APIs." — [Terms of Use](https://www.tradingview.com/policies/)
- §11: derived data cannot "be reverse-engineered in any manner". — [Terms of Use](https://www.tradingview.com/policies/)
- §2: TradingView does "not guarantee backward compatibility of our services and Application Programming Interface (API)". — [Terms of Use](https://www.tradingview.com/policies/)
- §4: use of TradingView products and widgets outside the site must keep the original attribution. — [Terms of Use](https://www.tradingview.com/policies/)
- §18: TradingView may "without prior notice, immediately terminate, limit your access to or suspend your TradingView account". — [Terms of Use](https://www.tradingview.com/policies/)
- §28.11: "governed by the laws of New York, excluding its conflicts-of-law rules". The page shows © 2026 and no last-updated date. — [Terms of Use](https://www.tradingview.com/policies/)
- **Enforcement page:** the ban message reads "We noticed some suspicious activity on your account, so we've had to ban it." It is triggered by activity that "violates paragraph 3 of our Terms of Use".
  - Users are "strictly prohibited from employing any automated data collection methods, including but not limited to scripts, APIs, screen scraping, data mining, robots", and all features are "for manual use only".
  - First violations get a temporary ban of variable length, and "successive violations may lead to a permanent ban." — [TradingView Help: account banned for suspicious activity](https://www.tradingview.com/support/solutions/43000674726-why-is-my-account-banned-due-to-suspicious-activity/)
- The Charting Library docs warn that obtaining the library from third parties "may lead to legal consequences", and that public repositories must not contain any part of it. — [Charting Library Get started](https://ar.tradingview.com/charting-library-docs/latest/quick-start.md)
- TradingView describes itself as a vendor of official real-time exchange data (e.g. Nasdaq) for end users (§10). Some data is "available without additional per-user fees only" (§13.10), which reflects exchange licensing constraints. — [Terms of Use](https://www.tradingview.com/policies/)
- **Singapore angle:**
  - The Copyright Act 2021 added a "computational data analysis" exception. It allows copying works to "identify, extract and analyse information", conditional on "lawful access".
  - Contract terms that purport to exclude or restrict this exception are void. This also covers foreign-law contracts where the foreign-law choice is "wholly or mainly to evade" the exception. Commentators note "lawful access" is open to interpretation. — [Bird & Bird (2021)](https://www.twobirds.com/en/insights/2021/singapore/coming-up-in-singapore-new-copyright-exception-for-text-and-data-mining); [Hugh Stephens blog](https://hughstephensblog.net/tag/singapore-copyright-law/)

### Inferences
- **Practical risk ranking, lowest to highest:**
  1. Reading TradingView's public docs and using LWC: no risk.
  2. Manual CSV export of your own chart for personal analysis: within "manual use", though it is still display-licensed data, so keep it personal and don't redistribute it.
  3. Low-volume unofficial websocket pulls: ToS breach, with a temporary-ban risk for the logged-in account.
  4. Automated scraping at scale, captcha circumvention, or feeding TradingView data into live automated order generation: an explicit §3 non-display breach, a likely permanent ban, and possible data-provider claims.
  5. Redistributing data, or using leaked Charting Library code: highest risk, including legal action.
- **Singapore's exception does not solve the problem.** The CDA exception is about *copyright* in works. Raw prices are largely facts, and TradingView's main levers are *contract* (account termination) and *data-provider licences*, which the exception does not neutralise. "Lawful access" is also doubtful when the access itself breaches the ToS. Treat it as a minor mitigating factor at most. This is not legal advice.
- **There is a tension in TradingView's own model.** §3 bans "automated trading" as a non-display use of its market data, yet TradingView sells webhook alerts (see Q5) that third-party bridges use to auto-trade. The safest reading: TradingView's chart, alerts and webhooks may drive *your* broker orders through official features. Pulling TradingView's *data* into your own automated engine is the prohibited part. Generate signals in your own engine from broker or vendor data instead.

### Gaps
- No public lawsuit by TradingView against an individual scraper or open-source library author was found. The DMCA search returned no TradingView-specific GitHub notice.
- I did not verify the enacted section numbers of Singapore's Copyright Act 2021 for the CDA exception and its anti-contract-override clause. The draft bill listed the override in Clause 180, and commentary sometimes cites ss. 243–244 and 187. Check against Singapore Statutes Online before quoting.
- Applicability of Singapore's Computer Misuse Act to unauthenticated websocket access was not researched. No source was found.
- A search snippet said the Italian policy page bars third parties from building automated-trading products on TradingView data, alerts or webhooks. This was not verified on the English page.

## Q5. Official ways to get data out of TradingView, and official integration routes

### Takeaway
TradingView has no public market-data API. The official exits are: (a) manual "Download chart data…" CSV of loaded bars plus indicator values, on paid plans; (b) Strategy Report "Download" CSV per tab (List of Trades, Performance Summary); (c) Pine Script running on TradingView plus alerts and webhooks (webhooks need a paid plan and 2FA); and (d) the TradingView REST API for Brokers. Option (d) is a spec *brokers* implement so TradingView can trade through them, not a data API for users.

### Cited Findings
- **Chart CSV export:**
  - Supercharts menu → "Download chart data…" → select chart → Download. It saves "tickers and indicators" to CSV.
  - "The data you export is what your chart shows you", so to get more you must "scroll the chart left or drag the x-axis" first. The help page names no plan or bar cap. — [TradingView Help: How to export chart data](https://www.tradingview.com/support/solutions/43000537255-how-to-export-chart-data/)
  - Plan requirement conflicts between sources. A 2019 TradingView blog said PRO+/Premium only (older, likely outdated). — [TradingView blog 2019](https://www.tradingview.com/blog/en/export-chart-data-in-csv-14395). A recent third-party guide says it starts at Essential, with caps of 10K bars on Essential and Plus, 20K on Premium and 40K on Ultimate, matching the chart history limits. — [TradersPost](https://blog.traderspost.io/article/tradingview-data-export)
- **Strategy Report export:** the "Download" button exports each tab separately to CSV. The List of Trades tab gives trade rows, and Performance Summary gives metrics. — [TradingView Help: How to export strategy data](https://www.tradingview.com/support/solutions/43000613680-how-to-export-strategy-data/)
- **Webhook alerts:**
  - "webhook alerts are only allowed when 2-factor authentication is enabled." — [TradingView Help: webhooks](https://www.tradingview.com/support/solutions/43000529348-webhooks)
  - Most third parties put the lowest webhook-capable plan at Essential (Basic has none) — [CrossTrade](https://crosstrade.io/blog/tradingview-plan-for-webhook-alerts). One guide says Plus+ (conflicting) — [PickMyTrade](https://blog.pickmytrade.io/tradingview-webhook-automation-trading-alerts/)
- **TradingView REST API for Brokers:**
  - It is a spec for brokers to implement, connecting their backend to the TradingView web platform. Client requests come from the browser, server requests from TradingView. Polling intervals are set via `/config`, or a streaming connection is used.
  - It includes `/quotes` (bid/ask) and `/depth` (L2). Work happens in a sandbox copy of TradingView after automated tests and IP whitelisting.
  - Spec versions seen: 1.10.1 on id.tradingview.com, 1.9.2 on other mirrors, 1.7.1 on an old URL. — [Broker API docs](https://www.tradingview.com/broker-api-docs/); [REST spec 1.10.1](https://id.tradingview.com/broker-api-docs/rest-api-spec)
  - Access reportedly needs a brokerage partnership. — [Dashdevs (secondary)](https://dashdevs.com/blog/tradingview-api-integration/)
- "There's no general-purpose REST endpoint you can call with a symbol and a date range and get candles back." — [TradersPost](https://blog.traderspost.io/article/tradingview-api)
- Deep Backtesting (official, in-platform) covers up to 2M bars per run. — [TradingView Help](https://www.tradingview.com/support/solutions/43000668210/)
- Third-party Chrome extensions claim to export OHLC or trade lists, e.g. TradChart (free tier limited to 25 rows). — [Chrome Web Store](https://chromewebstore.google.com/detail/dafeajcefjolfbiigfkgddhgobfllcgi). These are unverified and still fall under "automated" collection risk.

### Inferences
- **Best legitimate workflow for this project:**
  1. Prototype strategies in Pine on TradingView.
  2. Export the Strategy Report "List of Trades" CSV and the chart CSV (with the strategy's plotted indicators) for a few windows.
  3. Use those exports as a golden reference to validate the Python engine's fills and indicator math on the same feed. Note the feed must match, e.g. OANDA:XAUUSD vs your broker.
  4. Run full-history backtests in Python on broker or vendor data.
  5. For live automation, either use TradingView alerts → webhook → your own executor (official feature, paid plan + 2FA), or run signals entirely in Python against the broker API.
- A Python backtester should copy TradingView's Strategy Tester conventions so the comparison is meaningful. Make these configurable:
  - fill on next bar open by default
  - commission and slippage settings
  - pyramiding
  - `process_orders_on_close`
  - intrabar fill assumptions (a "bar magnifier"-like option)

### Gaps
- No current official page was found that lists which plan unlocks "Download chart data" or the per-plan CSV bar cap. Check the live [pricing](https://www.tradingview.com/pricing/) page.
- Exact CSV column and timestamp formats (Unix vs ISO; time-zone handling) are not documented on the help page.
- Pine Script's current major version (v6 since late 2024) and any 2026 changes, such as new `request.*` limits, were not researched in this session.

## Q6. Gold symbols on TradingView and how they differ

### Takeaway
"Gold" on TradingView is several different series:
- broker or aggregator **spot** feeds that trade 24/5: OANDA:XAUUSD, FX:XAUUSD, FOREXCOM, PEPPERSTONE, CAPITALCOM and others
- ICE-sourced spot reference rates: FX_IDC:XAUUSD and IC:XAUUSD
- a TradingView composite "index": TVC:GOLD
- **COMEX futures**: GC1! (100 oz) and MGC1! (10 oz), on CME hours with a daily break and a contango basis over spot

Prices typically differ by cents to a few dollars. Backtests should use the feed of the broker you will actually execute on.

### Cited Findings
- Feed-by-feed summary from a Sep 2026 broker-affiliated guide, so treat it with care: — [For Traders, 16 Sep 2026 (Spanish)](https://fortraders.com/es/blog/xau-usd-tradingview-grafico-oro)
  - **OANDA:XAUUSD**: spot OTC (CFD-style) from OANDA. It trades 24/5 from Sun 5pm ET to Fri 5pm ET, is free with slight delay, and is quoted per 1 troy oz.
  - **FX:XAUUSD**: aggregated spot.
  - **TVC:GOLD**: a composite/reference index, "not an executable price". It can sit $3–$8 from actual fills.
  - **COMEX:GC1!**: continuous standard futures, 100 oz, on CME session hours with daily pauses. It needs a CME real-time subscription or uses free delayed data. It typically trades above spot due to contango, by $1–$2+.
  - **COMEX:MGC1!**: micro futures, 10 oz.
  - Spot-to-spot differences between two brokers are usually $0.20–$0.60. Picking the wrong ticker can shift entries and stops by about $0.20–$2.00/oz.
- FX_IDC:XAUUSD is titled "Gold Spot / U.S. Dollar", with ICE shown as the provider. The same page lists other XAUUSD feeds: IC (ICE), FOREXCOM, CAPITALCOM, PEPPERSTONE, and the related TVC:GOLD. — [TradingView symbol page FX_IDC:XAUUSD](https://www.tradingview.com/symbols/XAUUSD/?exchange=FX_IDC)
- COMEX:GC1! is "Gold Futures", COMEX, 100 OZT, a "Continuous contract" with front month shown as GCZ2026. The footer says "Select market data provided by ICE Data Services." — [TradingView COMEX:GC1!](https://www.tradingview.com/symbols/COMEX-GC1!/)
- TVC:GOLD is "Gold" quoted in USD. The page does not say whether it is a CFD or an index. — [TradingView TVC:GOLD](https://www.tradingview.com/symbols/TVC-GOLD/)
- tvDatafeed's `resolve_symbol` passes `"session":"regular"|"extended"` and `"adjustment":"splits"`. This shows that session selection is a parameter of the series. — [main.py](https://raw.githubusercontent.com/rongardF/tvdatafeed/main/tvDatafeed/main.py)
- A tvDatafeed issue (Mar 2026) concerns "Daily settlement as close on daily interval". This suggests futures daily bars may use the settlement price as the close, unlike spot. — [tvdatafeed issue #84](https://github.com/rongardF/tvdatafeed/issues)

### Inferences
- **The symbol model must carry metadata, not just a ticker.** Store `vendor:ticker`, instrument type (spot CFD / index / future), contract multiplier (1 oz vs 10 vs 100), tick size, session template, timezone, and for futures a roll rule. GC1! is a continuous back-adjusted-or-not series, and roll gaps will create fake signals if unadjusted.
- **Session hours affect bars directly.** For spot XAUUSD (24/5, daily break around 17:00 ET), the H4 and D1 bar boundaries depend on the session anchor. TradingView typically anchors FX and CFD daily bars at 17:00 New York, which you need to replicate to match TradingView candles. This is inferred and not verified in this session.
- **Volume on spot feeds is tick or broker volume, not exchange volume.** Volume-based indicators will differ between OANDA, FX_IDC and GC1!.
- For a Singapore user, CFD brokers licensed by MAS such as OANDA Asia Pacific, IG, Saxo and CMC will each have their own XAUUSD feed. Backtest on that broker's history where possible. This is inferred, and I did not verify broker-specific TradingView tickers for Singapore entities.

### Gaps
- TradingView's own definition of the "TVC" prefix (TradingView-computed composite vs. ICE-provided) was not stated on the fetched page.
- Official tick size, pricescale and session strings (e.g. `"1700-1700"`, timezone `America/New_York`) for each gold symbol were not retrievable from the public symbol pages.
- Whether FX_IDC:XAUUSD includes weekend gaps or holiday sessions differently from OANDA was not verified.
- Which gold feeds, if any, are subject to the §11 "derived data" transformation is unknown.
