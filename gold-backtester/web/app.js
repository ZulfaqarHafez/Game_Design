/* Gold Strategy Lab: browser side of the backtester.
   All calculations happen in the Python API (/api/lab); this file draws the results. */
(function () {
  "use strict";
  var API = "/api/lab";
  var L = window.LightweightCharts;
  var $ = function (id) { return document.getElementById(id); };
  var state = {
    meta: null, strategies: {}, current: null, tf: null, days: null, preset: "realistic",
    custom: null, result: null, filter: "all", extra: null, selected: null, priceLines: [], plotSeries: [],
    seq: 0, showBH: false, locked: false,
  };
  var store = {
    get: function (k, d) { try { var v = localStorage.getItem("gsl:" + k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
    set: function (k, v) { try { localStorage.setItem("gsl:" + k, JSON.stringify(v)); } catch (e) { /* storage blocked */ } },
  };
  window.__gsl = state;   // read-only hook for the end-to-end tests

  // ---------------------------------------------------------------- shared API for indicators.js, draw.js, replay.js
  var hooks = {};
  var TF_SEC = { "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400, "1d": 86400 };
  var GSL = window.GSL = {
    state: state, store: store, L: window.LightweightCharts,
    bars: null, shown: 0, tf: null, barSec: 3600, clickConsumedAt: 0, onChartClick: null, replayActive: false,
    on: function (evt, fn) { (hooks[evt] = hooks[evt] || []).push(fn); },
    emit: function (evt, arg) { (hooks[evt] || []).forEach(function (fn) { try { fn(arg); } catch (e) { if (window.console) console.error(e); } }); },
    // bars on the price chart, as columns {t, o, h, l, c, v}; `shown` is how many are visible (replay hides the future)
    setBars: function (b, tf, shown) {
      GSL.bars = b; GSL.tf = tf || GSL.tf; GSL.barSec = TF_SEC[GSL.tf] || 3600;
      GSL.shown = shown === undefined ? b.t.length : shown; GSL.emit("bars", GSL.shown);
    },
    indexOfTime: function (t) {
      var T = GSL.bars && GSL.bars.t, lo = 0, hi = GSL.shown - 1;
      if (!T) return -1;
      while (lo <= hi) { var mid = (lo + hi) >> 1; if (T[mid] === t) return mid; if (T[mid] < t) lo = mid + 1; else hi = mid - 1; }
      return -1;
    },
    timeToLogical: function (t) {
      var T = GSL.bars && GSL.bars.t, n = GSL.shown; if (!T || !n) return null;
      if (t <= T[0]) return (t - T[0]) / GSL.barSec;
      if (t >= T[n - 1]) return n - 1 + (t - T[n - 1]) / GSL.barSec;
      var lo = 0, hi = n - 1;
      while (hi - lo > 1) { var mid = (lo + hi) >> 1; if (T[mid] <= t) lo = mid; else hi = mid; }
      return lo + (t - T[lo]) / (T[hi] - T[lo]);
    },
    logicalToTime: function (i) {
      var T = GSL.bars && GSL.bars.t, n = GSL.shown; if (!T || !n) return null;
      i = Math.round(i);
      if (i < 0) return T[0] + i * GSL.barSec;
      if (i >= n) return T[n - 1] + (i - n + 1) * GSL.barSec;
      return T[i];
    },
    shiftTime: function (t, di) { var lg = GSL.timeToLogical(t); return lg === null ? t : GSL.logicalToTime(Math.round(lg) + di); },
    setPanes: function (k) { var el = document.getElementById("chart"); if (el) el.style.setProperty("--panes", String(k)); },
  };

  // ---------------------------------------------------------------- formatting
  function money(v, dp) {
    if (v === null || v === undefined || isNaN(v)) return "n/a";
    dp = dp === undefined ? 2 : dp;
    if (Math.abs(v) < Math.pow(10, -dp) / 2) v = 0;
    var s = Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: dp, maximumFractionDigits: dp });
    return (v < 0 ? "-$" : "$") + s;
  }
  function num(v, dp) {
    if (v === null || v === undefined || isNaN(v)) return "n/a";
    if (!isFinite(v)) return "∞";
    dp = dp === undefined ? 2 : dp;
    if (Math.abs(v) < Math.pow(10, -dp) / 2) v = 0;
    return v.toLocaleString("en-US", { minimumFractionDigits: dp, maximumFractionDigits: dp });
  }
  function pct(v, dp) { return v === null || v === undefined ? "n/a" : num(v, dp === undefined ? 2 : dp) + "%"; }
  function cls(v) { return v > 0 ? "pos" : v < 0 ? "neg" : ""; }
  function esc(s) { return String(s === undefined || s === null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function dt(ts) { return new Date(ts * 1000).toISOString().slice(0, 16).replace("T", " "); }
  function tok(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }
  function toast(msg) { var t = $("toast"); t.textContent = msg; t.hidden = false; clearTimeout(toast.t); toast.t = setTimeout(function () { t.hidden = true; }, 3200); }
  function announce(msg) { var a = $("announce"); a.textContent = ""; setTimeout(function () { a.textContent = msg; }, 50); }
  function humanize(key) {
    var words = String(key).split("_").map(function (w) { return /^(atr|rsi|ema|sma|tp|sl|r)$/i.test(w) ? w.toUpperCase() : w; });
    var s = words.join(" ");
    return s.charAt(0).toUpperCase() + s.slice(1);
  }

  // ---------------------------------------------------------------- api
  function api(op, body) {
    var opts = body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {};
    return fetch(API + "?op=" + op, opts).then(function (r) {
      return r.json().catch(function () { return { error: "The server returned an unexpected response (" + r.status + "). Try again in a moment." }; })
        .then(function (j) { if (!r.ok || j.error) throw new Error(j.error || ("Request failed (" + r.status + ")")); return j; });
    }, function () { throw new Error("Can't reach the backtest server. Check your connection and try again."); });
  }

  // ---------------------------------------------------------------- charts
  function chartOpts() {
    return {
      autoSize: true,
      layout: { background: { color: tok("--panel") }, textColor: tok("--muted"), fontFamily: "JetBrains Mono, monospace", fontSize: 11,
        panes: { separatorColor: tok("--line"), enableResize: false } },
      grid: { vertLines: { color: tok("--line") }, horzLines: { color: tok("--line") } },
      rightPriceScale: { borderColor: tok("--line") },
      timeScale: { borderColor: tok("--line"), timeVisible: true, secondsVisible: false },
      crosshair: { mode: 0 },
    };
  }
  var dollars = { type: "custom", minMove: 1, formatter: function (v) { return "$" + Math.round(v).toLocaleString("en-US"); } };
  var price, candles, markers, eqChart, eqSeries, bhSeries, ddSeries;
  function initCharts() {
    if (!L) { $("chart").textContent = "The chart library could not load. Check your connection and reload."; return; }
    price = L.createChart($("chart"), chartOpts());
    candles = price.addSeries(L.CandlestickSeries, { upColor: tok("--chart-up"), downColor: tok("--chart-down"), borderVisible: false,
      wickUpColor: tok("--chart-up"), wickDownColor: tok("--chart-down") });
    markers = L.createSeriesMarkers(candles, []);
    price.subscribeCrosshairMove(legendUpdate);
    price.subscribeClick(function (p) {
      if (Date.now() - (GSL.clickConsumedAt || 0) < 400) return;      // a drawing tool used this click
      if (GSL.onChartClick && GSL.onChartClick(p)) return;            // bar replay is picking a start bar
      var r = state.result; if (!r || !p || !p.time || state.locked) return;
      var t = r.trades.find(function (x) { return x.entry_time === p.time || x.exit_time === p.time; }) ||
        r.trades.find(function (x) { return x.entry_time <= p.time && p.time <= x.exit_time; });
      if (t) focusTrade(t, true);
    });
    eqChart = L.createChart($("equity"), chartOpts());
    eqChart.applyOptions({ timeScale: { minBarSpacing: 0.001 } });
    eqSeries = eqChart.addSeries(L.AreaSeries, { lineColor: tok("--gold"), topColor: tok("--gold-soft"), bottomColor: "rgba(0,0,0,0)",
      lineWidth: 2, priceLineVisible: false, priceFormat: dollars });
    bhSeries = eqChart.addSeries(L.LineSeries, { color: tok("--muted"), lineWidth: 1, lineStyle: 2, priceLineVisible: false,
      lastValueVisible: false, priceFormat: dollars, visible: false });
    ddSeries = eqChart.addSeries(L.HistogramSeries, { color: tok("--chart-down"), priceLineVisible: false, lastValueVisible: false,
      priceFormat: { type: "custom", minMove: 0.01, formatter: function (v) { return v.toFixed(1) + "%"; } } }, 1);
    try { eqChart.panes()[1].setHeight(70); } catch (e) { /* older library */ }
    var rethemer = function () {
      [price, eqChart].forEach(function (c) { c.applyOptions(chartOpts()); });
      candles.applyOptions({ upColor: tok("--chart-up"), downColor: tok("--chart-down"), wickUpColor: tok("--chart-up"), wickDownColor: tok("--chart-down") });
      eqSeries.applyOptions({ lineColor: tok("--gold"), topColor: tok("--gold-soft") });
      bhSeries.applyOptions({ color: tok("--muted") });
      if (state.result) { drawMarkers(); drawEquity(); }
    };
    try { window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", rethemer); } catch (e) { /* old browser */ }
    new MutationObserver(rethemer).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  }
  var plotColors = ["#3d7bd9", "#a65fc4", "#d0801f", "#2f9e9e", "#7d8a2a"];
  function legendUpdate(p) {
    var r = state.result; if (!r) return;
    var c = null, B = GSL.bars;
    if (p && p.time && p.seriesData) c = p.seriesData.get(candles);
    if (!c && B && GSL.shown) { var i = GSL.shown - 1; c = { open: B.o[i], high: B.h[i], low: B.l[i], close: B.c[i] }; }
    var head = "<span><b>XAUUSD</b> " + esc(GSL.tf || r.data.timeframe) + (GSL.replayActive ? " · replay" : "") + "</span>";
    if (c) head += "<span>O <b>" + num(c.open) + "</b> H <b>" + num(c.high) + "</b> L <b>" + num(c.low) + "</b> C <b>" + num(c.close) + "</b></span>";
    if (!GSL.replayActive) Object.keys(r.plots).forEach(function (name, k) {
      head += '<span><i class="sw" style="background:' + plotColors[k % plotColors.length] + '"></i>' + esc(name) + "</span>";
    });
    $("legend").innerHTML = head;
  }
  function drawMarkers() {
    var r = state.result; if (!r || !markers) return;
    var first = r.candles.length ? r.candles[0][0] : 0;
    var up = tok("--chart-up"), down = tok("--chart-down"), mk = [];
    var labels = r.trades.length <= 150;   // dense charts read better with bare markers
    r.trades.forEach(function (t) {
      var long = t.side === "long";
      if (t.entry_time >= first) mk.push({ time: t.entry_time, position: long ? "belowBar" : "aboveBar", shape: long ? "arrowUp" : "arrowDown", color: long ? up : down, text: labels ? (long ? "Long" : "Short") : "" });
      if (t.exit_time >= first) mk.push({ time: t.exit_time, position: long ? "aboveBar" : "belowBar", shape: "circle", color: t.pnl >= 0 ? up : down, size: 0.6, text: labels ? (t.pnl >= 0 ? "+" : "") + Math.round(t.pnl) : "" });
    });
    (r.open_trades || []).forEach(function (t) {
      if (t.entry_time >= first) mk.push({ time: t.entry_time, position: t.side === "long" ? "belowBar" : "aboveBar", shape: t.side === "long" ? "arrowUp" : "arrowDown", color: tok("--gold"), text: "Open" });
    });
    mk.sort(function (a, b) { return a.time - b.time; });
    markers.setMarkers(mk);
  }
  function drawEquity() {
    var r = state.result; if (!r || !eqSeries) return;
    eqSeries.setData(r.equity.map(function (p) { return { time: p[0], value: p[1] }; }));
    bhSeries.setData((r.buyhold || []).map(function (p) { return { time: p[0], value: p[1] }; }));
    bhSeries.applyOptions({ visible: state.showBH });
    $("bh-key").hidden = !state.showBH;
    var down = tok("--chart-down");
    ddSeries.setData(r.drawdown.map(function (p) { return { time: p[0], value: p[1], color: down }; }));
    eqChart.timeScale().fitContent();
  }
  function columns(rows) {
    var b = { t: [], o: [], h: [], l: [], c: [], v: [] };
    rows.forEach(function (c) { b.t.push(c[0]); b.o.push(c[1]); b.h.push(c[2]); b.l.push(c[3]); b.c.push(c[4]); b.v.push(c[5] || 0); });
    return b;
  }
  function drawChart() {
    var r = state.result;
    if (GSL.replayActive) { drawEquity(); return; }       // bar replay owns the price chart until it ends
    candles.setData(r.candles.map(function (c) { return { time: c[0], open: c[1], high: c[2], low: c[3], close: c[4] }; }));
    GSL.setBars(columns(r.candles), r.data.timeframe);
    state.plotSeries.forEach(function (s) { price.removeSeries(s); });
    state.plotSeries = [];
    Object.keys(r.plots).forEach(function (name, k) {
      var s = price.addSeries(L.LineSeries, { color: plotColors[k % plotColors.length], lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
      s.setData(r.plots[name].map(function (p) { return { time: p[0], value: p[1] }; }));
      state.plotSeries.push(s);
    });
    clearSelection();
    drawMarkers();
    var n = r.candles.length;
    if (n > 300) price.timeScale().setVisibleLogicalRange({ from: n - 300, to: n + 5 }); else price.timeScale().fitContent();
    legendUpdate(null);
    var note = r.data.bars.toLocaleString() + " bars, " + r.data.start.slice(0, 10) + " → " + r.data.end.slice(0, 10) + " · data: " + (r.data.source || "Dukascopy");
    if (r.data.candles_shown < r.data.bars) note += " · chart shows the last " + r.data.candles_shown.toLocaleString() + " bars";
    $("chart-note").textContent = note;
    drawEquity();
  }
  function clearSelection() {
    state.priceLines.forEach(function (l) { candles.removePriceLine(l); });
    state.priceLines = [];
    state.selected = null;
    $("trade-nav").hidden = true;
    document.querySelectorAll("#trades tr.sel").forEach(function (tr) { tr.classList.remove("sel"); });
  }
  function stepTrade(dir) {
    var tr = state.result.trades, i = tr.findIndex(function (t) { return t.n === state.selected; });
    var j = Math.min(Math.max(i + dir, 0), tr.length - 1);
    if (i >= 0 && tr[j]) focusTrade(tr[j], true);
  }
  function focusTrade(t, stay) {
    var r = state.result;
    if (!r.candles.length || t.entry_time < r.candles[0][0]) { toast("That trade is older than the bars on the chart. Pick a shorter date range to see it."); return; }
    clearSelection();
    state.selected = t.n;
    var bar = r.candles.length > 1 ? r.candles[1][0] - r.candles[0][0] : 3600;
    var pad = Math.max(20, Math.round((t.exit_time - t.entry_time) / bar * 0.6)) * bar;
    price.timeScale().setVisibleRange({ from: t.entry_time - pad, to: t.exit_time + pad });
    state.priceLines.push(candles.createPriceLine({ price: t.entry_price, color: tok("--gold"), lineWidth: 1, lineStyle: 2, title: "Entry #" + t.n }));
    state.priceLines.push(candles.createPriceLine({ price: t.exit_price, color: t.pnl >= 0 ? tok("--chart-up") : tok("--chart-down"), lineWidth: 1, lineStyle: 2, title: "Exit " + money(t.pnl, 0) }));
    document.querySelectorAll("#trades tbody tr").forEach(function (tr) { tr.classList.toggle("sel", Number(tr.dataset.n) === t.n); });
    $("trade-nav").hidden = false;
    $("trade-nav-label").textContent = "#" + t.n + " " + t.side + " " + money(t.pnl, 0) + (t.r !== null && t.r !== undefined ? " (" + num(t.r, 1) + "R)" : "");
    if (!stay) $("chart").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "center" });
  }

  // ---------------------------------------------------------------- results
  function kpi(label, value, sub, c) {
    return '<div class="kpi"><span class="l">' + label + '</span><span class="v ' + (c || "") + '">' + value + '</span><span class="s">' + (sub || "&nbsp;") + "</span></div>";
  }
  function renderOverview() {
    var m = state.result.metrics, s = state.result.settings;
    $("kpis").classList.remove("loading");
    $("kpis").innerHTML = [
      kpi("Net profit", money(m.net_profit, 0), pct(m.net_profit_pct, 1) + " of " + money(s.initial_capital, 0), cls(m.net_profit)),
      kpi("Max drawdown", money(m.max_drawdown, 0), pct(m.max_drawdown_pct, 1) + " of peak"),
      kpi("Profit factor", num(m.profit_factor, 2), "won ÷ lost"),
      kpi("Win rate", pct(m.percent_profitable, 1), num(m.total_trades, 0) + " trades"),
      kpi("Avg trade", money(m.avg_trade), (m.avg_r === null || m.avg_r === undefined ? "no stop, no R" : num(m.avg_r, 2) + "R per trade"), cls(m.avg_trade)),
      kpi("Sharpe", num(m.annual_sharpe, 2), "annualised"),
      kpi("Trades / month", num(m.trades_per_month, 1), pct(m.exposure_pct, 0) + " time in market"),
      kpi("Buy &amp; hold", pct(m.buy_hold_return_pct, 1), "gold, same period"),
    ].join("");
    $("summary").innerHTML = '<div><span class="l">Net</span><span class="v ' + cls(m.net_profit) + '">' + money(m.net_profit, 0) + "</span></div>" +
      '<div><span class="l">Win rate</span><span class="v">' + pct(m.percent_profitable, 0) + "</span></div>" +
      '<div><span class="l">Profit f.</span><span class="v">' + num(m.profit_factor, 2) + "</span></div>" +
      '<div><span class="l">Max DD</span><span class="v">' + pct(m.max_drawdown_pct, 1) + "</span></div>";
    var empty = $("empty"), skipped = m.rejected_orders || 0;
    if (!m.total_trades) {
      empty.hidden = false;
      empty.innerHTML = "<b>No closed trades in this range.</b>" + (skipped ?
        "Every signal was too small to trade at this account size (see below)."
        : "Try a longer date range, a different timeframe, or loosen the inputs in Settings.");
    } else { empty.hidden = true; }
    var byRisk = $("p-qtytype").value !== "lots";
    $("skip-note").hidden = !skipped;
    if (skipped) {
      var last = state.result.trades.length ? state.result.trades[state.result.trades.length - 1] : null;
      $("skip-text").innerHTML = "<b>" + num(skipped, 0) + (skipped === 1 ? " signal was" : " signals were") + " skipped.</b> " +
        (byRisk ? "With this stop distance, the position size works out below the broker minimum of 0.01 lot."
                : "The account didn't have enough margin for the position.") +
        (last ? " Last trade closed <span class=nowrap>" + new Date(last.exit_time * 1000).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }) + "</span>." : "") +
        (byRisk ? " Raise the account size or risk %, or trade the minimum size." : " Raise the account size or lower the lots.");
      $("use-min-lot").hidden = !byRisk;
    }
    var notes = [];
    if (state.result.trades_truncated) notes.push("Showing the latest " + state.result.trades.length.toLocaleString() + " of " + state.result.trades_total.toLocaleString() + " trades.");
    if (m.open_pnl) notes.push("Open trade at the end: " + money(m.open_pnl) + " unrealised (not in net profit).");
    notes.push("Max drawdown uses TradingView's method. Sharpe on monthly returns (TradingView style): " + num(m.sharpe, 3) + ".");
    notes.push("Computed in " + (state.result.elapsed_ms / 1000).toFixed(1) + " s.");
    $("run-note").textContent = notes.join(" ");
  }
  function renderPerformance() {
    var r = state.result, m = r.metrics, sd = r.sides;
    var rows = [["Net profit", "net_profit", money], ["Gross profit", "gross_profit", money], ["Gross loss", "gross_loss", money],
      ["Profit factor", "profit_factor", function (v) { return num(v, 2); }], ["Total closed trades", "trades", function (v) { return num(v, 0); }],
      ["Percent profitable", "win_rate", function (v) { return pct(v, 1); }], ["Avg trade", "avg_trade", money],
      ["Avg winning trade", "avg_win", money], ["Avg losing trade", "avg_loss", money], ["Largest winning trade", "largest_win", money],
      ["Largest losing trade", "largest_loss", money], ["Avg # bars in trades", "avg_bars", function (v) { return num(v, 1); }],
      ["Commission paid", "commission", money]];
    var t1 = "<caption class=sr>Performance by side</caption><thead><tr><th scope=col>Measure</th><th class=num scope=col>All</th><th class=num scope=col>Long</th><th class=num scope=col>Short</th></tr></thead><tbody>";
    rows.forEach(function (row) {
      t1 += "<tr><th scope=row>" + row[0] + "</th>" + ["all", "long", "short"].map(function (k) {
        var v = sd[k] ? sd[k][row[1]] : null; return '<td class="num">' + row[2](v) + "</td>";
      }).join("") + "</tr>";
    });
    t1 += "</tbody>";
    var risk = [["Max equity drawdown (TradingView)", money(m.max_drawdown) + " · " + pct(m.max_drawdown_pct)],
      ["Max drawdown incl. open profit given back", money(m.max_drawdown_mtm) + " · " + pct(m.max_drawdown_mtm_pct)],
      ["Max equity run-up", money(m.max_runup)], ["Sharpe ratio (monthly, TradingView)", num(m.sharpe, 3)],
      ["Sortino ratio (monthly)", num(m.sortino, 3)], ["Sharpe ratio (annualised, daily)", num(m.annual_sharpe, 2)],
      ["CAGR", pct(m.cagr_pct)], ["Calmar ratio", num(m.calmar, 2)], ["Net profit ÷ max drawdown", num(m.return_over_max_dd, 2)],
      ["Buy & hold return", money(m.buy_hold_return) + " · " + pct(m.buy_hold_return_pct)],
      ["Max consecutive wins / losses", num(m.max_consecutive_wins, 0) + " / " + num(m.max_consecutive_losses, 0)],
      ["Overnight swap paid", money(m.swap_paid)], ["Time in market", pct(m.exposure_pct, 1)],
      ["Trades per month", num(m.trades_per_month, 1)], ["Average R per trade", num(m.avg_r, 2)],
      ["Signals skipped (too small)", num(m.rejected_orders || 0, 0)]];
    var t2 = "<caption class=sr>Risk and return measures</caption><thead><tr><th scope=col>Measure</th><th class=num scope=col>Value</th></tr></thead><tbody>" + risk.map(function (x) {
      return "<tr><th scope=row style='white-space:normal'>" + esc(x[0]) + '</th><td class="num">' + x[1] + "</td></tr>";
    }).join("") + "</tbody>";
    $("tab-performance").innerHTML = '<div class="perf-grid"><div class="scroll" tabindex="0" aria-label="Performance by side"><table>' + t1 +
      '</table></div><div class="scroll" tabindex="0" aria-label="Risk and return"><table>' + t2 + "</table></div></div>";
  }
  var fmtCache = {};
  function localParts(ts, tz) {
    var f = fmtCache[tz] || (fmtCache[tz] = new Intl.DateTimeFormat("en-US", { timeZone: tz, hour: "numeric", hourCycle: "h23", weekday: "short" }));
    var o = {}; f.formatToParts(new Date(ts * 1000)).forEach(function (p) { o[p.type] = p.value; });
    return { hour: Number(o.hour) % 24, wd: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].indexOf(o.weekday) };
  }
  function filteredTrades() {
    var f = state.filter, x = state.extra;
    return state.result.trades.filter(function (t) {
      var ok = f === "all" || t.side === f || (f === "win" && t.pnl > 0) || (f === "loss" && t.pnl <= 0);
      if (ok && x && x.type === "month") ok = new Date(t.entry_time * 1000).toISOString().slice(0, 7) === x.value;
      if (ok && x && x.type === "heat") { var lp = localParts(t.entry_time, x.tz); ok = lp.hour === x.hour && lp.wd === x.wd; }
      return ok;
    });
  }
  function renderTrades() {
    var list = filteredTrades().slice().reverse();
    var chip = $("extra-filter");
    chip.hidden = !state.extra;
    if (state.extra) chip.querySelector("span").textContent = "Showing " + state.extra.label + " (" + list.length + " trades).";
    var head = "<caption class=sr>List of trades, newest first. Select a row to show the trade on the chart.</caption><thead><tr><th class=num scope=col>#</th><th scope=col>Side</th><th scope=col>Entry (UTC)</th><th class=num scope=col>Entry</th><th scope=col>Exit (UTC)</th><th class=num scope=col>Exit</th><th scope=col>Exit by</th><th class=num scope=col>Lots</th><th class=num scope=col>P&amp;L $</th><th class=num scope=col>R</th><th class=num scope=col>P&amp;L %</th><th class=num scope=col>Run-up</th><th class=num scope=col>Drawdown</th><th class=num scope=col>Bars</th><th class=num scope=col>Cum. P&amp;L</th></tr></thead>";
    var body = list.slice(0, 1500).map(function (t) {
      return '<tr tabindex="0" data-n="' + t.n + '"' + (state.selected === t.n ? ' class="sel"' : "") + '><td class="num" data-label="#">' + t.n +
        '</td><td data-label="Side"><span class="side ' + t.side + '">' + t.side + '</span></td><td data-label="Entry time">' + dt(t.entry_time) +
        '</td><td class="num" data-label="Entry">' + num(t.entry_price) + '</td><td data-label="Exit time">' + dt(t.exit_time) +
        '</td><td class="num" data-label="Exit">' + num(t.exit_price) + '</td><td class="opt" data-label="Exit by">' + esc(exitBy(t)) +
        '</td><td class="num" data-label="Lots">' + num(t.lots) + '</td><td class="num ' + cls(t.pnl) + '" data-label="P&L $">' + num(t.pnl) +
        '</td><td class="num ' + cls(t.r) + '" data-label="R">' + (t.r === null ? "–" : num(t.r, 2)) +
        '</td><td class="num opt ' + cls(t.pnl) + '" data-label="P&L %">' + num(t.pnl_pct) + '</td><td class="num opt" data-label="Run-up">' + num(t.runup) +
        '</td><td class="num opt" data-label="Drawdown">' + num(t.drawdown) + '</td><td class="num" data-label="Bars">' + t.bars +
        '</td><td class="num opt ' + cls(t.cum_pnl) + '" data-label="Cum. P&L">' + num(t.cum_pnl) + "</td></tr>";
    }).join("");
    $("trades").innerHTML = head + "<tbody>" + (body || '<tr><td colspan="15">No trades match this filter.</td></tr>') + "</tbody>";
  }
  function exitBy(t) {
    var k = { stop: "Stop loss", target: "Take profit", margin: "Margin call", reverse: "Reversed" }[t.exit_kind];
    if (k) return k;
    if (t.exit_kind === "close") return /exit rule|time stop|End of data/.test(t.comment || "") ? t.comment : "Closed";
    return t.exit_id;
  }
  function showTradesWith(extra) {
    state.extra = extra; state.filter = "all";
    document.querySelectorAll("#trade-filter button").forEach(function (x) { x.setAttribute("aria-pressed", x.dataset.f === "all" ? "true" : "false"); });
    selectTab("trades"); renderTrades();
  }
  function renderAnalysis() {
    var r = state.result, trades = r.trades, tz = $("tz").value;
    var withR = trades.filter(function (t) { return t.r !== null && t.r !== undefined; });
    var edges = [-Infinity, -1.5, -1, -0.5, 0, 0.5, 1, 1.5, 2, 3, Infinity];
    var labels = ["< −1.5R", "−1.5 to −1", "−1 to −0.5", "−0.5 to 0", "0 to 0.5", "0.5 to 1", "1 to 1.5", "1.5 to 2", "2 to 3", "> 3R"];
    var counts = labels.map(function () { return 0; });
    withR.forEach(function (t) { for (var k = 0; k < labels.length; k++) if (t.r >= edges[k] && t.r < edges[k + 1]) { counts[k]++; break; } });
    var maxC = Math.max.apply(null, counts.concat([1]));
    $("r-hist").innerHTML = withR.length ? '<div class="bars" role="list">' + labels.map(function (l, k) {
      return '<div class="bar-row" role="listitem" aria-label="' + l + ": " + counts[k] + ' trades"><span class="lbl" aria-hidden="true">' + l + '</span><span class="track" aria-hidden="true"><span class="fill ' + (k < 4 ? "neg" : "pos") + '" style="width:' + (counts[k] / maxC * 100).toFixed(1) + '%"></span></span><span class="cnt" aria-hidden="true">' + counts[k] + "</span></div>";
    }).join("") + '</div><p class="hint">Average ' + num(r.metrics.avg_r, 2) + "R over " + withR.length + " trades with a stop.</p>"
      : '<p class="hint">' + (trades.length ? "This strategy has no stop loss, so R can't be measured." : "No trades yet.") + "</p>";
    var sess = { "Asia": [], "London": [], "New York": [] };
    trades.forEach(function (t) {
      var h = localParts(t.entry_time, "America/New_York").hour;
      (h >= 18 || h < 3 ? sess.Asia : h < 8 ? sess.London : h < 17 ? sess["New York"] : sess.Asia).push(t);
    });
    $("sessions").innerHTML = '<div class="scroll"><table class="sess"><caption class=sr>Results by session</caption><thead><tr><th scope=col>Session</th><th class=num scope=col>Trades</th><th class=num scope=col>Win %</th><th class=num scope=col>Net $</th><th class=num scope=col>Avg R</th></tr></thead><tbody>' +
      Object.keys(sess).map(function (k) {
        var ts = sess[k], net = ts.reduce(function (a, t) { return a + t.pnl; }, 0), w = ts.filter(function (t) { return t.pnl > 0; }).length;
        var rs = ts.filter(function (t) { return t.r !== null; }), ar = rs.length ? rs.reduce(function (a, t) { return a + t.r; }, 0) / rs.length : null;
        return "<tr><th scope=row>" + k + '</th><td class="num">' + ts.length + '</td><td class="num">' + (ts.length ? pct(w / ts.length * 100, 0) : "–") + '</td><td class="num ' + cls(net) + '">' + money(net, 0) + '</td><td class="num">' + (ar === null ? "–" : num(ar, 2)) + "</td></tr>";
      }).join("") + "</tbody></table></div>";
    var grid = {}, maxAbs = 0;
    trades.forEach(function (t) {
      var lp = localParts(t.entry_time, tz), key = lp.wd + ":" + lp.hour;
      var c = grid[key] || (grid[key] = { pnl: 0, n: 0 }); c.pnl += t.pnl; c.n++;
    });
    Object.keys(grid).forEach(function (k) { maxAbs = Math.max(maxAbs, Math.abs(grid[k].pnl)); });
    var days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], h = "<caption class=sr>Profit by entry hour (columns) and weekday (rows)</caption><thead><tr><th scope=col>Day</th>";
    for (var hr = 0; hr < 24; hr++) h += "<th scope=col>" + hr + "</th>";
    h += "</tr></thead><tbody>";
    days.forEach(function (d, wd) {
      var row = "", any = false;
      for (var hr = 0; hr < 24; hr++) {
        var c = grid[wd + ":" + hr];
        if (!c) { row += '<td class="empty-cell"><span class="sr">no trades</span><span aria-hidden="true">·</span></td>'; continue; }
        any = true;
        var lbl = d + " " + hr + ":00, " + c.n + " trades, " + money(c.pnl, 0);
        row += '<td class="cell ' + cls(c.pnl) + '" tabindex="0" style="--a:' + (maxAbs ? Math.abs(c.pnl) / maxAbs : 0).toFixed(2) + '" data-wd="' + wd + '" data-hour="' + hr + '" title="' + lbl + '"><span class="sr">' + lbl + '. Show trades.</span><span aria-hidden="true">' + c.n + "</span></td>";
      }
      if (any || wd < 5) h += "<tr><th scope=row>" + d + "</th>" + row + "</tr>";
    });
    $("heat").innerHTML = h + "</tbody>";
  }
  function renderMonthly() {
    var rows = {}, years = [];
    state.result.monthly.forEach(function (m) {
      var y = m.month.slice(0, 4), k = Number(m.month.slice(5, 7));
      if (!rows[y]) { rows[y] = {}; years.push(y); }
      rows[y][k] = m.ret;
    });
    var names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    var h = "<caption class=sr>Monthly returns in percent. Select a month to list its trades.</caption><thead><tr><th scope=col>Year</th>" + names.map(function (n) { return "<th class=num scope=col>" + n + "</th>"; }).join("") + "<th class=num scope=col>Total</th></tr></thead><tbody>";
    years.forEach(function (y) {
      var comp = 1;
      h += "<tr><th scope=row>" + y + "</th>";
      for (var k = 1; k <= 12; k++) {
        var v = rows[y][k];
        if (v === undefined || v === null) { h += "<td></td>"; continue; }
        comp *= 1 + v / 100;
        var mm = y + "-" + (k < 10 ? "0" : "") + k;
        h += '<td class="' + cls(v) + '" style="--a:' + Math.min(Math.abs(v) / 8, 1).toFixed(2) + '" tabindex="0" data-month="' + mm + '" title="Show trades opened in ' + names[k - 1] + " " + y + '">' + (v > 0 ? "+" : "") + v.toFixed(1) + "</td>";
      }
      var yr = (comp - 1) * 100;
      h += '<td class="yr ' + cls(yr) + '">' + (yr > 0 ? "+" : "") + yr.toFixed(1) + "</td></tr>";
    });
    $("tab-monthly").innerHTML = '<div class="scroll" tabindex="0" aria-label="Monthly returns"><table class="months">' + h + "</tbody></table></div>";
  }
  function renderProperties() {
    var r = state.result, s = r.settings, rows = [];
    var label = { initial_capital: "Account size", qty_type: "Sizing", qty_value: "Size value", contract_size: "Ounces per lot",
      commission_type: "Commission type", commission_value: "Commission", slippage_ticks: "Slippage (ticks)", mintick: "Tick size",
      spread_mode: "Spread", spread_fixed: "Fixed spread", swap_long: "Swap long ($/lot/night)", swap_short: "Swap short ($/lot/night)",
      margin_percent: "Margin %", pyramiding: "Pyramiding", process_orders_on_close: "Fill on bar close", intrabar: "In-bar path",
      limit_fill_ticks: "Limit fill ticks", point_value: "Point value", min_qty: "Min size (oz)", qty_step: "Size step (oz)" };
    Object.keys(label).forEach(function (k) { if (k in s) rows.push([label[k], String(s[k])]); });
    var p = r.strategy.params, d = r.data;
    var labelsMap = r.strategy.labels || {};
    $("tab-properties").innerHTML = '<div class="props-grid"><div class="scroll"><table><caption class=sr>Run details</caption><thead><tr><th scope=col>Run</th><th scope=col>Value</th></tr></thead><tbody>' +
      [["Strategy", r.strategy.name], ["Rules version", r.strategy.fingerprint], ["Symbol", d.symbol], ["Timeframe", d.timeframe],
        ["From", d.start.slice(0, 16)], ["To", d.end.slice(0, 16)], ["Bars", d.bars.toLocaleString()], ["Data", d.source]]
        .concat(Object.keys(p).map(function (k) { return [(labelsMap[k] || humanize(k)), String(p[k])]; }))
        .map(function (x) { return "<tr><th scope=row>" + esc(x[0]) + "</th><td>" + esc(x[1]) + "</td></tr>"; }).join("") +
      '</tbody></table></div><div class="scroll"><table><caption class=sr>Broker emulator settings</caption><thead><tr><th scope=col>Broker emulator</th><th scope=col>Value</th></tr></thead><tbody>' +
      rows.map(function (x) { return "<tr><th scope=row>" + esc(x[0]) + "</th><td>" + esc(x[1]) + "</td></tr>"; }).join("") + "</tbody></table></div></div>" +
      '<p class="hint">Orders fill on the next bar; stops and targets follow TradingView\'s open → nearer extreme → other extreme → close path.</p>';
  }
  function renderCompare() {
    var hist = store.get("history", []);
    var h = "<caption class=sr>Your previous runs</caption><thead><tr><th scope=col>When</th><th scope=col>Strategy</th><th scope=col>TF</th><th scope=col>Range</th><th scope=col>Costs</th><th scope=col>Inputs</th><th class=num scope=col>Net</th><th class=num scope=col>PF</th><th class=num scope=col>Max DD</th><th class=num scope=col>Trades</th></tr></thead><tbody>";
    h += hist.slice().reverse().map(function (x) {
      return "<tr><td>" + esc(x.when) + '</td><td class="name">' + esc(x.name) + "</td><td>" + esc(x.tf) + "</td><td>" + esc(x.range) + "</td><td>" + esc(x.preset) + '</td><td class="name">' + esc(x.params) + '</td><td class="num ' + cls(x.net) + '">' + money(x.net, 0) + '</td><td class="num">' + num(x.pf, 2) + '</td><td class="num">' + pct(x.dd, 1) + '</td><td class="num">' + x.trades + "</td></tr>";
    }).join("") || '<tr><td colspan="10">No runs yet.</td></tr>';
    $("compare").innerHTML = h + "</tbody>";
  }
  function renderAll() {
    state.extra = null;
    renderOverview(); renderPerformance(); renderAnalysis(); renderTrades(); renderMonthly(); renderProperties(); renderCompare(); drawChart();
    $("checks").innerHTML = "";
  }

  // ---------------------------------------------------------------- controls
  function strategyDef() { return state.strategies[state.current]; }
  function fillStrategySelect() {
    var sel = $("strategy"), mine = [], ex = [];
    Object.keys(state.strategies).forEach(function (id) { if (id.indexOf("saved:") !== 0) (state.strategies[id].mine ? mine : ex).push(id); });
    var saved = store.get("saved", {});
    var group = function (label, ids) {
      if (!ids.length) return "";
      return '<optgroup label="' + label + '">' + ids.map(function (id) {
        var s = state.strategies[id]; return '<option value="' + esc(id) + '">' + esc(s.name) + " · " + esc(s.timeframe) + "</option>";
      }).join("") + "</optgroup>";
    };
    var savedIds = Object.keys(saved).map(function (k) { return "saved:" + k; });
    savedIds.forEach(function (id) { state.strategies[id] = saved[id.slice(6)]; });
    sel.innerHTML = group("Saved in this browser", savedIds) + group("My strategies", mine) + group("Examples", ex);
    if (state.current) sel.value = state.current;
  }
  function fillTimeframes() {
    $("tf").innerHTML = state.meta.timeframes.filter(function (tf) { return state.meta.data[tf]; }).map(function (tf) {
      return '<button type="button" aria-pressed="false" data-tf="' + tf + '">' + (tf === "1d" ? "1D" : tf) + "</button>";
    }).join("");
  }
  function markSeg(id, attr, value) {
    document.querySelectorAll("#" + id + " button").forEach(function (b) {
      b.setAttribute("aria-pressed", String(b.dataset[attr]) === String(value) ? "true" : "false");
    });
  }
  function defaultDays(tf) { var d = state.meta.data[tf]; return d && d.default_days ? d.default_days : 0; }
  function syncDates() {
    var d = state.meta.data[state.tf]; if (!d) return;
    $("start").min = $("end").min = d.start; $("start").max = $("end").max = d.end;
    if (state.days) {
      var end = new Date(d.end + "T00:00:00Z"); var start = new Date(end.getTime() - state.days * 864e5);
      $("start").value = start.toISOString().slice(0, 10) < d.start ? d.start : start.toISOString().slice(0, 10);
    } else { $("start").value = d.start; }
    $("end").value = d.end;
  }
  function setStrategy(id, keepTf) {
    if (!state.strategies[id]) return false;
    state.current = id;
    var s = strategyDef();
    state.custom = null;
    $("strategy").value = id;
    if (!keepTf) { state.tf = state.meta.data[s.timeframe] ? s.timeframe : "1h"; state.days = defaultDays(state.tf); }
    markSeg("tf", "tf", state.tf); markSeg("range", "days", state.days); syncDates();
    var ev = s.evidence_level || "Your idea";
    var evCls = ev === "Peer-reviewed" ? "ready" : (ev === "Folklore" ? "not-ready" : "caution");
    $("about").innerHTML = '<p><span class="chip ' + evCls + '">Evidence: ' + esc(ev) + "</span></p><p>" + esc(s.description || "No description.") + "</p>" +
      (s.evidence ? '<p class="hint">' + esc(s.evidence) + "</p>" : "") + (s.report ? '<p><a href="' + esc(s.report) + '">Full report with checklist →</a></p>' : "");
    renderInputs();
    applyCardSettings(s.settings || {});
    $("yaml").value = s.yaml || "";
    $("yaml").removeAttribute("aria-invalid");
    $("yaml-status").textContent = "";
    if (decodeURIComponent(location.hash.slice(1)) !== id) {
      try { history.replaceState(null, "", "#" + encodeURIComponent(id)); } catch (e) { /* ignore */ }
    }
    return true;
  }
  function renderInputs() {
    var s = strategyDef(), keys = Object.keys(s.params || {}), labels = s.labels || {};
    $("inputs").innerHTML = keys.length ? keys.map(function (k) {
      var v = s.params[k], isInt = Number.isInteger(v);
      return '<label>' + esc(labels[k] || humanize(k)) + '<input type="number" data-param="' + esc(k) + '" value="' + v + '" step="' + (isInt ? 1 : 0.1) + '" inputmode="decimal"></label>';
    }).join("") : '<p class="hint">This strategy has no inputs.</p>';
  }
  function applyCardSettings(cs) {
    var d = state.meta.defaults.realistic;
    $("p-capital").value = cs.initial_capital || d.initial_capital;
    var qt = cs.qty_type || "risk_percent";
    $("p-qtytype").value = ["risk_percent", "lots", "percent_of_equity"].indexOf(qt) >= 0 ? qt : "lots";
    $("p-qtyvalue").value = cs.qty_value || (qt === "lots" ? 0.1 : 0.5);
    $("p-comm").value = d.commission_value; $("p-slip").value = d.slippage_ticks; $("p-spread").value = d.spread_mode;
    $("p-spreadfixed").value = 0.35; $("p-swapl").value = d.swap_long; $("p-swaps").value = d.swap_short; $("p-intrabar").value = "tv";
    syncPropsUI();
  }
  function syncPropsUI() {
    var qt = $("p-qtytype").value;
    $("p-qtyvalue-label").textContent = qt === "risk_percent" ? "Risk % per trade" : qt === "lots" ? "Lots (1 lot = 100 oz)" : "% of equity";
    $("p-spreadfixed-wrap").hidden = $("p-spread").value !== "fixed";
    var tv = state.preset === "tradingview";
    ["p-comm", "p-slip", "p-spread", "p-spreadfixed", "p-swapl", "p-swaps"].forEach(function (id) { $(id).disabled = tv; });
    $("tv-note").hidden = !tv;
  }
  function readNum(id) { var v = parseFloat($(id).value); return isNaN(v) ? null : v; }
  function buildRequest() {
    var req = { timeframe: state.tf, preset: state.preset, start: $("start").value || null, end: $("end").value || null };
    if (state.custom) req.card = state.custom; else if (state.current.indexOf("saved:") === 0) req.card = strategyDef().yaml; else req.strategy = state.current;
    var params = {};
    document.querySelectorAll("#inputs input[data-param]").forEach(function (i) {
      var v = parseFloat(i.value); if (!isNaN(v)) params[i.dataset.param] = v;
    });
    if (!state.custom) req.params = params;
    var st = { initial_capital: readNum("p-capital"), qty_type: $("p-qtytype").value, qty_value: readNum("p-qtyvalue"), intrabar: $("p-intrabar").value };
    if (state.preset === "realistic") {
      st.commission_value = readNum("p-comm"); st.slippage_ticks = Math.round(readNum("p-slip") || 0); st.spread_mode = $("p-spread").value;
      st.spread_fixed = readNum("p-spreadfixed"); st.swap_long = readNum("p-swapl"); st.swap_short = readNum("p-swaps");
    }
    Object.keys(st).forEach(function (k) { if (st[k] === null) delete st[k]; });
    req.settings = st;
    return req;
  }
  function setBusy(on) {
    $("busy").hidden = !on; $("run").disabled = on;
    $("run").querySelector(".run-label").textContent = on ? "Running…" : "Run backtest";
    $("results").setAttribute("aria-busy", on ? "true" : "false");
    $("results").classList.toggle("busy-state", on && !!state.result);
    var ov = $("overlay");
    if (on) { ov.className = "overlay"; $("overlay-text").textContent = "Running backtest…"; ov.hidden = false; }
    else if (!ov.classList.contains("error")) ov.hidden = true;
  }
  function placeholderKpis() {
    $("kpis").innerHTML = ["Net profit", "Max drawdown", "Profit factor", "Win rate", "Avg trade", "Sharpe", "Trades / month", "Buy &amp; hold"]
      .map(function (l) { return kpi(l, "0000", "&nbsp;"); }).join("");
    $("kpis").classList.add("loading");
  }
  function showError(msg) {
    $("banner").hidden = false;
    $("banner").textContent = (state.result ? "This run failed, so the results below are from your previous run. " : "") + msg;
    $("results").classList.toggle("stale", !!state.result);
    if (!state.result) {
      var ov = $("overlay"); ov.className = "overlay error"; $("overlay-text").textContent = "Couldn't run the backtest"; ov.hidden = false;
      $("kpis").classList.remove("loading");
    }
    announce("Backtest failed: " + msg);
  }
  function clearError() { $("banner").hidden = true; $("results").classList.remove("stale"); $("overlay").className = "overlay"; }
  function validDates() {
    var s = $("start").value, e = $("end").value;
    if (s && e && s > e) { showError("The start date is after the end date. Pick a start date before " + e + "."); return false; }
    return true;
  }
  function runBacktest() {
    if (!state.current) return Promise.resolve();
    if (state.locked) { toast("Finish or exit bar replay first."); return Promise.resolve(); }
    if (!validDates()) return Promise.resolve();
    var req = buildRequest(), my = ++state.seq;
    setBusy(true);
    return api("backtest", req).then(function (r) {
      if (my !== state.seq) return;
      clearError();
      state.result = r; renderAll(); remember(r, req); GSL.emit("result", r);
      var m = r.metrics;
      announce("Backtest finished: " + r.strategy.name + ", net profit " + money(m.net_profit, 0) + " on " + m.total_trades + " trades, max drawdown " + pct(m.max_drawdown_pct, 1) + ".");
    }).catch(function (e) { if (my === state.seq) showError(e.message); })
      .then(function () { if (my === state.seq) setBusy(false); });
  }
  function remember(r, req) {
    var hist = store.get("history", []);
    hist.push({ when: new Date().toLocaleString(), name: r.strategy.name + (state.custom ? " (edited)" : ""), tf: r.data.timeframe,
      range: r.data.start.slice(0, 10) + " → " + r.data.end.slice(0, 10), preset: req.preset,
      params: Object.keys(r.strategy.params).map(function (k) { return k + "=" + r.strategy.params[k]; }).join(", "),
      net: r.metrics.net_profit, pf: r.metrics.profit_factor, dd: r.metrics.max_drawdown_pct, trades: r.metrics.total_trades });
    store.set("history", hist.slice(-200));
  }
  var debounce = function (fn, ms) { var t; return function () { clearTimeout(t); t = setTimeout(fn, ms); }; };
  var autoRun = debounce(runBacktest, 600);

  function runChecks() {
    var btn = $("run-checks"); btn.disabled = true; btn.textContent = "Running checklist…";
    $("checks").innerHTML = '<p class="hint">Running about 15 backtests. This can take up to a minute on long ranges.</p>';
    api("validate", buildRequest()).then(function (v) {
      var rows = v.checks.map(function (c) {
        return '<tr><td><span class="chip ' + c.status + '">' + c.status.toUpperCase() + "</span></td><td>" + esc(c.name) + "</td><td>" + esc(c.value) + '</td><td class="rule">' + esc(c.rule) + "</td></tr>";
      }).join("");
      $("checks").innerHTML = '<p class="verdict ' + v.verdict + '">' + esc(v.headline) + "</p>" +
        (v.quick ? '<p class="hint">Long range: parameter-stability and look-ahead checks were skipped to stay within the time limit.</p>' : "") +
        '<div class="scroll" tabindex="0" aria-label="Checklist results"><table class="checks"><caption class=sr>Readiness checks</caption><thead><tr><th scope=col>Result</th><th scope=col>Check</th><th scope=col>Value</th><th scope=col>Rule</th></tr></thead><tbody>' + rows + "</tbody></table></div>";
      announce("Checklist finished. " + v.headline);
    }).catch(function (e) { $("checks").innerHTML = '<div class="error-box">' + esc(e.message) + "</div>"; })
      .then(function () { btn.disabled = false; btn.textContent = "Run checklist"; });
  }
  function downloadCSV() {
    var r = state.result; if (!r) return;
    var cols = ["n", "side", "entry_time", "entry_price", "exit_time", "exit_price", "exit_id", "exit_kind", "lots", "pnl", "r", "pnl_pct", "runup", "drawdown", "bars", "cum_pnl", "commission"];
    var lines = [cols.join(",")].concat(r.trades.map(function (t) {
      return cols.map(function (c) { return /time/.test(c) ? new Date(t[c] * 1000).toISOString() : (t[c] === null ? "" : t[c]); }).join(",");
    }));
    var blob = new Blob([lines.join("\n")], { type: "text/csv" });
    var a = document.createElement("a"); a.href = URL.createObjectURL(blob);
    a.download = (r.strategy.name || "trades").replace(/[^a-z0-9]+/gi, "_") + "_" + r.data.timeframe + ".csv";
    document.body.appendChild(a); a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 500);
  }
  function showPine() {
    var req = state.custom ? { card: state.custom } : (state.current.indexOf("saved:") === 0 ? { card: strategyDef().yaml } : { strategy: state.current });
    api("pine", req).then(function (r) {
      $("pine-code").textContent = r.pine;
      var d = $("pine-dialog"); if (d.showModal) d.showModal(); else d.setAttribute("open", "");
      $("pine-copy").focus();
    }).catch(function (e) { toast(e.message); });
  }
  function saveYaml() {
    var text = $("yaml").value, m = /^name:\s*(.+)$/m.exec(text);
    if (!m) { $("yaml-status").textContent = "Add a name: line first, for example name: My idea"; $("yaml").setAttribute("aria-invalid", "true"); return; }
    var name = m[1].trim().replace(/^["']|["']$/g, ""), key = name.toLowerCase().replace(/[^a-z0-9]+/g, "-");
    state.custom = text;
    $("yaml-status").textContent = "Checking the rules…";
    return runBacktest().then(function () {
      var r = state.result;
      if (!r || r.strategy.name !== name || !$("banner").hidden) { $("yaml-status").textContent = "Fix the error shown above the results, then save again."; $("yaml").setAttribute("aria-invalid", "true"); return; }
      $("yaml").removeAttribute("aria-invalid");
      var saved = store.get("saved", {});
      saved[key] = { name: name, timeframe: r.data.timeframe, yaml: text, params: r.strategy.params, labels: r.strategy.labels || {}, settings: {}, mine: true,
        description: "Saved in this browser on " + new Date().toLocaleDateString() + ".", evidence_level: "Your idea" };
      store.set("saved", saved);
      fillStrategySelect();
      setStrategy("saved:" + key, true);
      $("yaml-status").textContent = "Saved as “" + name + "” in this browser. To keep it for good, add the card to strategies/ in the repo.";
    });
  }

  // ---------------------------------------------------------------- settings sheet (phones)
  var BG_PARTS = [".top", ".toolbar", "#summary", ".chart-area", "#results", ".foot"];
  function isSheet() { return matchMedia("(max-width: 900px)").matches; }
  function openSheet() {
    $("panel").classList.add("open"); $("backdrop").hidden = false; $("open-settings").setAttribute("aria-expanded", "true");
    BG_PARTS.forEach(function (s) { var el = document.querySelector(s); if (el) el.inert = true; });
    setTimeout(function () { $("close-settings").focus(); }, 50);
  }
  function closeSheet() {
    if (!$("panel").classList.contains("open")) return;
    $("panel").classList.remove("open"); $("backdrop").hidden = true; $("open-settings").setAttribute("aria-expanded", "false");
    BG_PARTS.forEach(function (s) { var el = document.querySelector(s); if (el) el.inert = false; });
    $("open-settings").focus();
  }

  // ---------------------------------------------------------------- tabs
  var TABS = ["overview", "performance", "analysis", "trades", "monthly", "checks", "properties", "compare"];
  function selectTab(name, focus) {
    document.querySelectorAll(".tabs button").forEach(function (x) {
      var on = x.dataset.tab === name;
      x.setAttribute("aria-selected", on ? "true" : "false"); x.tabIndex = on ? 0 : -1;
      if (on && focus) x.focus();
    });
    document.querySelectorAll(".tab-body").forEach(function (x) { x.hidden = x.id !== "tab-" + name; });
    if (name === "compare") renderCompare();
    if (name === "overview" && eqChart) eqChart.timeScale().fitContent();
  }

  // ---------------------------------------------------------------- wiring
  function wire() {
    var savedTz = store.get("tz", null); if (savedTz) $("tz").value = savedTz;
    state.showBH = !!store.get("bh", false); $("bh-toggle").checked = state.showBH;
    $("strategy").addEventListener("change", function () { setStrategy(this.value); runBacktest(); });
    $("tf").addEventListener("click", function (e) {
      var b = e.target.closest("button"); if (!b) return;
      state.tf = b.dataset.tf; state.days = defaultDays(state.tf); markSeg("tf", "tf", state.tf); markSeg("range", "days", state.days); syncDates(); runBacktest();
    });
    $("range").addEventListener("click", function (e) {
      var b = e.target.closest("button"); if (!b) return;
      state.days = Number(b.dataset.days); markSeg("range", "days", state.days); syncDates(); runBacktest();
    });
    ["start", "end"].forEach(function (id) { $(id).addEventListener("change", function () { state.days = null; markSeg("range", "days", -1); autoRun(); }); });
    $("preset").addEventListener("click", function (e) {
      var b = e.target.closest("button"); if (!b) return;
      state.preset = b.dataset.preset; markSeg("preset", "preset", state.preset); syncPropsUI(); runBacktest();
    });
    $("run").addEventListener("click", runBacktest);
    $("inputs").addEventListener("input", autoRun);
    $("props").addEventListener("change", function () { syncPropsUI(); autoRun(); });
    $("reset-inputs").addEventListener("click", function () { renderInputs(); runBacktest(); });
    $("use-min-lot").addEventListener("click", function () {
      $("p-qtytype").value = "lots"; $("p-qtyvalue").value = 0.01; syncPropsUI();
      runBacktest().then(function () { toast("Now trading a fixed 0.01 lot. Change it in Settings → Account."); });
    });
    $("apply-yaml").addEventListener("click", function () {
      state.custom = $("yaml").value; $("yaml-status").textContent = "Running your edited rules…";
      runBacktest().then(function () {
        var failed = !$("banner").hidden;
        $("yaml").setAttribute("aria-invalid", failed ? "true" : "false");
        $("yaml-status").textContent = failed ? "These rules have an error (shown above the results)." : "Showing results for your edited rules (not saved yet).";
      });
    });
    $("save-yaml").addEventListener("click", saveYaml);
    $("pine-btn").addEventListener("click", showPine);
    $("pine-close").addEventListener("click", function () { $("pine-dialog").close(); });
    $("pine-copy").addEventListener("click", function () {
      var text = $("pine-code").textContent;
      (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject()).then(function () { toast("Pine Script copied"); })
        .catch(function () { var r = document.createRange(); r.selectNodeContents($("pine-code")); var s = getSelection(); s.removeAllRanges(); s.addRange(r); toast("Code selected: press copy"); });
    });
    var tabs = document.querySelector(".tabs");
    tabs.addEventListener("click", function (e) { var b = e.target.closest("button[data-tab]"); if (b) selectTab(b.dataset.tab); });
    tabs.addEventListener("keydown", function (e) {
      var cur = TABS.indexOf(document.activeElement.dataset.tab); if (cur < 0) return;
      var next = { ArrowRight: cur + 1, ArrowLeft: cur - 1, Home: 0, End: TABS.length - 1 }[e.key];
      if (next === undefined) return;
      e.preventDefault(); selectTab(TABS[(next + TABS.length) % TABS.length], true);
    });
    $("trade-filter").addEventListener("click", function (e) {
      var b = e.target.closest("button"); if (!b) return;
      state.filter = b.dataset.f; document.querySelectorAll("#trade-filter button").forEach(function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
      renderTrades();
    });
    var pickTrade = function (tr) { var n = Number(tr.dataset.n); var t = state.result.trades.find(function (x) { return x.n === n; }); if (t) focusTrade(t); };
    $("trades").addEventListener("click", function (e) { var tr = e.target.closest("tr[data-n]"); if (tr) pickTrade(tr); });
    $("trades").addEventListener("keydown", function (e) { var tr = e.target.closest("tr[data-n]"); if (tr && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); pickTrade(tr); } });
    $("csv").addEventListener("click", downloadCSV);
    $("run-checks").addEventListener("click", runChecks);
    $("clear-history").addEventListener("click", function () { store.set("history", []); renderCompare(); toast("History cleared"); });
    $("open-settings").addEventListener("click", openSheet);
    $("close-settings").addEventListener("click", closeSheet);
    $("backdrop").addEventListener("click", closeSheet);
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && $("panel").classList.contains("open")) closeSheet(); });
    matchMedia("(max-width: 900px)").addEventListener("change", function () { if (!isSheet()) closeSheet(); });
    $("prev-trade").addEventListener("click", function () { stepTrade(-1); });
    $("next-trade").addEventListener("click", function () { stepTrade(1); });
    $("close-trade").addEventListener("click", clearSelection);
    $("bh-toggle").addEventListener("change", function () { state.showBH = this.checked; store.set("bh", state.showBH); drawEquity(); });
    $("tz").addEventListener("change", function () { store.set("tz", this.value); if (state.result) renderAnalysis(); });
    var monthPick = function (td) { showTradesWith({ type: "month", value: td.dataset.month, label: "trades opened in " + td.dataset.month }); };
    $("tab-monthly").addEventListener("click", function (e) { var td = e.target.closest("td[data-month]"); if (td) monthPick(td); });
    $("tab-monthly").addEventListener("keydown", function (e) { var td = e.target.closest("td[data-month]"); if (td && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); monthPick(td); } });
    var heatPick = function (td) {
      var tz = $("tz").value, d = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][Number(td.dataset.wd)];
      showTradesWith({ type: "heat", wd: Number(td.dataset.wd), hour: Number(td.dataset.hour), tz: tz,
        label: "trades opened " + d + " " + td.dataset.hour + ":00–" + td.dataset.hour + ":59 (" + $("tz").selectedOptions[0].textContent + ")" });
    };
    $("heat").addEventListener("click", function (e) { var td = e.target.closest("td[data-wd]"); if (td) heatPick(td); });
    $("heat").addEventListener("keydown", function (e) { var td = e.target.closest("td[data-wd]"); if (td && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); heatPick(td); } });
    $("clear-extra").addEventListener("click", function () { state.extra = null; renderTrades(); });
    window.addEventListener("hashchange", function () {
      var id = decodeURIComponent(location.hash.slice(1));
      if (id && id !== state.current && state.strategies[id]) { setStrategy(id); runBacktest(); }
    });
  }

  // ---------------------------------------------------------------- boot
  initCharts();
  Object.assign(GSL, {
    price: price, candles: candles, markers: markers, eqChart: eqChart,
    api: api, toast: toast, announce: announce, tok: tok, esc: esc, num: num, money: money, pct: pct, dt: dt, cls: cls,
    drawChart: function () { drawChart(); }, drawMarkers: function () { drawMarkers(); }, runBacktest: runBacktest,
    buildRequest: buildRequest, selectTab: selectTab, readNum: readNum, clearSelection: clearSelection,
    setStrategy: setStrategy, fillStrategySelect: fillStrategySelect, saveYaml: function () { return saveYaml(); },
    setTimeframe: function (tf) {
      if (!state.meta.data[tf]) return;
      state.tf = tf; state.days = defaultDays(tf); markSeg("tf", "tf", tf); markSeg("range", "days", state.days); syncDates();
    },
    // show a result that didn't come from a strategy backtest (e.g. trades placed in bar replay)
    showResult: function (r) { state.result = r; clearError(); renderAll(); GSL.emit("result", r); },
    setLocked: function (on) {
      state.locked = on;
      document.querySelectorAll("#strategy, #tf button, #range button, #start, #end, #preset button, #run, #apply-yaml, #run-checks, #use-min-lot")
        .forEach(function (el) { el.disabled = on; });
      // with every control disabled, the phone toolbar is still a scroll area: keep it reachable by keyboard
      var tc = document.querySelector(".toolbar-controls");
      if (on) { tc.tabIndex = 0; tc.setAttribute("aria-label", "Chart options (locked during replay)"); } else { tc.removeAttribute("tabindex"); tc.removeAttribute("aria-label"); }
    },
  });
  wire();
  GSL.on("bars", function () { legendUpdate(null); });
  GSL.on("step", function () { legendUpdate(null); });
  markSeg("preset", "preset", state.preset);
  placeholderKpis();
  setBusy(true);
  api("strategies").then(function (meta) {
    state.meta = meta;
    meta.strategies.forEach(function (s) { state.strategies[s.id] = s; });
    fillTimeframes(); fillStrategySelect();
    var want = decodeURIComponent((location.hash || "").slice(1));
    var first = state.strategies[want] ? want : (meta.strategies.filter(function (s) { return s.mine; })[0] || {}).id || "tsmom_daily";
    if (!state.strategies[first]) first = meta.strategies[0].id;
    setStrategy(first);
    return runBacktest();
  }).catch(function (e) { setBusy(false); showError(e.message); });
})();
