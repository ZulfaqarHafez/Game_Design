/* Gold Strategy Lab: browser side of the backtester.
   All calculations happen in the Python API (/api/lab); this file draws the results. */
(function () {
  "use strict";
  var API = "/api/lab";
  var L = window.LightweightCharts;
  var $ = function (id) { return document.getElementById(id); };
  var state = {
    meta: null, strategies: {}, current: null, tf: null, days: null, preset: "realistic",
    params: {}, custom: null, result: null, filter: "all", selected: null, priceLines: [], plotSeries: [],
    running: false, seq: 0,
  };
  var store = {
    get: function (k, d) { try { var v = localStorage.getItem("gsl:" + k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
    set: function (k, v) { try { localStorage.setItem("gsl:" + k, JSON.stringify(v)); } catch (e) { /* storage off */ } },
  };

  // ---------------------------------------------------------------- formatting
  function money(v, dp) {
    if (v === null || v === undefined || isNaN(v)) return "n/a";
    var s = Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: dp === undefined ? 2 : dp, maximumFractionDigits: dp === undefined ? 2 : dp });
    return (v < 0 ? "-$" : "$") + s;
  }
  function num(v, dp) {
    if (v === null || v === undefined || isNaN(v)) return "n/a";
    if (!isFinite(v)) return "∞";
    if (Math.abs(v) < Math.pow(10, -(dp || 2)) / 2) v = 0;
    return v.toLocaleString("en-US", { minimumFractionDigits: dp === undefined ? 2 : dp, maximumFractionDigits: dp === undefined ? 2 : dp });
  }
  function pct(v, dp) { return v === null || v === undefined ? "n/a" : num(v, dp === undefined ? 2 : dp) + "%"; }
  function cls(v) { return v > 0 ? "pos" : v < 0 ? "neg" : ""; }
  function esc(s) { return String(s === undefined || s === null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function dt(ts) { var d = new Date(ts * 1000); return d.toISOString().slice(0, 16).replace("T", " "); }
  function tok(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }
  function toast(msg) { var t = $("toast"); t.textContent = msg; t.hidden = false; clearTimeout(toast.t); toast.t = setTimeout(function () { t.hidden = true; }, 2600); }

  // ---------------------------------------------------------------- api
  function api(op, body) {
    var opts = body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {};
    return fetch(API + "?op=" + op, opts).then(function (r) {
      return r.json().catch(function () { return { error: "The server returned an unexpected response (" + r.status + ")." }; })
        .then(function (j) { if (!r.ok || j.error) throw new Error(j.error || ("Request failed (" + r.status + ")")); return j; });
    });
  }

  // ---------------------------------------------------------------- charts
  var chartOpts = function () {
    return {
      autoSize: true,
      layout: { background: { color: tok("--panel") }, textColor: tok("--muted"), fontFamily: "JetBrains Mono, monospace", fontSize: 11 },
      grid: { vertLines: { color: tok("--line") }, horzLines: { color: tok("--line") } },
      rightPriceScale: { borderColor: tok("--line") },
      timeScale: { borderColor: tok("--line"), timeVisible: true, secondsVisible: false },
      crosshair: { mode: 0 },
    };
  };
  var price, candles, markers, eqChart, eqSeries, bhSeries, ddSeries;
  function initCharts() {
    if (!L) { $("chart").textContent = "The chart library could not load. Check your connection and reload."; return; }
    price = L.createChart($("chart"), chartOpts());
    candles = price.addSeries(L.CandlestickSeries, { upColor: tok("--up"), downColor: tok("--down"), borderVisible: false,
      wickUpColor: tok("--up"), wickDownColor: tok("--down") });
    markers = L.createSeriesMarkers(candles, []);
    price.subscribeCrosshairMove(legendUpdate);
    eqChart = L.createChart($("equity"), chartOpts());
    eqChart.applyOptions({ timeScale: { minBarSpacing: 0.001 } });
    eqSeries = eqChart.addSeries(L.AreaSeries, { lineColor: tok("--gold"), topColor: tok("--gold-soft"), bottomColor: "rgba(0,0,0,0)", lineWidth: 2, priceLineVisible: false });
    bhSeries = eqChart.addSeries(L.LineSeries, { color: tok("--muted"), lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false });
    ddSeries = eqChart.addSeries(L.HistogramSeries, { color: tok("--down-soft"), priceScaleId: "dd", priceLineVisible: false, lastValueVisible: false });
    eqChart.priceScale("dd").applyOptions({ scaleMargins: { top: 0.78, bottom: 0 } });
    var rethemer = function () {
      [price, eqChart].forEach(function (c) { c.applyOptions(chartOpts()); });
      candles.applyOptions({ upColor: tok("--up"), downColor: tok("--down"), wickUpColor: tok("--up"), wickDownColor: tok("--down") });
      eqSeries.applyOptions({ lineColor: tok("--gold"), topColor: tok("--gold-soft") });
      bhSeries.applyOptions({ color: tok("--muted") });
      if (state.result) drawMarkers();
    };
    try { window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", rethemer); } catch (e) { /* old browser */ }
    new MutationObserver(rethemer).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  }
  var plotColors = ["#3d7bd9", "#b56bd1", "#d98c3d", "#3fa7a7", "#8a8f3d"];
  function legendUpdate(p) {
    var r = state.result; if (!r) return;
    var c = null;
    if (p && p.time && p.seriesData) c = p.seriesData.get(candles);
    if (!c) { var last = r.candles[r.candles.length - 1]; c = last ? { open: last[1], high: last[2], low: last[3], close: last[4] } : null; }
    var head = "<span><b>XAUUSD</b> " + esc(r.data.timeframe) + "</span>";
    if (c) head += "<span>O <b>" + num(c.open) + "</b> H <b>" + num(c.high) + "</b> L <b>" + num(c.low) + "</b> C <b>" + num(c.close) + "</b></span>";
    Object.keys(r.plots).forEach(function (name, k) {
      head += '<span><i class="sw" style="background:' + plotColors[k % plotColors.length] + '"></i>' + esc(name) + "</span>";
    });
    $("legend").innerHTML = head;
  }
  function drawMarkers() {
    var r = state.result; if (!r || !markers) return;
    var first = r.candles.length ? r.candles[0][0] : 0;
    var up = tok("--up"), down = tok("--down"), mk = [];
    r.trades.forEach(function (t) {
      var long = t.side === "long";
      if (t.entry_time >= first) mk.push({ time: t.entry_time, position: long ? "belowBar" : "aboveBar", shape: long ? "arrowUp" : "arrowDown", color: long ? up : down, text: long ? "Long" : "Short" });
      if (t.exit_time >= first) mk.push({ time: t.exit_time, position: long ? "aboveBar" : "belowBar", shape: "circle", color: t.pnl >= 0 ? up : down, size: 0.6, text: (t.pnl >= 0 ? "+" : "") + Math.round(t.pnl) });
    });
    (r.open_trades || []).forEach(function (t) {
      if (t.entry_time >= first) mk.push({ time: t.entry_time, position: t.side === "long" ? "belowBar" : "aboveBar", shape: t.side === "long" ? "arrowUp" : "arrowDown", color: tok("--gold"), text: "Open" });
    });
    mk.sort(function (a, b) { return a.time - b.time; });
    markers.setMarkers(mk);
  }
  function drawChart() {
    var r = state.result;
    candles.setData(r.candles.map(function (c) { return { time: c[0], open: c[1], high: c[2], low: c[3], close: c[4] }; }));
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
    var note = r.data.bars.toLocaleString() + " bars, " + r.data.start.slice(0, 10) + " → " + r.data.end.slice(0, 10) + " · source: " + r.data.source;
    if (r.data.candles_shown < r.data.bars) note += " · chart shows the last " + r.data.candles_shown.toLocaleString() + " bars";
    $("chart-note").textContent = note;
    eqSeries.setData(r.equity.map(function (p) { return { time: p[0], value: p[1] }; }));
    bhSeries.setData((r.buyhold || []).map(function (p) { return { time: p[0], value: p[1] }; }));
    ddSeries.setData(r.drawdown.map(function (p) { return { time: p[0], value: p[1], color: tok("--down-soft") }; }));
    eqChart.timeScale().fitContent();
  }
  function clearSelection() {
    state.priceLines.forEach(function (l) { candles.removePriceLine(l); });
    state.priceLines = [];
    state.selected = null;
  }
  function focusTrade(t) {
    var r = state.result;
    if (!r.candles.length || t.entry_time < r.candles[0][0]) { toast("That trade is older than the bars on the chart. Narrow the date range to see it."); return; }
    clearSelection();
    state.selected = t.n;
    var bar = r.candles.length > 1 ? r.candles[1][0] - r.candles[0][0] : 3600;
    var pad = Math.max(20, Math.round((t.exit_time - t.entry_time) / bar * 0.6)) * bar;
    price.timeScale().setVisibleRange({ from: t.entry_time - pad, to: t.exit_time + pad });
    state.priceLines.push(candles.createPriceLine({ price: t.entry_price, color: tok("--gold"), lineWidth: 1, lineStyle: 2, title: "Entry #" + t.n }));
    state.priceLines.push(candles.createPriceLine({ price: t.exit_price, color: t.pnl >= 0 ? tok("--up") : tok("--down"), lineWidth: 1, lineStyle: 2, title: "Exit " + money(t.pnl, 0) }));
    document.querySelectorAll("#trades tbody tr").forEach(function (tr) { tr.classList.toggle("sel", Number(tr.dataset.n) === t.n); });
    $("chart").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "center" });
  }

  // ---------------------------------------------------------------- results
  function kpi(label, value, sub, c) {
    return '<div class="kpi"><span class="l">' + label + '</span><span class="v ' + (c || "") + '">' + value + '</span><span class="s">' + (sub || "&nbsp;") + "</span></div>";
  }
  function renderOverview() {
    var m = state.result.metrics, s = state.result.settings;
    $("kpis").innerHTML = [
      kpi("Net profit", money(m.net_profit, 0), pct(m.net_profit_pct) + " of " + money(s.initial_capital, 0), cls(m.net_profit)),
      kpi("Max drawdown", money(m.max_drawdown, 0), pct(m.max_drawdown_pct) + " (TradingView method)"),
      kpi("Profit factor", num(m.profit_factor, 2), "gross profit ÷ gross loss"),
      kpi("Win rate", pct(m.percent_profitable, 1), num(m.total_trades, 0) + " closed trades"),
      kpi("Avg trade", money(m.avg_trade), "win/loss ratio " + num(m.win_loss_ratio, 2), cls(m.avg_trade)),
      kpi("Sharpe (annual)", num(m.annual_sharpe, 2), "monthly TradingView: " + num(m.sharpe, 3)),
      kpi("Buy &amp; hold", pct(m.buy_hold_return_pct, 1), "holding gold over the same period"),
    ].join("");
    var notes = [];
    if (m.rejected_orders) notes.push(m.rejected_orders + " signals were skipped because the position would be under 0.01 lot. Raise the account size or risk %, or use fixed lots.");
    if (state.result.trades_truncated) notes.push("Showing the latest " + state.result.trades.length.toLocaleString() + " of " + state.result.trades_total.toLocaleString() + " trades.");
    if (m.open_pnl) notes.push("Open trade at the end: " + money(m.open_pnl) + " unrealised (not in net profit).");
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
    var t1 = "<thead><tr><th></th><th class=num>All</th><th class=num>Long</th><th class=num>Short</th></tr></thead><tbody>";
    rows.forEach(function (row) {
      t1 += "<tr><th>" + row[0] + "</th>" + ["all", "long", "short"].map(function (k) {
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
      ["Trades per month", num(m.trades_per_month, 1)], ["Signals skipped (too small)", num(m.rejected_orders || 0, 0)]];
    var t2 = "<thead><tr><th>Measure</th><th class=num>Value</th></tr></thead><tbody>" + risk.map(function (x) {
      return "<tr><th style='white-space:normal'>" + esc(x[0]) + '</th><td class="num">' + x[1] + "</td></tr>";
    }).join("") + "</tbody>";
    $("tab-performance").innerHTML = '<div class="perf-grid"><div class="scroll"><table>' + t1 + '</table></div><div class="scroll"><table>' + t2 + "</table></div></div>";
  }
  function filteredTrades() {
    var f = state.filter;
    return state.result.trades.filter(function (t) {
      return f === "all" || t.side === f || (f === "win" && t.pnl > 0) || (f === "loss" && t.pnl <= 0);
    });
  }
  function renderTrades() {
    var list = filteredTrades().slice().reverse();
    var head = "<thead><tr><th class=num>#</th><th>Side</th><th>Entry (UTC)</th><th class=num>Entry</th><th>Exit (UTC)</th><th class=num>Exit</th><th>Exit by</th><th class=num>Lots</th><th class=num>P&amp;L $</th><th class=num>P&amp;L %</th><th class=num>Run-up</th><th class=num>Drawdown</th><th class=num>Bars</th><th class=num>Cum. P&amp;L</th></tr></thead>";
    var body = list.slice(0, 1500).map(function (t) {
      return '<tr data-n="' + t.n + '"' + (state.selected === t.n ? ' class="sel"' : "") + '><td class="num">' + t.n + '</td><td><span class="side ' + t.side + '">' + t.side + "</span></td><td>" + dt(t.entry_time) + '</td><td class="num">' + num(t.entry_price) + "</td><td>" + dt(t.exit_time) + '</td><td class="num">' + num(t.exit_price) + "</td><td>" + esc(t.exit_id) + '</td><td class="num">' + num(t.lots) + '</td><td class="num ' + cls(t.pnl) + '">' + num(t.pnl) + '</td><td class="num ' + cls(t.pnl) + '">' + num(t.pnl_pct) + '</td><td class="num">' + num(t.runup) + '</td><td class="num">' + num(t.drawdown) + '</td><td class="num">' + t.bars + '</td><td class="num ' + cls(t.cum_pnl) + '">' + num(t.cum_pnl) + "</td></tr>";
    }).join("");
    $("trades").innerHTML = head + "<tbody>" + (body || '<tr><td colspan="14">No trades match.</td></tr>') + "</tbody>";
  }
  function renderMonthly() {
    var rows = {}, years = [];
    state.result.monthly.forEach(function (m) {
      var y = m.month.slice(0, 4), k = Number(m.month.slice(5, 7));
      if (!rows[y]) { rows[y] = {}; years.push(y); }
      rows[y][k] = m.ret;
    });
    var names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    var h = "<thead><tr><th></th>" + names.map(function (n) { return "<th class=num>" + n + "</th>"; }).join("") + "<th class=num>Year</th></tr></thead><tbody>";
    years.forEach(function (y) {
      var comp = 1;
      h += "<tr><th>" + y + "</th>";
      for (var k = 1; k <= 12; k++) {
        var v = rows[y][k];
        if (v === undefined || v === null) { h += "<td></td>"; continue; }
        comp *= 1 + v / 100;
        h += '<td class="' + cls(v) + '" style="--a:' + Math.min(Math.abs(v) / 8, 1).toFixed(2) + '">' + (v > 0 ? "+" : "") + v.toFixed(1) + "</td>";
      }
      var yr = (comp - 1) * 100;
      h += '<td class="yr ' + cls(yr) + '">' + (yr > 0 ? "+" : "") + yr.toFixed(1) + "</td></tr>";
    });
    $("tab-monthly").innerHTML = '<div class="scroll"><table class="months">' + h + "</tbody></table></div>";
  }
  function renderCompare() {
    var hist = store.get("history", []);
    var h = "<thead><tr><th>When</th><th>Strategy</th><th>TF</th><th>Range</th><th>Costs</th><th>Inputs</th><th class=num>Net</th><th class=num>PF</th><th class=num>Max DD</th><th class=num>Trades</th></tr></thead><tbody>";
    h += hist.slice().reverse().map(function (x) {
      return "<tr><td>" + esc(x.when) + '</td><td class="name">' + esc(x.name) + "</td><td>" + esc(x.tf) + "</td><td>" + esc(x.range) + "</td><td>" + esc(x.preset) + '</td><td class="name">' + esc(x.params) + '</td><td class="num ' + cls(x.net) + '">' + money(x.net, 0) + '</td><td class="num">' + num(x.pf, 2) + '</td><td class="num">' + pct(x.dd, 1) + '</td><td class="num">' + x.trades + "</td></tr>";
    }).join("") || '<tr><td colspan="10">No runs yet.</td></tr>';
    $("compare").innerHTML = h + "</tbody>";
  }
  function renderAll() {
    renderOverview(); renderPerformance(); renderTrades(); renderMonthly(); renderCompare(); drawChart();
    $("checks").innerHTML = "";
  }

  // ---------------------------------------------------------------- controls
  function strategyDef() { return state.strategies[state.current]; }
  function fillStrategySelect() {
    var sel = $("strategy"), mine = [], ex = [];
    Object.keys(state.strategies).forEach(function (id) { (state.strategies[id].mine ? mine : ex).push(id); });
    var saved = store.get("saved", {});
    var html = "";
    var group = function (label, ids) {
      if (!ids.length) return "";
      return '<optgroup label="' + label + '">' + ids.map(function (id) {
        var s = state.strategies[id]; return '<option value="' + esc(id) + '">' + esc(s.name) + " · " + esc(s.timeframe) + "</option>";
      }).join("") + "</optgroup>";
    };
    var savedIds = Object.keys(saved).map(function (k) { return "saved:" + k; });
    savedIds.forEach(function (id) { state.strategies[id] = saved[id.slice(6)]; });
    html += group("Saved in this browser", savedIds) + group("My strategies", mine) + group("Examples", ex);
    sel.innerHTML = html;
  }
  function fillTimeframes() {
    $("tf").innerHTML = state.meta.timeframes.filter(function (tf) { return state.meta.data[tf]; }).map(function (tf) {
      return '<button type="button" role="radio" data-tf="' + tf + '">' + tf.toUpperCase().replace("M", "m").replace("H", "h").replace("D", "D") + "</button>";
    }).join("");
  }
  function markSeg(id, attr, value) {
    document.querySelectorAll("#" + id + " button").forEach(function (b) {
      var on = String(b.dataset[attr]) === String(value);
      b.setAttribute(b.getAttribute("role") === "radio" ? "aria-checked" : "aria-pressed", on ? "true" : "false");
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
    if (!state.strategies[id]) return;
    state.current = id;
    var s = strategyDef();
    state.custom = null;
    state.params = Object.assign({}, s.params);
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
    $("yaml-status").textContent = "";
    try { history.replaceState(null, "", "#" + encodeURIComponent(id)); } catch (e) { /* ignore */ }
  }
  function renderInputs() {
    var s = strategyDef(), keys = Object.keys(s.params || {});
    $("inputs").innerHTML = keys.length ? keys.map(function (k) {
      var v = state.params[k], isInt = Number.isInteger(s.params[k]);
      return '<label>' + esc(k.replace(/_/g, " ")) + '<input type="number" data-param="' + esc(k) + '" value="' + v + '" step="' + (isInt ? 1 : 0.1) + '" inputmode="decimal"></label>';
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
    state.running = on; $("busy").hidden = !on; $("run").disabled = on;
    $("run").querySelector(".run-label").textContent = on ? "Running…" : "Run backtest";
  }
  function showError(msg) {
    var box = '<div class="error-box">' + esc(msg) + "</div>";
    $("kpis").innerHTML = box; $("run-note").textContent = "";
    toast(msg);
  }
  function runBacktest() {
    var req = buildRequest(), my = ++state.seq;
    setBusy(true);
    return api("backtest", req).then(function (r) {
      if (my !== state.seq) return;
      state.result = r; renderAll(); remember(r, req);
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
  var autoRun = debounce(runBacktest, 500);

  function runChecks() {
    var btn = $("run-checks"); btn.disabled = true; btn.textContent = "Running checklist…";
    $("checks").innerHTML = '<p class="hint">Running about 15 backtests. This can take up to a minute on long ranges.</p>';
    api("validate", buildRequest()).then(function (v) {
      var rows = v.checks.map(function (c) {
        return '<tr><td><span class="chip ' + c.status + '">' + c.status.toUpperCase() + "</span></td><td>" + esc(c.name) + "</td><td>" + esc(c.value) + '</td><td class="rule">' + esc(c.rule) + "</td></tr>";
      }).join("");
      $("checks").innerHTML = '<p class="verdict ' + v.verdict + '">' + esc(v.headline) + "</p>" +
        (v.quick ? '<p class="hint">Long range: parameter-stability and look-ahead checks were skipped to stay within the time limit.</p>' : "") +
        '<div class="scroll"><table class="checks"><thead><tr><th>Result</th><th>Check</th><th>Value</th><th>Rule</th></tr></thead><tbody>' + rows + "</tbody></table></div>";
    }).catch(function (e) { $("checks").innerHTML = '<div class="error-box">' + esc(e.message) + "</div>"; })
      .then(function () { btn.disabled = false; btn.textContent = "Run checklist"; });
  }
  function downloadCSV() {
    var r = state.result; if (!r) return;
    var cols = ["n", "side", "entry_time", "entry_price", "exit_time", "exit_price", "exit_id", "lots", "pnl", "pnl_pct", "runup", "drawdown", "bars", "cum_pnl", "commission"];
    var lines = [cols.join(",")].concat(r.trades.map(function (t) {
      return cols.map(function (c) { return /time/.test(c) ? new Date(t[c] * 1000).toISOString() : t[c]; }).join(",");
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
    }).catch(function (e) { toast(e.message); });
  }
  function saveYaml() {
    var text = $("yaml").value, m = /^name:\s*(.+)$/m.exec(text);
    if (!m) { $("yaml-status").textContent = "Add a name: line first."; return; }
    var name = m[1].trim().replace(/^["']|["']$/g, ""), key = name.toLowerCase().replace(/[^a-z0-9]+/g, "-");
    state.custom = text;
    $("yaml-status").textContent = "Checking the rules…";
    runBacktest().then(function () {
      var r = state.result;
      if (!r || r.strategy.name !== name) { $("yaml-status").textContent = "Fix the error above before saving."; return; }
      var saved = store.get("saved", {});
      saved[key] = { name: name, timeframe: r.data.timeframe, yaml: text, params: r.strategy.params, settings: {}, mine: true,
        description: "Saved in this browser on " + new Date().toLocaleDateString() + ".", evidence_level: "Your idea" };
      store.set("saved", saved);
      fillStrategySelect();
      setStrategy("saved:" + key, true);
      $("yaml-status").textContent = "Saved as \u201c" + name + "\u201d in this browser. To keep it for good, add the card to strategies/ in the repo.";
    });
  }

  // ---------------------------------------------------------------- wiring
  function wire() {
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
    $("reset-inputs").addEventListener("click", function () { state.params = Object.assign({}, strategyDef().params); renderInputs(); runBacktest(); });
    $("apply-yaml").addEventListener("click", function () {
      state.custom = $("yaml").value; $("yaml-status").textContent = "Running your edited rules…";
      runBacktest().then(function () { if (state.result) $("yaml-status").textContent = "Showing results for your edited rules (not saved yet)."; });
    });
    $("save-yaml").addEventListener("click", saveYaml);
    $("pine-btn").addEventListener("click", showPine);
    $("pine-close").addEventListener("click", function () { $("pine-dialog").close(); });
    $("pine-copy").addEventListener("click", function () {
      var text = $("pine-code").textContent;
      (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject()).then(function () { toast("Pine Script copied"); })
        .catch(function () { var r = document.createRange(); r.selectNodeContents($("pine-code")); var s = getSelection(); s.removeAllRanges(); s.addRange(r); toast("Selected: press copy"); });
    });
    document.querySelector(".tabs").addEventListener("click", function (e) {
      var b = e.target.closest("button[data-tab]"); if (!b) return;
      document.querySelectorAll(".tabs button").forEach(function (x) { x.setAttribute("aria-selected", x === b ? "true" : "false"); });
      document.querySelectorAll(".tab-body").forEach(function (x) { x.hidden = x.id !== "tab-" + b.dataset.tab; });
      if (b.dataset.tab === "compare") renderCompare();
      if (b.dataset.tab === "overview" && eqChart) eqChart.timeScale().fitContent();
    });
    $("trade-filter").addEventListener("click", function (e) {
      var b = e.target.closest("button"); if (!b) return;
      state.filter = b.dataset.f; document.querySelectorAll("#trade-filter button").forEach(function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
      renderTrades();
    });
    $("trades").addEventListener("click", function (e) {
      var tr = e.target.closest("tr[data-n]"); if (!tr) return;
      var n = Number(tr.dataset.n); var t = state.result.trades.find(function (x) { return x.n === n; }); if (t) focusTrade(t);
    });
    $("csv").addEventListener("click", downloadCSV);
    $("run-checks").addEventListener("click", runChecks);
    $("clear-history").addEventListener("click", function () { store.set("history", []); renderCompare(); });
    $("open-settings").addEventListener("click", function () { $("panel").classList.add("open"); });
    $("close-settings").addEventListener("click", function () { $("panel").classList.remove("open"); });
  }

  // ---------------------------------------------------------------- boot
  initCharts();
  wire();
  markSeg("preset", "preset", state.preset);
  api("strategies").then(function (meta) {
    state.meta = meta;
    meta.strategies.forEach(function (s) { state.strategies[s.id] = s; });
    fillTimeframes(); fillStrategySelect();
    var want = decodeURIComponent((location.hash || "").slice(1));
    var first = state.strategies[want] ? want : (meta.strategies.filter(function (s) { return s.mine; })[0] || {}).id || "tsmom_daily";
    if (!state.strategies[first]) first = meta.strategies[0].id;
    setStrategy(first);
    return runBacktest();
  }).catch(function (e) { showError("Could not reach the backtest server: " + e.message); });
})();
