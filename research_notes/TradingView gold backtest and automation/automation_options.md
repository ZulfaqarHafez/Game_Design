# Automating a backtested gold (XAUUSD) strategy: TradingView alerts, bridges, broker APIs, hosting, safety controls, and Singapore regulation

Research date: 25 Oct 2026. Several sources disagree. Every conflict is flagged where it appears. Prices are in USD unless stated.

---

## 1. TradingView alerts and webhooks: plans, placeholders, request format, IPs, ports, 2FA, reliability limits

### Takeaway
Webhooks need a paid TradingView plan and 2FA on the account. Each webhook is an HTTP POST to port 80 or 443, sent from four published IPv4 addresses. The receiver has 3 seconds to respond. TradingView documents no retries. An alert that fires more than 15 times in 3 minutes is stopped automatically. Strategy placeholders such as `{{strategy.order.action}}` let one alert carry every order a Pine strategy places. On Essential and Plus, alerts appear to expire after about 2 months, while Premium and Ultimate allow open-ended alerts. Sources conflict on this point; details below.

### Cited Findings
**Webhook mechanics (official Help Center)**
- Webhook alerts work only when 2-factor authentication is enabled on the TradingView account. — [TradingView: About webhooks](https://www.tradingview.com/support/solutions/43000529348-about-webhooks/)
- Each alert triggers an HTTP **POST** to the URL, with the alert message as the body. If the message is valid JSON, the `Content-Type` is `application/json`. Otherwise it is `text/plain`. — [TradingView: About webhooks](https://www.tradingview.com/support/solutions/43000529348-about-webhooks/)
- Only **ports 80 and 443** are accepted, and requests to other ports are rejected. — [TradingView: About webhooks](https://www.tradingview.com/support/solutions/43000529348-about-webhooks/)
- Timeout: "If a remote server takes longer than three seconds to process a request, the request will be cancelled." — [TradingView: About webhooks](https://www.tradingview.com/support/solutions/43000529348-about-webhooks/)
- Published source IPs for allowlisting: **52.89.214.238, 34.212.75.30, 54.218.53.128, 52.32.178.7**. IPv6 is not supported for webhooks. — [TradingView: About webhooks](https://www.tradingview.com/support/solutions/43000529348-about-webhooks/)
- The help page describes no automatic retries. Delivery failures appear in the "Webhook status" column of the alert log. TradingView advises against putting credentials or passwords in the webhook body and says to use authenticated, secured endpoints. — [TradingView: About webhooks](https://www.tradingview.com/support/solutions/43000529348-about-webhooks/)

**Alert placeholders (official Help Center)**
- General placeholders: `{{ticker}}`, `{{exchange}}` (delayed symbols get a `_DL`/`_DLY` suffix), `{{open}}`, `{{high}}`, `{{low}}`, `{{close}}`, `{{volume}}`, `{{time}}` (bar time in UTC, `yyyy-MM-ddTHH:mm:ssZ`), `{{timenow}}` (fire time, to the nearest second), `{{interval}}`, `{{syminfo.currency}}`, `{{syminfo.basecurrency}}`, `{{plot_0}}`…`{{plot_19}}` (first 20 series only), `{{plot("Name")}}`. Simple price alerts always use 1-minute bars. — [TradingView: variable values in alerts](https://www.tradingview.com/support/solutions/43000531021-how-to-use-a-variable-value-in-alert/)
- Strategy-only placeholders: `{{strategy.position_size}}`, `{{strategy.order.action}}` ("buy"/"sell"), `{{strategy.order.contracts}}`, `{{strategy.order.price}}`, `{{strategy.order.id}}` (the ID from strategy.entry/exit/order), `{{strategy.order.comment}}` (falls back to the order ID), `{{strategy.order.alert_message}}` (the `alert_message` argument of the order call, Pine v4+), `{{strategy.market_position}}` ("long"/"flat"/"short"), `{{strategy.market_position_size}}`, `{{strategy.prev_market_position}}`, `{{strategy.prev_market_position_size}}`. — [TradingView: variable values in alerts](https://www.tradingview.com/support/solutions/43000531021-how-to-use-a-variable-value-in-alert/)
- Placeholders in the `message` argument of `alertcondition()` are pulled into the alert text box (Pine v4+). — [TradingView: variable values in alerts](https://www.tradingview.com/support/solutions/43000531021-how-to-use-a-variable-value-in-alert/)

**Rate and reliability limits**
- A regular alert, or a script alert from `alert()`, that triggers **more than 15 times in 3 minutes is stopped automatically**. Each watchlist-alert symbol has its own 15-per-3-minute cap, and a whole watchlist alert stops at 1,000 triggers in 3 minutes. — [TradingView: Alert was triggered too often and stopped](https://th.tradingview.com/support/solutions/43000690939/); [TradingView: Alerts on alert() function](https://www.tradingview.com/support/solutions/43000597494-alerts-on-alert-function/)
- A strategy that flips back and forth on a fast chart can hit that limit in a busy minute. — [CrossTrade blog (third party)](https://crosstrade.io/blog/tradingview-webhook-not-working)
- Open-ended alerts are set under "Expiration" → "Open-ended" → "Set unexpired". They are unavailable for watchlist alerts. Even open-ended alerts can be auto-deactivated if they were created more than a year ago, have not triggered in over a year, and have not been edited in over a year. — [TradingView: Premium plan alerts still expiring in 2 months](https://www.tradingview.com:443/support/solutions/43000688759-i-upgraded-to-the-premium-plan-but-my-alerts-still-expiring-in-2-months/)

**Plans, alert counts, pricing**
- Official pricing page, annual billing shown as a monthly equivalent: Basic $0 (3 price alerts); Essential $12.95/mo (20 price + 20 technical alerts); Plus $29.95/mo (100 + 100); Premium $59.95/mo (400 + 400, plus 2 watchlist alerts); Ultimate $199.95/mo (1,000 + 1,000, plus 15 watchlist alerts). "Only the Ultimate plan is available for professional users." The checkmarks in the webhook column did not survive text extraction. — [TradingView pricing](https://www.tradingview.com/pricing/)
- A third-party guide (2026) says every paid plan supports webhooks and Basic does not. It puts monthly-billed list prices at about $14.95 / $34.95 / $69.95 / $239.95. — [CrossTrade: Which TradingView plan for webhooks](https://crosstrade.io/blog/tradingview-plan-for-webhook-alerts)
- **Conflict on expiry.** CrossTrade (third party, 2026) says Essential and Plus alerts expire after 2 months while Premium and Ultimate alerts are open-ended. The TradingView help article lists open-ended alerts for "Premium and Ultimate" in one version and "Premium, Expert and Ultimate" in another. My text extraction of the pricing page showed "alerts that don't expire" ticked for every paid plan, plus an unlabelled "1 mo. / 2 mo. / 2 mo." duration row. That extraction is unreliable. — [CrossTrade](https://crosstrade.io/blog/tradingview-plan-for-webhook-alerts); [TradingView help 43000688759](https://www.tradingview.com:443/support/solutions/43000688759-i-upgraded-to-the-premium-plan-but-my-alerts-still-expiring-in-2-months/); [TradingView pricing](https://www.tradingview.com/pricing/)
- One third-party source (NexusFi) uses outdated plan names and limits, and a wikibit blog gives different prices ($24.95 Plus, $49.95 Premium). Both should be discounted. — [CrossTrade summary of conflicting sources](https://crosstrade.io/blog/tradingview-plan-for-webhook-alerts)

**TradingView broker integration**
- OANDA is a supported broker in TradingView's trading panel, so users can trade OANDA accounts from TradingView charts. — [Finance Magnates](https://www.financemagnates.com/forex/technology/tradingview-integrates-oandas-api-expanded-deal/); [FinanceFeeds](https://financefeeds.com/oanda-users-now-can-trade-directly-from-tradingview-charts/)

### Inferences
- **The 3-second timeout means the receiver must acknowledge immediately.** It should validate, write to a durable queue, return 200, and place broker orders asynchronously. A synchronous broker call inside the handler risks a timeout, and TradingView documents no retry.
- **With no retries, alerts can be lost.** The live engine should reconcile its intended position against the broker's actual position on a timer instead of trusting that every alert arrived. Sending absolute target-position alerts (`{{strategy.position_size}}` / `{{strategy.market_position}}`) is more robust than sending only deltas (`{{strategy.order.action}}` + `{{strategy.order.contracts}}`). Losing one target-position message is self-correcting; losing one delta is not.
- **Authentication.** TradingView webhooks cannot add custom headers; nothing in the help page describes header configuration. The practical scheme is an IP allowlist of the 4 IPs, a random per-strategy secret in the JSON body or URL path (never a broker credential), TLS on 443, and strict JSON schema validation. This partly conflicts with TradingView's "no credentials in body" advice. A rotatable shared secret that cannot trade on its own is a reasonable compromise.
- **Use Premium or above for production bots** so alerts are open-ended and do not silently expire, or re-arm alerts on a calendar. Treat this as provisional until someone checks the live pricing page by hand.
- **Idempotency key.** `{{strategy.order.id}}` + `{{time}}` + `{{ticker}}` (or a key built in Pine and passed via `alert_message`) can dedupe repeated deliveries.
- Example JSON message for a strategy alert:
  `{"secret":"<rotating>","strategy":"gold_v1","symbol":"{{ticker}}","action":"{{strategy.order.action}}","qty":"{{strategy.order.contracts}}","target_pos":"{{strategy.position_size}}","price":"{{close}}","order_id":"{{strategy.order.id}}","bar_time":"{{time}}","fired":"{{timenow}}"}`
- TradingView's XAUUSD feed (e.g. OANDA:XAUUSD, FOREXCOM:XAUUSD) will differ slightly from the executing broker's quotes. Backtest on the same feed you execute on, or measure the basis.

### Gaps
- Webhook availability per plan was not readable from the official pricing page; the "all paid plans" claim comes from a third party.
- Alert expiry by plan conflicts across sources (see above). Verify on tradingview.com/pricing.
- No official TradingView figure was found for maximum payload size or retry behaviour. The help page says nothing on either.
- Whether the four IPs changed during 2025–2026 is unknown. The page shows the current list but no change history.

---

## 2. Bridge services: PineConnector, TradersPost, 3Commas, WunderTrading, Capitalise.ai, AutoView

### Takeaway
For spot XAUUSD, the only bridge relevant to MetaTrader is **PineConnector**. It now prices at about $59–$199/month and centres on MT5, with optional hosted MT5 instances in Virginia. **TradersPost** covers stocks, options, futures and crypto but not forex/CFDs, so it works only for gold *futures* (GC/MGC). **3Commas** and **WunderTrading** are crypto-exchange bots and do not fit spot gold CFDs. Capitalise.ai and AutoView could not be verified for 2026.

### Cited Findings
**PineConnector**
- Current tiers: **Core $59/mo** (launch price, rising to $69 after launch; 1 MT5 account; 1 hosted "Edge" MT5 instance), **Plus $129/mo** ($149 after launch; 3 accounts), **Pro $199/mo** (5 accounts, unlimited tasks, priority support). Trial: "7 days for $7". No annual pricing is listed. — [PineConnector pricing](https://www.pineconnector.com/pages/pricing)
- Every plan includes unlimited signals and "<1s typical" bridge latency, excluding webhook delivery and broker execution. Edge hosting is in Virginia, US, with London "coming in November". The page mentions only MT5, not MT4 or cTrader. — [PineConnector pricing](https://www.pineconnector.com/pages/pricing)
- How it works: TradingView alert → PineConnector Bridge → MetaTrader. You run MT5 plus the PineConnector EA on your own PC or VPS, or use the hosted Edge MT5. Example alert syntax: `60123456789,buy,XAUUSD,vol_lots=1`. The leading number appears to be the licence ID, but the page does not define it. — [PineConnector pricing](https://www.pineconnector.com/pages/pricing)

**TradersPost**
- Annual billing, shown as monthly equivalents: Starter $41.65 (1 live / 4 paper accounts, 1 asset class), Basic $84.15 (2 / 6, 2 classes), Pro $169.15 (3 / 8, 3 classes), Premium $254.15 (6 / 10, all classes). The free plan is a 7-day trial: manual submission on live accounts, automated submission on paper. Add-on accounts cost $10/mo live and $5/mo paper. Listed asset classes are stocks, options, futures and crypto; forex is not mentioned. — [TradersPost pricing](https://traderspost.io/pricing)
- Third-party sources list broker connections including Alpaca, TradeStation, Tradier, Interactive Brokers, Tradovate, NinjaTrader, ProjectX, Coinbase, Kraken, Binance and Bybit. They also quote different, older prices (e.g. $49/$99/$199/$299). — [PickMyTrade comparison](https://pickmytrade.io/compare/pickmytrade-vs-traderspost); [LuxAlgo review](https://www.luxalgo.com/blog/traderspost-autotrading-platform-reviewed/); [Benzinga](https://benzinga.com/money/traderspost-review)

**3Commas / WunderTrading**
- 3Commas offers a "Signal Bot" that executes TradingView alerts. Capterra lists the Pro tier at about $40/mo (20 signal bots, 3 accounts), and GetApp lists Starter at about $15/mo. Both describe crypto exchanges. — [Capterra](https://www.capterra.com/p/10030799/3Commas/); [GetApp](https://www.getapp.com/all-software/a/3commas)
- WunderTrading integrates with crypto exchanges such as Binance, Kraken, KuCoin and Bybit. No pricing was found. — [FinancialContent / GlobePRWire comparison](https://markets.financialcontent.com/franklincredit/article/globeprwire-2025-10-29-tradingview-bots-and-automation-comparing-the-best-platforms-for-crypto-bot-trading)

### Inferences
- A bridge adds a third party, a subscription and another point of failure, and a webhook still has to get from TradingView to the bridge. For a team already writing Python, a self-hosted webhook receiver feeding its own broker adapter is cheaper and allows proper risk checks. PineConnector makes sense only if the trader wants MT5 execution without writing code.
- Crypto bots (3Commas, WunderTrading) could trade gold-backed tokens such as PAXG/XAUT on crypto exchanges. That is a different instrument, with different custody, liquidity and regulatory risk. For a gold-CFD/XAUUSD strategy, treat it as out of scope.
- PineConnector's Edge servers in Virginia sit far from the Asian or London MT5 trade servers that Singapore-facing brokers use. This adds round-trip latency, which matters little for H1+ strategies but is worth measuring for scalping.

### Gaps
- **Capitalise.ai** and **AutoView**: no current (2025–2026) official pricing or broker lists were retrieved, so their status is unknown.
- PineConnector's MT4 support and its older, cheaper pricing could not be confirmed. The current page mentions only MT5.
- TradersPost's official broker list for 2026 was not on the pricing page.

---

## 3. Direct broker APIs for gold, and which ones Singapore residents can use under MAS regulation

### Takeaway
For a Singapore retail trader, the most practical direct API is **OANDA v20 REST**. It runs from Python on Linux, has a free practice environment, and the local entity is MAS-licensed (OANDA Asia Pacific Pte Ltd). **MT5 via the `MetaTrader5` Python package** works with many MAS-licensed brokers but needs Windows and a running terminal. **Interactive Brokers** documents XAUUSD as `CMDTY`, but its own campus page reportedly excludes IB Singapore customers from London spot gold, so IBKR is mainly a gold *futures* route. cTrader Open API, Saxo OpenAPI and IG are viable but need per-broker confirmation for retail XAUUSD API access.

### Cited Findings
**MetaTrader 5 Python package (`MetaTrader5` on PyPI)**
- Latest version 5.0.6231, released **27 Sep 2026**. Requires Python >=3.6,<4, with classifiers up to 3.14. Every wheel is tagged "Windows x86-64" and there is no source distribution, so the package is effectively Windows-only. — [PyPI: MetaTrader5](https://pypi.org/project/MetaTrader5/)
- `order_send(request)` sends a `MqlTradeRequest`-style dict. Fields: `action`, `magic`, `order`, `symbol`, `volume`, `price`, `stoplimit`, `sl`, `tp`, `deviation` (max slippage in points), `type`, `type_filling`, `type_time`, `expiration`, `comment`, `position`, `position_by`. It returns `OrderSendResult` with `retcode` (10009 = `TRADE_RETCODE_DONE`), `deal`, `order`, `volume`, `price`, `bid`, `ask`, `comment`, `request_id`, `retcode_external`, `request`. `last_error()` gives error detail, and `order_check` validates a request before sending. — [MQL5 docs: order_send](https://www.mql5.com/en/docs/python_metatrader5/mt5ordersend_py)
- The script connects to an installed MT5 terminal via `initialize()`. The symbol must be visible in Market Watch or enabled with `symbol_select`. The official example sends a 0.1-lot market buy with a 20-point deviation and SL/TP, then closes it by passing `position=<ticket>`. — [MQL5 docs: order_send](https://www.mql5.com/en/docs/python_metatrader5/mt5ordersend_py)

**OANDA v20 REST API**
- Base URLs: live REST `https://api-fxtrade.oanda.com`, practice REST `https://api-fxpractice.oanda.com`, live streaming `https://stream-fxtrade.oanda.com`, practice streaming `https://stream-fxpractice.oanda.com`. — [OANDA Development Guide](https://developer.oanda.com/rest-live-v20/development-guide/)
- Limits: **120 REST requests/second per IP** (HTTP 429 beyond that), **20 active streams per IP**, and no more than **2 new connections/second**. — [OANDA Development Guide](https://developer.oanda.com/rest-live-v20/development-guide/)
- Auth is `Authorization: Bearer <token>`, using a personal access token generated in the Account Management Portal ("Manage API Access") after accepting the API licence. — [OANDA Order endpoints](https://developer.oanda.com/rest-live-v20/order-ep/); [OANDA Getting Started](https://developer.oanda.com/rest-live-v20/introduction/)
- Orders: `POST /v3/accounts/{accountID}/orders` with body `{"order":{"type":"MARKET","instrument":"EUR_USD","units":"-100","timeInForce":"FOK","positionFill":"DEFAULT"}}`. Units are a string, and negative means sell. `stopLossOnFill`, `takeProfitOnFill` and `clientExtensions` (`id`, `tag`, `comment`) are supported. An order can be fetched by client ID: `GET /v3/accounts/{accountID}/orders/@<clientID>`. — [OANDA Order endpoints](https://developer.oanda.com/rest-live-v20/order-ep/)
- v20 accounts are "available to all divisions except OANDA Global Markets and OANDA TMS BROKERS S.A." — [OANDA Getting Started](https://developer.oanda.com/rest-live-v20/introduction/)
- OANDA's Singapore entity is **OANDA Asia Pacific Pte Ltd**, described by a third party as MAS-licensed. Its Singapore site lists OANDA web/mobile, TradingView, MT4, MT5 and the OANDA API. A third party says the customer agreement provides **no negative-balance protection**. — [CompareForexBrokers SG MT5](https://www.compareforexbrokers.com/sg/mt5/); [OANDA SG guides](https://www.oanda.com/sg-en/skills-and-insights/guides/); [CompareForexBrokers OANDA review](https://www.compareforexbrokers.com/sg/oanda-review/)
- Instrument naming uses underscores (`EUR_USD`), so gold should be `XAU_USD`. Candles accept `count` up to 5000, `granularity`, and `price` = M/B/A. The daily alignment default is 17:00 America/New_York. This comes from third-party wrapper docs, not OANDA's own pages. — [oandapyV20 docs](https://oanda-api-v20.readthedocs.io/en/latest/endpoints/instruments.html)

**Interactive Brokers**
- TWS API contract for spot gold: `symbol="XAUUSD"`, `secType="CMDTY"`, `exchange="SMART"`, `currency="USD"`. — [IBKR TWS API: Commodities](https://www.interactivebrokers.com/docs/tws-api/contracts/commodities.md)
- An IBKR Campus lesson, seen only as a search snippet because direct fetches returned HTTP 403, says London Spot Gold (XAUUSD) and Silver are available to most customers who are not residents of the US, Canada, Australia, Hong Kong or Japan, and **"are also not available to customers of IB Singapore."** US Spot Gold (USGOLD) is limited to US residents. — [IBKR Campus: Trading spot gold and silver](https://www.interactivebrokers.eu/campus/trading-lessons/trading-spot-gold-and-silver-using-ibkrs-tws/); [IBKR US Spot Gold](https://www.interactivebrokers.com/en/index.php?f=3187)
- Older forum reports say XAUUSD needs specific trading permissions and was missing from demo accounts. — [NinjaTrader forum](https://forum.ninjatrader.com/forum/ninjatrader-8/platform-technical-support-aa/104212-nt8-ib-cmdty-exchange-support-for-xauusd)
- Python: **`ib_async`** is the maintained successor to `ib_insync`, which was renamed after the original author died in early 2024. It requires Python >=3.10, and its first release was functionally equivalent to ib_insync 0.9.86. It is not affiliated with IBKR. — [PyPI: ib_async](https://pypi.org/project/ib_async); [GitHub mirror](https://github.com/ClimberMel/ib_async)

**cTrader Open API**
- Messages use Protobuf or JSON. Version 2.0 uses Protobuf only. The API is available to anyone registered with a cTrader-affiliated broker, and Spotware publishes an official open-source Python library (OpenApiPy) with samples. A Spotware sample app shows XAUUSD quotes on a demo account. — [cTrader Open API docs](https://help.ctrader.com/open-api/); [FX News Group](https://fxnewsgroup.com/forex-news/platforms/ctrader-open-api-gets-python-library/); [App Store: Open API Trader](https://apps.apple.com/us/app/-/id6476977387)

**Saxo OpenAPI**
- Saxo Capital Markets Pte Ltd is MAS-regulated. Its Singapore site offers spot gold, gold CFDs, futures, options and ETPs, plus an OpenAPI with a demo/simulation environment. Exchange market data needs separate licensing, and API questions go to openapisupport@saxobank.com. — [Saxo SG API](https://www.home.saxo/en-sg/platforms/api); [Saxo SG gold](https://www.home.saxo/en-sg/campaigns/trading-gold); [Saxo SG Excel/OpenAPI](https://www.home.saxo/en-sg/platforms/excel)

**IG Singapore**
- IG Asia Pte Ltd is MAS-regulated and holds a CMS licence. Spot gold (100 oz) CFDs carry a **20% retail margin (5:1)** with a minimum spread of 0.3. MT4 and ProRealTime appear in the site navigation. — [IG SG gold trading](https://www.ig.com/sg/commodities/gold-trading); [IG SG margin](https://ig.com/sg/charges/margin)

### Inferences
- **Comparison for this project:**
  - **OANDA v20.** Strongest fit for one Python codebase across backtest, paper and live. Linux/Docker-friendly REST and streaming, a free practice account that mirrors the live API (so paper→live is a URL and token change), `clientExtensions.id` for idempotency, and MAS-licensed locally. Downside: CFD/spot pricing with spreads and financing, and reportedly no negative-balance protection.
  - **MT5 (`MetaTrader5`).** Widest choice of brokers, and also the route PineConnector uses. Downsides: Windows-only Python wheels, a GUI terminal that must stay logged in, a single-terminal/single-account model, and a synchronous API. Plan on a Windows VPS. Linux setups via Wine exist, but they are unsupported and outside this research.
  - **IBKR.** Best for exchange-traded gold futures (COMEX GC/MGC) with transparent fees. London spot XAUUSD appears unavailable to IB Singapore clients. TWS or IB Gateway must run, and needs a daily restart/re-login. Futures roll logic is needed and changes the backtest.
  - **cTrader / Saxo / IG.** Possible, but each needs per-broker confirmation that a Singapore *retail* account can trade XAUUSD via API. They are less proven for this use case.
- Design a `Broker` interface (submit/cancel/positions/account/price stream) with adapters `PaperBroker`, `OandaBroker`, `MT5Broker` and `IBBroker`. The strategy code then never imports a broker SDK.

### Gaps
- **The XAU_USD instrument name** was not confirmed in OANDA's own docs. Verify it with `GET /v3/accounts/{id}/instruments` on a practice account.
- **Whether OANDA Asia Pacific (SG) accounts get v20 API access** is not stated in OANDA's docs (only the excluded divisions are listed). Third-party and OANDA SG pages list "OANDA API", but confirm with OANDA SG. OANDA SG's XAU/USD margin was not found.
- **IBKR Singapore exclusion** rests on a search snippet; the page itself returned 403. Confirm in Client Portal under trading permissions. Whether IB Singapore offers metal CFDs as an alternative was not researched.
- **IG REST API** details (endpoints, auth, availability for SG clients) were not retrieved.
- **MAS-licensed cTrader brokers** offering XAUUSD via Open API were not identified.
- **Saxo OpenAPI** retail eligibility and XAUUSD order support for SG clients are unconfirmed.

---

## 4. Hosting: running a bot 24/5 (Windows VPS for MT5), latency, uptime, costs

### Takeaway
MetaQuotes' built-in MQL5 VPS costs about $10–15/month per account, and some brokers subsidise it. Third-party Windows "forex VPS" plans start around $17–21/month. A Python bot on OANDA or IBKR can run on any small Linux VPS. MT5 needs Windows.

### Cited Findings
- MetaQuotes' native MQL5 VPS costs about **$10–15/month** depending on term (third-party, July 2026). — [NYC Servers blog](https://newyorkcityservers.com/blog/mql5-vps-vs-windows-vps)
- IG lists MQL5 VPS at about $15/month and free for IG clients holding at least $1,000. — [IG help: VPS on MT5](https://www.ig.com/en/help-and-support/platforms/mt5/how-to-access-vps-on-mt5)
- Older (2020) official-forum pricing: $15 for 1 month, $42 for 3, $79 for 6, $153 for 12, with 24 hours free for new users. This is likely outdated. You need one MQL5 VPS per trading account. — [MQL5 forum](https://www.mql5.com/en/forum/222058/6181337)
- Third-party MT5 VPS (New York City Servers): $16.67/month on an annual plan, $20.83 monthly. — [NYC Servers MT5 VPS](https://newyorkcityservers.com/mt5-vps)
- MT5 (`MetaTrader5` Python) wheels are Windows x86-64 only. — [PyPI: MetaTrader5](https://pypi.org/project/MetaTrader5/)

### Inferences
- MQL5's built-in VPS is designed to host MT5 terminals, EAs and indicators. It is not a general Windows box, so an external Python process running the `MetaTrader5` package needs a full Windows VPS. This is my understanding and not verified in a source this session.
- **Latency:** The webhook path is TradingView (US-based IPs) → your receiver → broker. For H1/H4 gold strategies, a few hundred ms is irrelevant. For M1 scalping, host the receiver and engine near the broker's trade server (often London or NY4/LD4 for FX/CFD brokers) and measure fill slippage in forward testing.
- **Uptime design:** Use systemd or Docker with restart=always, a heartbeat to Telegram or email, a daily restart window outside market hours (gold CFDs typically have a daily break around 17:00 New York), and state persisted to disk (SQLite) so a restart reconciles instead of re-entering trades.
- A small Linux VPS (1 vCPU / 1–2 GB) is enough for an OANDA/IBKR Python bot. IBKR additionally needs IB Gateway, which is Java and needs about 1–2 GB of RAM.

### Gaps
- No primary source this session gave current Linux VPS prices or uptime SLAs from mainstream providers in Singapore regions (e.g. AWS ap-southeast-1, DigitalOcean SGP).
- The current official MQL5 VPS price list was not retrieved directly.
- Broker trade-server locations for Singapore entities (OANDA SG, IG SG, etc.) were not found.

---

## 5. Safety controls: best practices for retail algo trading

### Takeaway
FIA's industry best practices (2024) are pre-trade limits (max order size, max intraday position, price tolerance), cancel-on-disconnect, kill switches, post-trade analysis and conformance testing. A retail bot should copy these in its own risk layer and add daily-loss stops, idempotent order IDs, broker reconciliation, news blackouts and an audit log. TradingView's alert behaviour (no retries, 3-second timeout, auto-stop at 15 triggers in 3 minutes) adds specific failure modes to defend against.

### Cited Findings
- FIA's July 2024 *Best Practices for Automated Trading Risk Controls and System Safeguards* lists pre-trade controls: **maximum order size, maximum intraday position, price tolerance, cancel-on-disconnect, kill switches**. It also covers exchange volatility controls, post-trade analysis and conformance testing, and says the practices apply to evolving technologies such as AI. — [FIA 2024 white paper (PDF)](https://fia.org/sites/default/files/2024-07/FIA_WP_AUTOMATED%20TRADING%20RISK%20CONTROLS_FINAL_0.pdf); [FIA announcement](https://www.fia.org/fia/articles/fia-releases-best-practices-automated-trading-risk-controls-and-system-safeguards)
- FIA guidance says a kill switch should disable a platform's trading and cancel resting orders. Kill switches are a last-resort control. — [FIA Order Handling for Executing Brokers](https://www.fia.org/sites/default/files/2019-05/Order-Handling-for-Executing-Brokers.pdf); [CFTC TAC FIA presentation](https://cftc.gov/media/2746/TAC100319_FIA/download)
- TradingView: no documented webhook retry, 3-second timeout, alerts auto-stopped above 15 triggers in 3 minutes, failures visible in the alert log. — [TradingView webhooks](https://www.tradingview.com/support/solutions/43000529348-about-webhooks/); [TradingView alert stopped](https://th.tradingview.com/support/solutions/43000690939/)
- OANDA: client-assigned order IDs via `clientExtensions.id`, retrievable via `/orders/@<id>`. Rate limits are 120 req/s and 2 new connections/s per IP. — [OANDA Order endpoints](https://developer.oanda.com/rest-live-v20/order-ep/); [OANDA Development Guide](https://developer.oanda.com/rest-live-v20/development-guide/)
- MT5: the `magic` field identifies the EA's orders, `deviation` caps slippage, `order_check` validates before sending, and `retcode` 10009 = done. — [MQL5 order_send](https://www.mql5.com/en/docs/python_metatrader5/mt5ordersend_py)
- OANDA's Japanese entity raised XAG/USD margin from 5% to 20% effective 2 Feb 2026. Brokers can change metals margin abruptly. — [Traders Union](https://tradersunion.com/news/brokers-news/show/1346613-oanda-japan-raises-margin/)

### Inferences (recommended control set for this project)
1. **Staged rollout:** backtest → walk-forward/out-of-sample → **paper/forward test** on a broker practice account (e.g. OANDA practice), long enough to cover several regimes and enough trades to compare against the backtest (rule of thumb: at least 4–8 weeks and 30+ trades) → live at minimum size → scale up. These thresholds are judgment, not a sourced standard.
2. **Pre-trade risk gate**, which every order passes regardless of signal source: max order size (lots/units), max net position, max orders per minute and day, price tolerance (reject if the requested price is more than X away from the latest broker quote), a spread filter (skip when the XAUUSD spread is above N points), a margin-usage cap, and allowed trading sessions.
3. **Loss limits:** a max daily loss in currency or % of equity, measured on equity including unrealised P&L, which flattens positions and blocks new entries until the next session. Add max weekly drawdown and a max consecutive-loss counter.
4. **Kill switch:** a single command (CLI, Telegram, or a flag file/DB row) that cancels all pending orders, optionally flattens, and refuses new orders until manually re-armed. Trigger it automatically on a loss limit, on a broker/position mismatch, or when the broker connection is lost beyond N seconds.
5. **Server-side protective stops on every entry** (OANDA `stopLossOnFill`, MT5 `sl`, IB bracket child) as the retail stand-in for exchange cancel-on-disconnect. Positions stay protected if the bot dies.
6. **Idempotency / duplicate protection:** derive a deterministic client order ID from (strategy, symbol, bar time, signal ID). Store it in SQLite before sending, reject repeats, and use broker client IDs (`clientExtensions.id`, MT5 `comment` + `magic`, IB `orderRef`) to check after a timeout whether the order actually went through before resending.
7. **Reconnect and reconciliation:** exponential backoff on reconnect. On every reconnect, and periodically, pull broker positions and orders and compare them with internal state. Never "replay" missed signals blindly; recompute the target position.
8. **Webhook hardening (TradingView path):** HTTPS on 443, the 4-IP allowlist, a per-strategy secret, JSON schema validation, a staleness check (reject if `timenow` is more than N seconds old), dedupe on order ID, and a 200 response within 3 seconds.
9. **News filter:** block new entries in a window (e.g. ±15–30 min) around high-impact USD releases (NFP, CPI, FOMC), which move gold sharply. Load them from an economic-calendar feed and log every block.
10. **Logging and audit trail:** append-only, structured (JSON) logs of every signal, risk decision, order request, broker response, fill and position snapshot, with UTC timestamps and the code version (git SHA). Run a daily P&L reconciliation against broker statements, and alert on errors.
11. **Same-code guarantee:** the strategy emits target positions or intents only. The backtest uses a simulated broker with realistic spread, slippage, commission and swap for XAUUSD, so live/backtest divergence comes down to fills, not code paths.

### Gaps
- The full text of the FIA 2024 PDF was not read, so no specific numeric thresholds are cited from it.
- No authoritative source was found that sets a minimum forward-testing period for retail algos.
- No MAS-specific guidance on retail-run automated trading controls was found. MAS's algo-trading expectations target licensed intermediaries; this was not researched in depth.

---

## 6. Regulatory notes for Singapore retail traders (CFDs, leveraged FX, gold, automated trading)

### Takeaway
MAS sets a **5% minimum margin (20:1)** for retail leveraged FX / FX CFDs. In 2014 it chose not to extend that rule to other underlyings, so gold CFD leverage is effectively set by each broker's margin policy. IG Singapore, for example, charges **20% margin (5:1)** on spot gold for retail. CFDs and leveraged FX are unlisted Specified Investment Products, so brokers must run a **Customer Knowledge Assessment (CKA)** before retail clients trade them. No MAS rule was found that prohibits a retail client from automating trades on their own account.

### Cited Findings
- In 2014 MAS adopted a **5% minimum margin** for CFDs on FX and other leveraged FX contracts with retail investors, in line with Hong Kong (5%) and Japan (4%). The minimum had previously been 2% (50x). MAS decided **not** to extend the CFD margin requirements to all other unlisted margined derivatives. It also imposed a S$5m base capital requirement on dealers serving retail clients in unlisted derivatives, implemented via SF(FMR) Regulations amendments. — [MAS Response to Feedback on Unlisted Margined Derivatives](https://www.mas.gov.sg/-/media/MAS/News-and-Publications/Consultation-Papers/Response-to-Feedback-on-Proposed-Regulatory-Requirements-for-Unlisted-Margined-Derivatives-Offered-to-Retail-Investors.pdf); [MAS CP P002-2014](https://www.mas.gov.sg/-/media/MAS/News-and-Publications/Consultation-Papers/Consult-paper--Legislative-Amendments-to-Regulatory-Requirements-for-Unlisted-Margined-Derivatives-Offered-to-Retail-Investors.pdf); [MAS 2012 consultation](https://www.mas.gov.sg/-/media/MAS/resource/publications/consult_papers/2012/28-May-2012-Review-of-Regulatory-Framework-for-Unlisted-Margined-Derivatives.pdf)
- Third-party Singapore broker guides consistently report retail major-FX leverage capped at **1:20**. — [ForexBrokers.com SG](https://www.forexbrokers.com/guides/singapore); [capitalmarkets.sg](https://capitalmarkets.sg/forex-cfd-brokers)
- **Gold leverage conflicts across sources:** IG Singapore (a primary broker source) charges **20% retail margin (5:1)** on spot gold. The MoneyBees blog lists gold at 10:1 (10% margin), GoodMoneyGuide says Singapore CFD brokers offer about 5:1 (20%) on gold, and LiquidityFinder lists SG gold at 20:1 and major FX at 50:1 (likely outdated). — [IG SG gold](https://www.ig.com/sg/commodities/gold-trading); [MoneyBees](https://themoneybees.co/blog/cfd-trading-for-beginners-ms); [GoodMoneyGuide SG](https://goodmoneyguide.com/sg/best-gold-trading-platforms-in-singapore/); [LiquidityFinder](https://liquidityfinder.com/insight/industry/comparison-of-cfd-retail-broker-leverage-limits-by-regulator)
- Accredited Investors can get higher leverage; IG reportedly allows up to 1:50 for AI status (third party). — [SeaMoneyTips](https://seamoneytips.com/best-forex-brokers-singapore-2026/)
- **MAS Notice SFA 04-N12 (Sale of Investment Products)** requires a **Customer Knowledge Assessment** before an intermediary transacts in *unlisted* Specified Investment Products for a retail customer. Listed SIPs require a Customer Account Review instead. — [MAS Notice SFA 04-N12](https://www.mas.gov.sg/regulation/notices/notice-sfa-04-n12); [MoneySense: SIPs](https://www.moneysense.gov.sg/investments/understanding-specified-investment-products/); [MAS 2011 media release](https://www.mas.gov.sg/news/media-releases/2011/mas-requires-intermediaries-to-assess-investment-knowledge-and-experience-of-retail-customers)
- Brokers treat CFDs and leveraged FX as unlisted SIPs that need a CKA. Typical pass criteria, which are alternatives, include at least 6 CFD or leveraged-FX trades in the past 3 years, relevant education or qualifications, or relevant work experience. City Index says a client who fails can still qualify via a short e-learning quiz. Criteria vary by firm. — [City Index SG CKA](https://cityindex.com/en-sg/customer-knowledge-assessment); [Phillip Nova CKA/CAR](https://www.phillipnova.com.sg/faq/risk-warning-statement-2/)
- MAS-regulated entities relevant here: OANDA Asia Pacific Pte Ltd (per a third party), IG Asia Pte Ltd (CMS licence), Saxo Capital Markets Pte Ltd, and IB Singapore. — [CompareForexBrokers](https://www.compareforexbrokers.com/sg/mt5/); [IG SG](https://www.ig.com/sg/commodities/gold-trading); [Saxo SG API](https://www.home.saxo/en-sg/platforms/api)
- OANDA SG reportedly offers no negative-balance protection, so leveraged losses can exceed the deposit. — [CompareForexBrokers OANDA review](https://www.compareforexbrokers.com/sg/oanda-review/)

### Inferences
- In practice, expect about **5:1 to 10:1 on gold CFDs** at Singapore-licensed brokers for retail clients. Position sizing in the backtest should use the actual broker's margin, not offshore 1:100+ figures, or margin calls will not be modelled.
- Using an offshore broker to get higher leverage removes MAS protections (segregation rules, dispute channels). For a Singapore resident, a MAS-licensed entity is the safer default.
- The MAS margin rules were found in 2012–2014 documents. The SF(FMR) Regulations may have been amended since, so check current text before quoting a figure as law.
- Bridge or VPS providers (PineConnector, TradingView) are not brokers and are not MAS-regulated. Their failures are not covered by broker protections, which is another argument for broker-side stops.

### Gaps
- I found no current (2024–2026) MAS primary text that states the gold CFD margin rule specifically; whether one exists is unconfirmed.
- No MAS guidance aimed at *retail clients* running their own automated trading was found.
- The latest amendment date of SFA 04-N12 is unclear; one source says 2018.
- I did not research tax treatment of trading gains in Singapore, which matters if trading becomes frequent.

---

## 7. Comparison of automation routes and recommended architecture

### Takeaway
Recommended setup: a **self-hosted Python engine** where the strategy, risk gate and broker adapters are shared between backtest and live. Use **OANDA v20 practice → OANDA SG live** as the default path, with **MT5** (Windows VPS) and **IBKR futures** as alternate adapters. TradingView is an **optional signal adapter** behind a hardened webhook receiver that feeds the *same* risk gate. Bridges such as PineConnector are a no-code fallback, not the core.

### Cited Findings
(Supporting facts are cited in sections 1–6. Key comparison inputs are restated here with sources.)
- TradingView webhooks: paid plan, 2FA, ports 80/443, 3 s timeout, 4 IPv4 sources, no documented retries. — [TradingView webhooks](https://www.tradingview.com/support/solutions/43000529348-about-webhooks/)
- PineConnector: $59–$199/month, MT5-centred, hosted Edge in Virginia. — [PineConnector pricing](https://www.pineconnector.com/pages/pricing)
- TradersPost: covers stocks, options, futures and crypto, from $41.65/month (annual). — [TradersPost pricing](https://traderspost.io/pricing)
- OANDA v20: practice and live hosts, 120 req/s, Bearer token, client order IDs. — [OANDA Development Guide](https://developer.oanda.com/rest-live-v20/development-guide/); [OANDA Order endpoints](https://developer.oanda.com/rest-live-v20/order-ep/)
- MT5 Python: Windows-only wheels, needs a running terminal. — [PyPI MetaTrader5](https://pypi.org/project/MetaTrader5/); [MQL5 order_send](https://www.mql5.com/en/docs/python_metatrader5/mt5ordersend_py)
- IBKR: XAUUSD is `CMDTY`/`SMART`/`USD`, reportedly unavailable to IB Singapore customers. — [IBKR TWS API Commodities](https://www.interactivebrokers.com/docs/tws-api/contracts/commodities.md); [IBKR Campus](https://www.interactivebrokers.eu/campus/trading-lessons/trading-spot-gold-and-silver-using-ibkrs-tws/)

### Inferences
**Route comparison**

| Route | Signal source | Execution | Monthly cost (approx.) | Main risks |
|---|---|---|---|---|
| A. TradingView → PineConnector → MT5 | Pine strategy | MT5 broker (MAS-licensed options exist) | TV Premium about $60–70 + PineConnector $59–199 (+ VPS if self-hosting MT5) | Two third parties; no retries; limited custom risk logic; Pine and Python logic drift apart |
| B. TradingView → own webhook receiver → Python risk gate → broker API | Pine strategy | OANDA / MT5 / IB adapter | TV Premium about $60–70 + VPS | Lost alerts (no retry); Pine and Python strategy versions must be kept in sync; webhook security |
| C. Python engine (signals from broker data) → risk gate → broker API | Python strategy (same code as backtest) | OANDA / MT5 / IB adapter | VPS only (+ optional TV for charting) | You own all ops: uptime, reconnects, data quality |
| D. TradersPost / 3Commas / WunderTrading | Pine | Futures or crypto brokers only | $15–254 | Not suitable for spot XAUUSD CFDs |

**Recommended architecture (route C as the core, B as an optional input)**
- `strategy/` holds pure functions or classes: `on_bar(bar, state) -> TargetPosition`. They do no I/O, and the same module is imported by both backtester and live runner.
- `data/` provides a historical loader (broker candles, e.g. OANDA `XAU_USD` M1/M5, or CSV) and a live feed (OANDA pricing stream / MT5 `copy_rates` polling / IB `reqRealTimeBars`). Bars are normalised to UTC.
- `signals/` has `InternalSignalSource` (runs the strategy on live bars) and `TradingViewWebhookSource`: a FastAPI/uvicorn app behind TLS on 443, with the 4-IP allowlist, secret, schema validation, staleness check, dedupe, enqueue, and a reply under 3 s.
- `risk/` is the RiskGate. It enforces max order size, max position, max daily loss, price tolerance, spread filter, session and news blackout, rate limits and the kill switch, and every order passes through it whatever the signal source.
- `execution/` contains OrderManager (idempotent client IDs, retry with lookup-before-resend, protective SL on every entry) plus a `Broker` protocol with `PaperBroker` (simulated fills, also used in backtest), `OandaBroker` (practice/live by config), `MT5Broker` (Windows only) and `IBBroker` (futures).
- `state/` uses SQLite (orders, fills, positions, signal IDs, daily P&L) and a reconciler that runs on startup, on reconnect and every N minutes.
- `ops/` covers structured JSON logs, a Telegram/email alerting heartbeat, a daily report, and a `KILL` flag file or Telegram `/kill` command.
- Deployment: Linux VPS + Docker for OANDA/IB; Windows VPS for MT5. Config switches `mode: backtest | paper | practice | live`, and live mode needs an explicit flag plus a smaller default size.
- Rollout: paper (internal PaperBroker on live data) → OANDA practice account → live at minimum units → scale up after the forward-test metrics match the backtest within tolerance.

### Gaps
- Real end-to-end latency (TradingView fire → broker fill) for each route was not measured or found in sources.
- Total cost depends on broker spreads and financing for XAUUSD at OANDA SG / IG SG / MT5 brokers, which were not researched in detail.
