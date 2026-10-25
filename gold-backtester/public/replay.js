/* Bar replay: hide the future, step through history bar by bar, and trade by hand. Fills follow the
   backtest engine's rules (you act at a bar's close; stops and targets trigger along TradingView's
   open → nearer extreme → other extreme → close path; spread, commission, slippage and swap included),
   and every decision is recorded. "Finish and review" re-runs the session on the server for the full
   Strategy Tester report, and "Build a strategy" turns your entries into a strategy card. */
(function () {
  "use strict";
  var G = window.GSL, TA = window.TA, $ = function (id) { return document.getElementById(id); };
  if (!G || !G.price) return;
  var R = { picking: false, active: false, bars: null, cur: -1, last: true, loading: null, timer: null,
    session: null, pos: null, s: null, lastResult: null };
  var MAX_SESSIONS = 60;

  // ------------------------------------------------------------- sessions (kept in this browser)
  function sessions() { return G.store.get("sessions", []); }
  function saveSession() {
    var S = R.session; if (!S) return;
    S.position = R.pos ? JSON.parse(JSON.stringify(R.pos)) : null;
    var all = sessions().filter(function (x) { return x.id !== S.id; });
    all.push(S); while (all.length > MAX_SESSIONS) all.shift();
    G.store.set("sessions", all);
  }
  function sessionNet(S) { return S.trades.reduce(function (a, t) { return a + t.pnl; }, 0) + (S.swap || 0); }
  function newSession(tf, t) {
    var d = new Date(t * 1000).toISOString().slice(0, 10);
    return { format: "goldlab-replay-session", version: 1, id: "s" + Date.now().toString(36), name: "Replay " + tf + " from " + d,
      created: new Date().toISOString(), timeframe: tf, preset: R.s.preset, settings: R.s.request, start_time: t, current_time: t,
      trades: [], position: null, swap: 0, events: [] };
  }
  function log(type, extra) { var e = Object.assign({ type: type, time: R.bars.t[R.cur] }, extra || {}); R.session.events.push(e); if (R.session.events.length > 2000) R.session.events.shift(); }

  // ------------------------------------------------------------- costs, captured when the session starts
  function captureSettings(saved) {
    var req = saved ? { preset: saved.preset, settings: saved.settings } : G.buildRequest(), st = req.settings || {};
    var d = G.state.meta.defaults.realistic, tv = req.preset === "tradingview";
    var pick = function (k) { return st[k] !== undefined && st[k] !== null ? st[k] : d[k]; };
    return {
      preset: req.preset, request: st,
      capital: st.initial_capital || d.initial_capital,
      commission: tv ? 0 : pick("commission_value"), slipTicks: tv ? 0 : pick("slippage_ticks"),
      spreadMode: tv ? "none" : pick("spread_mode"), spreadFixed: tv ? 0 : (st.spread_fixed || 0),
      swapLong: tv ? 0 : pick("swap_long"), swapShort: tv ? 0 : pick("swap_short"),
      intrabar: tv ? "tv" : (st.intrabar || "tv"), margin: tv ? 100 : 5,
    };
  }
  function spread(j) { return R.s.spreadMode === "data" ? (R.bars.sp[j] || 0) : R.s.spreadMode === "fixed" ? R.s.spreadFixed : 0; }
  function slip() { return R.s.slipTicks * 0.01; }
  function fee(qty) { return R.s.commission ? qty / 100 * R.s.commission : 0; }
  function qtyOf(lots) { return Math.round(Math.floor(lots * 100 + 1e-9) * 1e8) / 1e8; }
  function cash() { return R.s.capital + R.session.trades.reduce(function (a, t) { return a + t.pnl; }, 0) + (R.session.swap || 0); }
  function mark(P, j) { var c = R.bars.c[j]; return P.side > 0 ? c : c + spread(j); }
  function openPnl(j) { var P = R.pos; return P ? P.side * (mark(P, j) - P.entry_price) * P.qty - P.fee_entry : 0; }

  // ------------------------------------------------------------- the broker (mirrors goldlab/engine/broker.py)
  function triggers(P, s) {
    var out = [];
    if (P.side > 0) { if (P.sl !== null) out.push([-1, P.sl, "SL"]); if (P.tp !== null) out.push([1, P.tp, "TP"]); }
    else { if (P.sl !== null) out.push([1, P.sl - s, "SL"]); if (P.tp !== null) out.push([-1, P.tp - s, "TP"]); }
    return out;
  }
  function fillPrice(P, kind, bid, s, gap) {
    var sl = slip();
    if (kind === "SL") return P.side > 0 ? (gap ? Math.min(P.sl, bid) : P.sl) - sl : (gap ? Math.max(P.sl, bid + s) : P.sl) + sl;
    return P.side > 0 ? (gap ? Math.max(P.tp, bid) : P.tp) : (gap ? Math.min(P.tp, bid + s) : P.tp);
  }
  function processBar(j) {
    var P = R.pos; if (!P) return;
    var b = R.bars, o = b.o[j], h = b.h[j], l = b.l[j], c = b.c[j], s = spread(j);
    if (b.roll[j] && (R.s.swapLong || R.s.swapShort)) {
      var f = (P.side > 0 ? R.s.swapLong : R.s.swapShort) * P.qty / 100 * b.roll[j];
      P.swap += f; R.session.swap = (R.session.swap || 0) + f;
    }
    var trig = triggers(P, s);
    for (var k = 0; k < trig.length; k++) {
      var d = trig[k][0], thr = trig[k][1];
      if ((d > 0 && o >= thr) || (d < 0 && o <= thr)) { closePos(trig[k][2], fillPrice(P, trig[k][2], o, s, true), j); return; }
    }
    var path = R.s.intrabar === "pessimistic" ? (P.side > 0 ? [o, l, h, c] : [o, h, l, c]) : ((h - o) <= (o - l) ? [o, h, l, c] : [o, l, h, c]);
    for (var m = 1; m < path.length; m++) {
      var a = path[m - 1], z = path[m], best = null;
      trig.forEach(function (x) {
        if (z > a && x[0] > 0 && a < x[1] && x[1] <= z && (best === null || x[1] < best[1])) best = x;
        if (z < a && x[0] < 0 && z <= x[1] && x[1] < a && (best === null || x[1] > best[1])) best = x;
      });
      if (best) { closePos(best[2], fillPrice(P, best[2], best[1], s, false), j); return; }
    }
  }
  function openPos(side) {
    if (R.pos) { G.toast("Close your position first."); return; }
    var j = R.cur, lots = Number($("rp-lots").value);
    if (!(lots >= 0.01 && lots <= 100)) { G.toast("Lots must be between 0.01 and 100."); $("rp-lots").focus(); return; }
    var qty = qtyOf(lots), s = spread(j), dir = side === "long" ? 1 : -1;
    var price = dir > 0 ? R.bars.c[j] + s + slip() : R.bars.c[j] - slip();
    var need = qty * price * R.s.margin / 100, eq = cash();
    if (need > eq) { G.toast("Not enough margin: " + G.money(need, 0) + " needed, balance " + G.money(eq, 0) + ". Use fewer lots."); return; }
    var dSL = Number($("rp-sl").value), dTP = Number($("rp-tp").value);
    var sl = $("rp-sl").value !== "" && dSL > 0 ? round2(price - dir * dSL) : null;
    var tp = $("rp-tp").value !== "" && dTP > 0 ? round2(price + dir * dTP) : null;
    R.pos = { id: "M" + (R.session.trades.length + 1), side: dir, sideName: side, lots: lots, qty: qty, entry_price: price,
      entry_time: R.bars.t[j], entry_index: j, sl: sl, tp: tp, init_sl: sl, init_tp: tp, fee_entry: fee(qty), swap: 0,
      note: $("rp-note").value.trim().slice(0, 300), mods: [] };
    G.store.set("rp-lots", lots);
    log(side === "long" ? "buy" : "sell", { price: price, lots: lots, sl: sl, tp: tp });
    $("rp-note").value = "";
    saveSession(); refresh();
    G.announce((side === "long" ? "Bought " : "Sold ") + lots + " lot at " + G.num(price) + ".");
  }
  function closePos(by, price, j) {
    var P = R.pos; if (!P) return;
    var gross = P.side * (price - P.entry_price) * P.qty, pnl = gross - fee(P.qty) - P.fee_entry;
    var risk = P.init_sl !== null && P.side * (P.entry_price - P.init_sl) > 0 ? Math.abs(P.entry_price - P.init_sl) * P.qty : null;
    var t = { id: P.id, side: P.sideName, lots: P.lots, entry_time: P.entry_time, entry_price: P.entry_price, sl: P.init_sl,
      tp: P.init_tp, final_sl: P.sl, final_tp: P.tp, exit_time: R.bars.t[j], exit_price: price, exit_by: by,
      pnl: pnl, r: risk ? pnl / risk : null, bars: j - P.entry_index, swap: P.swap, note: P.note, mods: P.mods };
    R.session.trades.push(t); R.pos = null;
    log("close", { by: by, price: price, pnl: pnl });
    saveSession();
    var msg = (by === "TP" ? "Take profit hit: " : by === "SL" ? "Stop loss hit: " : "Closed: ") + (pnl >= 0 ? "+" : "") + G.money(pnl);
    G.toast(msg); G.announce(msg);
  }
  function modify(sl, tp) {
    var P = R.pos; if (!P) return false;
    var j = R.cur, bid = R.bars.c[j], ask = bid + spread(j);
    if (sl !== null && (P.side > 0 ? sl >= bid : sl <= ask)) { G.toast("The stop must be " + (P.side > 0 ? "below" : "above") + " the current price."); return false; }
    if (tp !== null && (P.side > 0 ? tp <= bid : tp >= ask)) { G.toast("The target must be " + (P.side > 0 ? "above" : "below") + " the current price."); return false; }
    P.mods = P.mods.filter(function (m) { return m.time !== R.bars.t[j]; });
    P.mods.push({ time: R.bars.t[j], sl: sl, tp: tp });
    P.sl = sl; P.tp = tp;
    log("modify", { sl: sl, tp: tp }); saveSession(); refresh();
    return true;
  }
  function round2(v) { return Math.round(v * 100) / 100; }

  // ------------------------------------------------------------- chart
  function barObj(i) { var b = R.bars; return { time: b.t[i], open: b.o[i], high: b.h[i], low: b.l[i], close: b.c[i] }; }
  function markers() {
    var up = G.tok("--chart-up"), dn = G.tok("--chart-down"), mk = [];
    R.session.trades.forEach(function (t) {
      var long = t.side === "long";
      mk.push({ time: t.entry_time, position: long ? "belowBar" : "aboveBar", shape: long ? "arrowUp" : "arrowDown", color: long ? up : dn, text: long ? "Buy" : "Sell" });
      mk.push({ time: t.exit_time, position: long ? "aboveBar" : "belowBar", shape: "circle", color: t.pnl >= 0 ? up : dn, size: 0.7, text: (t.pnl >= 0 ? "+" : "") + Math.round(t.pnl) });
    });
    if (R.pos) mk.push({ time: R.pos.entry_time, position: R.pos.side > 0 ? "belowBar" : "aboveBar", shape: R.pos.side > 0 ? "arrowUp" : "arrowDown", color: G.tok("--gold"), text: R.pos.side > 0 ? "Buy" : "Sell" });
    mk = mk.filter(function (m) { return m.time <= R.bars.t[R.cur]; }).sort(function (a, b) { return a.time - b.time; });
    G.markers.setMarkers(mk);
  }
  function orderLines() {
    var P = R.pos;
    if (!P) { G.draw.setOrderLines([]); return; }
    var lines = [{ key: "entry", price: P.entry_price, color: "#6b7380", label: (P.side > 0 ? "Long " : "Short ") + P.lots + " @ " + G.num(P.entry_price), dash: true }];
    if (P.sl !== null) lines.push({ key: "sl", price: P.sl, color: G.tok("--chart-down"), label: "Stop " + G.num(P.sl) + "  " + G.money(-Math.abs(P.entry_price - P.sl) * P.qty, 0), draggable: true });
    if (P.tp !== null) lines.push({ key: "tp", price: P.tp, color: G.tok("--chart-up"), label: "Target " + G.num(P.tp) + "  +" + G.money(Math.abs(P.tp - P.entry_price) * P.qty, 0).replace("-", ""), draggable: true });
    G.draw.setOrderLines(lines, function (key, price) {
      var p = round2(price);
      if (!modify(key === "sl" ? p : R.pos.sl, key === "tp" ? p : R.pos.tp)) orderLines();
    });
  }

  // ------------------------------------------------------------- UI
  function atrNow() {
    if (!R._atr || R._atrFor !== R.bars.t.length) { R._atr = TA.atr(R.bars.h, R.bars.l, R.bars.c, 14); R._atrFor = R.bars.t.length; }
    var v = R._atr[R.cur]; return v === v ? v : null;
  }
  function refresh() {
    if (!R.active) return;
    var j = R.cur, b = R.bars, s = spread(j), P = R.pos, S = R.session;
    $("rp-time").textContent = new Date(b.t[j] * 1000).toISOString().slice(0, 16).replace("T", " ") + " UTC";
    $("rp-bid").textContent = G.num(b.c[j] - slip());
    $("rp-ask").textContent = G.num(b.c[j] + s + slip());
    var a = atrNow(); $("rp-atr").textContent = a ? "ATR(14) now " + G.num(a, 2) : "";
    var lots = Number($("rp-lots").value) || 0, dSL = Number($("rp-sl").value) || 0, eq = cash();
    $("rp-risk").textContent = dSL > 0 && lots > 0 ? "Risk at stop ≈ " + G.money(dSL * qtyOf(lots), 0) + " (" + G.num(dSL * qtyOf(lots) / eq * 100, 1) + "% of balance)" : "No stop: risk is open-ended";
    $("rp-ticket").hidden = !!P;
    $("rp-position").hidden = !P;
    if (P) {
      var op = openPnl(j), risk = P.init_sl !== null ? Math.abs(P.entry_price - P.init_sl) * P.qty : null;
      $("rp-pos-text").innerHTML = '<span class="side ' + P.sideName + '">' + P.sideName + "</span> " + P.lots + " lot @ " + G.num(P.entry_price) +
        ' · open P&amp;L <b class="' + G.cls(op) + '">' + (op >= 0 ? "+" : "") + G.money(op) + "</b>" + (risk ? " (" + G.num(op / risk, 2) + "R)" : "");
      if (document.activeElement !== $("rp-pos-sl")) $("rp-pos-sl").value = P.sl === null ? "" : P.sl;
      if (document.activeElement !== $("rp-pos-tp")) $("rp-pos-tp").value = P.tp === null ? "" : P.tp;
    }
    var n = S.trades.length, wins = S.trades.filter(function (t) { return t.pnl > 0; }).length, net = sessionNet(S);
    $("rp-stats").innerHTML = "Balance <b>" + G.money(eq + (P ? openPnl(j) : 0), 0) + "</b> · " + n + " trade" + (n === 1 ? "" : "s") +
      (n ? ' · net <b class="' + G.cls(net) + '">' + (net >= 0 ? "+" : "") + G.money(net, 0) + "</b> · " + Math.round(wins / n * 100) + "% wins" : "");
    $("rp-count").textContent = n;
    $("rp-trades").innerHTML = n ? "<thead><tr><th>#</th><th>Side</th><th>Entry</th><th class=num>Price</th><th>Exit by</th><th class=num>P&amp;L</th><th class=num>R</th><th>Note</th></tr></thead><tbody>" +
      S.trades.slice().reverse().map(function (t) {
        return "<tr><td>" + G.esc(t.id) + '</td><td><span class="side ' + t.side + '">' + t.side + "</span></td><td>" + G.dt(t.entry_time) + '</td><td class="num">' + G.num(t.entry_price) +
          "</td><td>" + ({ SL: "Stop loss", TP: "Take profit", Close: "Closed" }[t.exit_by] || t.exit_by) + '</td><td class="num ' + G.cls(t.pnl) + '">' + G.num(t.pnl) +
          '</td><td class="num">' + (t.r === null ? "–" : G.num(t.r, 2)) + '</td><td class="note">' + G.esc(t.note || "") + "</td></tr>";
      }).join("") + "</tbody>" : "<tbody><tr><td>No trades yet. Buy or sell, then step forward.</td></tr></tbody>";
    $("rp-play").textContent = R.timer ? "❚❚ Pause" : "▶ Play";
    $("rp-play").setAttribute("aria-pressed", R.timer ? "true" : "false");
    $("rp-learn").disabled = n < 3;
    markers(); orderLines();
  }
  function showDock(mode) {
    $("replay-dock").hidden = !mode;
    $("replay-hint").hidden = mode !== "run";
    $("rp-pick").hidden = mode !== "pick";
    $("rp-run").hidden = mode !== "run";
    $("replay-btn").setAttribute("aria-pressed", mode ? "true" : "false");
  }

  // ------------------------------------------------------------- start, step, play, stop
  function beginPick() {
    if (!G.state.result || !G.state.meta) { G.toast("Wait for the chart to load first."); return; }
    if (R.active) return;
    R.picking = true; showDock("pick");
    var d = G.state.meta.data[G.state.tf] || {};
    var end = d.end ? new Date(d.end + "T00:00:00Z") : new Date();
    $("rp-date").min = d.start || ""; $("rp-date").max = d.end || "";
    if (!$("rp-date").value) $("rp-date").value = new Date(end.getTime() - 180 * 864e5).toISOString().slice(0, 10);
    G.onChartClick = function (p) { if (!R.picking || !p || p.time === undefined) return false; startAt(p.time); return true; };
    G.announce("Bar replay: click a candle on the chart, or pick a date, to choose where to start.");
    $("rp-date").focus();
  }
  function cancelPick() { R.picking = false; G.onChartClick = null; showDock(null); $("replay-btn").focus(); }
  function loadBars(at, before) {
    return G.api("bars", { timeframe: R.tf, at: at, before: before, after: 3000 });
  }
  function toColumns(b) { return { t: b.t, o: b.o, h: b.h, l: b.l, c: b.c, v: b.v, sp: b.sp, roll: b.roll }; }
  function startAt(t, resume) {
    R.picking = false; G.onChartClick = null;
    R.tf = resume ? resume.timeframe : G.state.tf;
    R.s = captureSettings(resume);
    $("rp-pick-status").textContent = "Loading bars…";
    return loadBars(t, 400).then(function (b) {
      R.bars = toColumns(b); R.cur = b.index; R.last = b.last;
      if (resume) {
        R.session = resume; R.pos = resume.position ? JSON.parse(JSON.stringify(resume.position)) : null;
        if (R.bars.t[R.cur] !== resume.current_time) G.toast("Resuming at the nearest bar.");
      } else {
        R.session = newSession(R.tf, R.bars.t[R.cur]); R.pos = null;
      }
      R.session.current_time = R.bars.t[R.cur];
      enter();
      saveSession();
    }).catch(function (e) { $("rp-pick-status").textContent = e.message; R.picking = true; if (!resume) beginPick(); else G.toast(e.message); });
  }
  function enter() {
    R.active = true; G.replayActive = true; G.setLocked(true); G.clearSelection();
    // the strategy's own lines would show the future and keep their times on the time axis: empty them
    // (drawChart() rebuilds them when replay ends)
    (G.state.plotSeries || []).forEach(function (s) { s.setData([]); });
    G.markers.setMarkers([]);
    G.candles.setData(R.bars.t.slice(0, R.cur + 1).map(function (_, i) { return barObj(i); }));
    G.setBars(R.bars, R.tf, R.cur + 1);
    G.price.timeScale().setVisibleLogicalRange({ from: R.cur - 120, to: R.cur + 12 });
    $("rp-lots").value = G.store.get("rp-lots", 0.1);
    var a = atrNow();
    if (a && !$("rp-sl").value) { $("rp-sl").value = (Math.round(a * 1.5 * 10) / 10).toFixed(1); $("rp-tp").value = (Math.round(a * 3 * 10) / 10).toFixed(1); }
    $("rp-pick-status").textContent = "";
    showDock("run"); refresh();
    $("chart-note").textContent = "Bar replay on " + R.tf + ": the future is hidden. Bars after " + G.dt(R.bars.t[R.cur]) + " UTC appear as you step forward.";
    G.announce("Replay started at " + G.dt(R.bars.t[R.cur]) + " UTC. Use Next bar or Play to move forward.");
    $("rp-step").focus();
  }
  function step() {
    if (!R.active) return Promise.resolve(false);
    if (R.cur >= R.bars.t.length - 1) {
      if (R.last) { pause(); G.toast("That's the end of the data for " + R.tf + "."); return Promise.resolve(false); }
      if (!R.loading) {
        R.loading = loadBars(R.bars.t[R.bars.t.length - 1] + 1, 0).then(function (b) {
          ["t", "o", "h", "l", "c", "v", "sp", "roll"].forEach(function (k) { R.bars[k] = R.bars[k].concat(b[k]); });
          R.last = b.last; R.loading = null;
          G.setBars(R.bars, R.tf, R.cur + 1);
        }).catch(function (e) { R.loading = null; pause(); G.toast(e.message); });
      }
      return R.loading.then(function () { return step(); });
    }
    R.cur++;
    processBar(R.cur);
    G.shown = R.cur + 1;
    G.candles.update(barObj(R.cur));
    G.emit("step", R.cur + 1);
    R.session.current_time = R.bars.t[R.cur];
    saveSession(); refresh();
    return Promise.resolve(true);
  }
  function play() {
    if (R.timer) { pause(); return; }
    var speed = Number($("rp-speed").value) || 1;
    R.timer = setInterval(function () { if (!R.loading) step(); }, 1000 / speed);
    refresh();
  }
  function pause() { if (R.timer) { clearInterval(R.timer); R.timer = null; } if (R.active) refresh(); }
  function leave() {
    pause();
    R.active = false; G.replayActive = false; G.setLocked(false);
    G.draw.setOrderLines([]);
    showDock(null);
    if (G.state.result) G.drawChart();
  }
  function exit() {
    var S = R.session; leave();
    if (S) G.toast("Session saved. Resume it from My sessions.");
    $("replay-btn").focus();
  }

  // ------------------------------------------------------------- review and learn
  function request(S) {
    var trades = S.trades.map(function (t) {
      return { side: t.side, lots: t.lots, entry_time: t.entry_time, entry_price: t.entry_price, sl: t.sl, tp: t.tp,
        exit_time: t.exit_by === "Close" ? t.exit_time : null, exit_by: t.exit_by, note: t.note, mods: (t.mods || []).map(function (m) { return { time: m.time, sl: m.sl, tp: m.tp }; }) };
    });
    if (S.position) {
      var P = S.position;
      trades.push({ side: P.sideName, lots: P.lots, entry_time: P.entry_time, entry_price: P.entry_price, sl: P.init_sl, tp: P.init_tp,
        exit_time: null, exit_by: "", note: P.note, mods: P.mods.map(function (m) { return { time: m.time, sl: m.sl, tp: m.tp }; }) });
    }
    return trades;
  }
  function review(S) {
    S = S || R.session;
    if (!S || (!S.trades.length && !S.position)) { G.toast("No trades to review yet. Buy or sell first."); return Promise.resolve(); }
    if (R.active) leave();
    G.toast("Reviewing your session…");
    return G.api("manual", { timeframe: S.timeframe, preset: S.preset, settings: S.settings, start_time: S.start_time, end_time: S.current_time,
      trades: request(S), name: S.name }).then(function (r) {
      r.session_id = S.id; R.lastResult = r;
      G.showResult(r); G.selectTab("overview");
      G.announce("Review ready: " + r.metrics.total_trades + " trades, net " + G.money(r.metrics.net_profit, 0) + ".");
    }).catch(function (e) { G.toast("Couldn't review the session: " + e.message); });
  }
  var learned = null;
  function learnFrom(list) {
    var trades = [], seen = [], tf = list[0].timeframe;
    list.forEach(function (S) {
      S.trades.forEach(function (t) {
        trades.push({ side: t.side, lots: t.lots, entry_time: t.entry_time, entry_price: t.entry_price, sl: t.sl, tp: t.tp,
          exit_time: t.exit_time, exit_by: t.exit_by, note: t.note });
      });
      seen.push([S.start_time, S.current_time]);
    });
    if (trades.length < 3) { G.toast("Take at least 3 trades before building a strategy from them."); return Promise.resolve(); }
    var name = list.length === 1 ? list[0].name.replace(/^Replay/, "My setup") : "My setup (" + tf + ", " + list.length + " sessions)";
    G.toast("Looking for the pattern in your " + trades.length + " trades…");
    return G.api("learn", { timeframe: tf, trades: trades, seen: seen, name: name }).then(function (out) {
      learned = out; showLearn(out);
    }).catch(function (e) { G.toast("Couldn't build a strategy: " + e.message); });
  }
  function pctTxt(v) { return Math.round(v * 100) + "%"; }
  function showLearn(out) {
    var h = '<p>From <b>' + out.trades + " trades</b> on " + G.esc(out.timeframe) + ".</p>";
    ["long", "short"].forEach(function (side) {
      var s = out.sides[side]; if (!s || !s.trades) return;
      h += "<h3>" + (side === "long" ? "Your buys" : "Your sells") + " (" + s.trades + ")</h3>";
      if (!s.found) {
        h += '<p class="hint">' + (s.trades < 3 ? "Take at least 3 of these to learn a rule from them." :
          "No clear pattern among the conditions checked. Adding a note on why you entered helps you spot it.") + "</p>";
        return;
      }
      h += '<ul class="learn-conds">' + s.conditions.map(function (c) {
        return "<li><b>" + G.esc(c.label) + "</b><span>true at " + pctTxt(c.at_your_entries) + " of your entries, " + pctTxt(c.on_all_bars) + " of all bars</span></li>";
      }).join("") + "</ul>";
      h += '<p class="hint">Stop: ' + s.stop.atr_multiple + " × ATR(14)" + (s.stop.from_trades ? " (your usual stop)" : "") +
        (s.target ? ". Target: " + s.target.r_multiple + "R (your usual target)" : ". No fixed target") + (s.max_bars ? ". You usually held about " + s.max_bars + " bars" : "") + ".</p>";
    });
    (out.notes || []).filter(function (n) { return !/^Only \d|don't share a clear pattern/.test(n); }).forEach(function (n) { h += '<p class="hint">' + G.esc(n) + "</p>"; });
    if (out.reproduction) {
      var rp = out.reproduction;
      h += '<p class="learn-score">The strategy repeats <b>' + rp.reproduced + " of your " + rp.your_entries + " entries</b> on the bars you replayed (it took " + rp.card_entries + " trades there).</p>";
    }
    if (out.backtest) {
      var bt = out.backtest;
      h += "<p>On " + G.esc(out.timeframe) + " data from " + bt.start + " to " + bt.end + ": <b>" + bt.total_trades + " trades, net " + G.money(bt.net_profit, 0) +
        ", profit factor " + G.num(bt.profit_factor, 2) + ", max drawdown " + G.pct(bt.max_drawdown_pct, 1) + "</b>. Check it with the checklist before trusting it.</p>";
    }
    if (out.card) h += '<details><summary>Strategy card (YAML)</summary><pre tabindex="0" aria-label="Learned strategy card"><code>' + G.esc(out.card) + "</code></pre></details>";
    else h += '<p class="hint">There isn\'t enough of a pattern to write a strategy yet. Take more trades, and add a note on why you entered.</p>';
    $("learn-body").innerHTML = h;
    $("learn-run").disabled = !out.card; $("learn-save").disabled = !out.card;
    var d = $("learn-dialog"); if (d.showModal) d.showModal(); else d.setAttribute("open", "");
    $("learn-close").focus();
  }
  function loadLearned(andSave) {
    if (!learned || !learned.card) return;
    $("learn-dialog").close();
    if (R.active) leave();
    G.setTimeframe(learned.timeframe);
    $("yaml").value = learned.card; $("rules-block").open = true;
    G.state.custom = learned.card;
    var p = andSave ? G.saveYaml() : G.runBacktest();
    return p && p.then ? p.then(function () { if (!andSave) $("yaml-status").textContent = "Showing your learned strategy. Save it to keep it."; }) : p;
  }

  // ------------------------------------------------------------- sessions dialog
  function renderSessions() {
    var all = sessions().slice().reverse();
    var groups = {};
    all.forEach(function (S) { groups[S.timeframe] = (groups[S.timeframe] || 0) + S.trades.length; });
    $("sessions-list").innerHTML = all.length ? '<div class="scroll"><table class="sessions"><caption class=sr>Saved replay sessions</caption><thead><tr><th scope=col>Session</th><th scope=col>TF</th><th class=num scope=col>Trades</th><th class=num scope=col>Net</th><th scope=col>Actions</th></tr></thead><tbody>' +
      all.map(function (S) {
        var net = sessionNet(S);
        return '<tr data-id="' + S.id + '"><td class="name">' + G.esc(S.name) + "<small>" + G.dt(S.start_time) + " → " + G.dt(S.current_time) + (S.position ? " · position open" : "") + "</small></td><td>" + G.esc(S.timeframe) +
          '</td><td class="num">' + S.trades.length + '</td><td class="num ' + G.cls(net) + '">' + G.money(net, 0) + '</td><td class="acts">' +
          '<button type="button" class="btn small" data-act="resume">Resume</button><button type="button" class="btn small ghost" data-act="review">Review</button>' +
          '<button type="button" class="btn small ghost" data-act="learn"' + (S.trades.length < 3 ? " disabled" : "") + '>Build strategy</button>' +
          '<button type="button" class="btn small ghost" data-act="export">Export</button><button type="button" class="btn small ghost" data-act="delete" aria-label="Delete ' + G.esc(S.name) + '">Delete</button></td></tr>';
      }).join("") + "</tbody></table></div>" +
      Object.keys(groups).filter(function (tf) { return all.filter(function (S) { return S.timeframe === tf; }).length > 1 && groups[tf] >= 3; }).map(function (tf) {
        return '<button type="button" class="btn small" data-learn-tf="' + tf + '">Build one strategy from all ' + tf + " sessions (" + groups[tf] + " trades)</button>";
      }).join(" ")
      : '<p class="hint">No sessions yet. Press Replay, pick a start, and trade.</p>';
  }
  function openSessions() {
    renderSessions();
    var d = $("sessions-dialog"); if (d.showModal) d.showModal(); else d.setAttribute("open", "");
    $("sessions-close").focus();
  }
  function download(name, obj) {
    var blob = new Blob([JSON.stringify(obj, null, 2)], { type: "application/json" });
    var a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name;
    document.body.appendChild(a); a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 500);
  }
  function importSession(file) {
    var fr = new FileReader();
    fr.onload = function () {
      try {
        var S = JSON.parse(fr.result);
        if (S.format !== "goldlab-replay-session" || !Array.isArray(S.trades) || !S.timeframe) throw new Error("This isn't a replay session file.");
        S.id = "s" + Date.now().toString(36); S.events = S.events || []; S.swap = S.swap || 0;
        var all = sessions(); all.push(S); G.store.set("sessions", all.slice(-MAX_SESSIONS));
        renderSessions(); G.toast("Imported “" + S.name + "”");
      } catch (e) { G.toast("Couldn't import: " + e.message); }
    };
    fr.readAsText(file);
  }

  // ------------------------------------------------------------- results notice
  G.on("result", function (r) {
    var manual = r && r.strategy && r.strategy.manual;
    $("mode-note").hidden = !manual;
    if (manual) {
      var S = sessions().find(function (x) { return x.id === r.session_id; });
      $("mode-text").innerHTML = "<b>Your replay session.</b> " + r.metrics.total_trades + " closed trades on " + G.esc(r.data.timeframe) + ", " + r.data.start.slice(0, 10) + " → " + r.data.end.slice(0, 10) +
        ", with the same costs and fill rules as a backtest.";
      $("mode-learn").disabled = !S || S.trades.length < 3;
      $("mode-resume").hidden = !S;
      R.reviewing = S || null;
    }
  });

  // ------------------------------------------------------------- wiring
  $("replay-btn").addEventListener("click", function () { if (R.active) return; if (R.picking) cancelPick(); else beginPick(); });
  $("rp-cancel").addEventListener("click", cancelPick);
  $("rp-go").addEventListener("click", function () { if ($("rp-date").value) startAt($("rp-date").value); });
  $("rp-random").addEventListener("click", function () {
    var d = G.state.meta.data[G.state.tf]; if (!d) return;
    var a = Date.parse(d.start + "T00:00:00Z") / 1000 + 60 * 864e2, b = Date.parse(d.end + "T00:00:00Z") / 1000 - 30 * 864e2;
    var t = Math.floor(a + Math.random() * Math.max(0, b - a));
    $("rp-date").value = new Date(t * 1000).toISOString().slice(0, 10); startAt(t);
  });
  $("rp-step").addEventListener("click", function () { step(); });
  $("rp-play").addEventListener("click", play);
  $("rp-speed").addEventListener("change", function () { if (R.timer) { pause(); play(); } });
  $("rp-buy").addEventListener("click", function () { openPos("long"); });
  $("rp-sell").addEventListener("click", function () { openPos("short"); });
  $("rp-close").addEventListener("click", function () { if (R.pos) { var j = R.cur, P = R.pos; closePos("Close", P.side > 0 ? R.bars.c[j] - slip() : R.bars.c[j] + spread(j) + slip(), j); refresh(); } });
  $("rp-position").addEventListener("submit", function (e) {
    e.preventDefault(); if (!R.pos) return;
    var sl = $("rp-pos-sl").value === "" ? null : round2(Number($("rp-pos-sl").value)), tp = $("rp-pos-tp").value === "" ? null : round2(Number($("rp-pos-tp").value));
    if (modify(sl, tp)) G.toast("Stop and target updated");
  });
  ["rp-lots", "rp-sl", "rp-tp"].forEach(function (id) { $(id).addEventListener("input", function () { if (R.active) refresh(); }); });
  $("rp-finish").addEventListener("click", function () { review(); });
  $("rp-exit").addEventListener("click", exit);
  $("rp-learn").addEventListener("click", function () { pause(); learnFrom([R.session]); });
  $("sessions-btn").addEventListener("click", openSessions);
  $("sessions-close").addEventListener("click", function () { $("sessions-dialog").close(); });
  $("sessions-import").addEventListener("change", function () { if (this.files[0]) importSession(this.files[0]); this.value = ""; });
  $("sessions-list").addEventListener("click", function (e) {
    var b = e.target.closest("button"); if (!b) return;
    if (b.dataset.learnTf) { $("sessions-dialog").close(); learnFrom(sessions().filter(function (S) { return S.timeframe === b.dataset.learnTf && S.trades.length; })); return; }
    var id = b.closest("tr").dataset.id, S = sessions().find(function (x) { return x.id === id; }); if (!S) return;
    var act = b.dataset.act;
    if (act === "delete") {
      if (!confirm("Delete “" + S.name + "”? Its " + S.trades.length + " trades will be gone.")) return;
      G.store.set("sessions", sessions().filter(function (x) { return x.id !== id; })); renderSessions(); return;
    }
    if (act === "export") { download(S.name.replace(/[^a-z0-9]+/gi, "_") + ".json", S); return; }
    $("sessions-dialog").close();
    if (act === "resume") { if (R.active) leave(); startAt(S.current_time, S); }
    else if (act === "review") review(S);
    else if (act === "learn") learnFrom([S]);
  });
  $("learn-close").addEventListener("click", function () { $("learn-dialog").close(); });
  $("learn-run").addEventListener("click", function () { loadLearned(false); });
  $("learn-save").addEventListener("click", function () { loadLearned(true); });
  $("mode-learn").addEventListener("click", function () { if (R.reviewing) learnFrom([R.reviewing]); });
  $("mode-resume").addEventListener("click", function () { var S = R.reviewing; if (S) startAt(S.current_time, S); });
  $("mode-back").addEventListener("click", function () { $("mode-note").hidden = true; G.runBacktest(); });
  document.addEventListener("keydown", function (e) {
    if (!R.active || document.querySelector("dialog[open]")) return;
    var el = document.activeElement, tag = (el && el.tagName) || "";
    if (/INPUT|TEXTAREA|SELECT/.test(tag) || (el && el.closest && el.closest(".tabs"))) return;
    if (e.key === "ArrowRight" && !e.altKey && !e.ctrlKey && !e.metaKey) { e.preventDefault(); step(); }
    else if (e.key === " " && tag !== "BUTTON" && tag !== "A") { e.preventDefault(); play(); }
    else if (e.shiftKey && (e.key === "B" || e.key === "b")) { e.preventDefault(); openPos("long"); }
    else if (e.shiftKey && (e.key === "S" || e.key === "s")) { e.preventDefault(); openPos("short"); }
    else if (e.shiftKey && (e.key === "C" || e.key === "c")) { e.preventDefault(); $("rp-close").click(); }
  });
  G.replay = { state: R, step: step, startAt: startAt, review: review, learnFrom: learnFrom, sessions: sessions, exit: exit, open: openPos,
    close: function () { $("rp-close").click(); }, modify: modify };
})();
