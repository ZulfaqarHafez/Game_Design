/* Chart indicators: pick from a menu, edit inputs and colours, remove. Overlays draw on the price pane,
   oscillators get their own pane underneath. Values come from ta.js, which mirrors the Python engine. */
(function () {
  "use strict";
  var G = window.GSL, L = G.L, TA = window.TA, $ = function (id) { return document.getElementById(id); };
  if (!G || !TA || !G.price) return;

  var SOURCES = ["close", "open", "high", "low", "hl2", "hlc3", "ohlc4"];
  function len(def) { return { k: "length", label: "Length", def: def, min: 1, max: 1000, int: true }; }
  function src() { return { k: "source", label: "Source", def: "close", options: SOURCES }; }
  var DEFS = {
    sma: { name: "Simple moving average (SMA)", short: "SMA", inputs: [len(50), src()], lines: [["value", "Value", "#3d7bd9"]],
      calc: function (d, p) { return { value: TA.sma(TA.source(d, p.source), p.length) }; } },
    ema: { name: "Exponential moving average (EMA)", short: "EMA", inputs: [len(20), src()], lines: [["value", "Value", "#d0801f"]],
      calc: function (d, p) { return { value: TA.ema(TA.source(d, p.source), p.length) }; } },
    wma: { name: "Weighted moving average (WMA)", short: "WMA", inputs: [len(20), src()], lines: [["value", "Value", "#2f9e9e"]],
      calc: function (d, p) { return { value: TA.wma(TA.source(d, p.source), p.length) }; } },
    bb: { name: "Bollinger Bands", short: "BB", inputs: [len(20), { k: "mult", label: "Standard deviations", def: 2, min: 0.1, max: 10 }, src()],
      lines: [["upper", "Upper", "#7d6bd6"], ["basis", "Basis", "#c4842d"], ["lower", "Lower", "#7d6bd6"]],
      calc: function (d, p) { return TA.bb(TA.source(d, p.source), p.length, p.mult); } },
    kc: { name: "Keltner Channels", short: "KC", inputs: [len(20), { k: "mult", label: "ATR multiple", def: 1.5, min: 0.1, max: 10 }],
      lines: [["upper", "Upper", "#2f9e9e"], ["basis", "Basis", "#7d8a2a"], ["lower", "Lower", "#2f9e9e"]],
      calc: function (d, p) { return TA.keltner(d.h, d.l, d.c, p.length, p.mult); } },
    dc: { name: "Donchian Channels", short: "DC", inputs: [len(20)], lines: [["upper", "Upper", "#3d7bd9"], ["mid", "Middle", "#9aa3ad"], ["lower", "Lower", "#3d7bd9"]],
      calc: function (d, p) { return TA.donchian(d.h, d.l, p.length); } },
    vwap: { name: "VWAP (resets 17:00 New York)", short: "VWAP", inputs: [], lines: [["value", "VWAP", "#a65fc4"]],
      calc: function (d) { return { value: TA.vwap(d.t, d.h, d.l, d.c, d.v) }; } },
    st: { name: "Supertrend", short: "Supertrend", inputs: [{ k: "factor", label: "Factor", def: 3, min: 0.1, max: 20 }, { k: "atr", label: "ATR length", def: 10, min: 1, max: 500, int: true }],
      lines: [["line", "Line", "#1f7a52"]], dirColors: true,
      calc: function (d, p) { return TA.supertrend(d.h, d.l, d.c, p.factor, p.atr); } },
    rsi: { name: "Relative Strength Index (RSI)", short: "RSI", pane: true, inputs: [len(14), src()], lines: [["value", "RSI", "#a65fc4"]], levels: [30, 70],
      calc: function (d, p) { return { value: TA.rsi(TA.source(d, p.source), p.length) }; } },
    macd: { name: "MACD", short: "MACD", pane: true,
      inputs: [{ k: "fast", label: "Fast length", def: 12, min: 1, max: 500, int: true }, { k: "slow", label: "Slow length", def: 26, min: 1, max: 500, int: true },
        { k: "signal", label: "Signal length", def: 9, min: 1, max: 500, int: true }, src()],
      lines: [["hist", "Histogram", "#9aa3ad", "hist"], ["macd", "MACD", "#3d7bd9"], ["signal", "Signal", "#d0801f"]], levels: [0],
      calc: function (d, p) { return TA.macd(TA.source(d, p.source), p.fast, p.slow, p.signal); } },
    stoch: { name: "Stochastic", short: "Stoch", pane: true,
      inputs: [len(14), { k: "smoothK", label: "%K smoothing", def: 3, min: 1, max: 50, int: true }, { k: "smoothD", label: "%D smoothing", def: 3, min: 1, max: 50, int: true }],
      lines: [["k", "%K", "#3d7bd9"], ["d", "%D", "#d0801f"]], levels: [20, 80],
      calc: function (d, p) { return TA.stoch(d.c, d.h, d.l, p.length, p.smoothK, p.smoothD); } },
    atr: { name: "Average True Range (ATR)", short: "ATR", pane: true, inputs: [len(14)], lines: [["value", "ATR", "#b23a32"]],
      calc: function (d, p) { return { value: TA.atr(d.h, d.l, d.c, p.length) }; } },
    adx: { name: "ADX and DMI", short: "ADX", pane: true, inputs: [len(14)], lines: [["adx", "ADX", "#c4842d"], ["plus", "+DI", "#1f7a52"], ["minus", "−DI", "#b23a32"]], levels: [25],
      calc: function (d, p) { return TA.dmi(d.h, d.l, d.c, p.length, p.length); } },
    cci: { name: "Commodity Channel Index (CCI)", short: "CCI", pane: true, inputs: [len(20)], lines: [["value", "CCI", "#2f9e9e"]], levels: [-100, 100],
      calc: function (d, p) { var tp = d.c.map(function (_, i) { return (d.h[i] + d.l[i] + d.c[i]) / 3; }); return { value: TA.cci(tp, p.length) }; } },
    vol: { name: "Volume (tick volume)", short: "Volume", pane: true, inputs: [], lines: [["value", "Volume", "#9aa3ad", "hist"]], volume: true,
      calc: function (d) { return { value: d.v.slice() }; } },
  };
  var ORDER = ["ema", "sma", "wma", "bb", "kc", "dc", "vwap", "st", "rsi", "macd", "stoch", "atr", "adx", "cci", "vol"];

  var list = G.store.get("indicators", []).filter(function (x) { return DEFS[x.type]; });
  var live = {};          // id -> {series: {line: api}, values: {line: array}, levels: [priceLines]}
  var count = 0;          // bars currently shown (replay shows fewer than it has)

  function params(ind) {
    var p = {}; DEFS[ind.type].inputs.forEach(function (inp) { p[inp.k] = ind.inputs && ind.inputs[inp.k] !== undefined ? ind.inputs[inp.k] : inp.def; });
    return p;
  }
  function label(ind) {
    var d = DEFS[ind.type], p = params(ind);
    var bits = d.inputs.filter(function (i) { return i.k !== "source" || p.source !== "close"; }).map(function (i) { return p[i.k]; });
    return d.short + (bits.length ? " " + bits.join(" ") : "");
  }
  function save() { G.store.set("indicators", list); }
  function finite(v) { return v === v && v !== null && v !== undefined && isFinite(v); }
  function point(t, v, extra) { var o = { time: t, value: v }; if (extra) o.color = extra; return o; }

  function paneFor(ind) {
    if (!DEFS[ind.type].pane) return 0;
    var used = list.filter(function (x) { return DEFS[x.type].pane && x.visible !== false; });
    return 1 + used.indexOf(ind);
  }
  function destroy(id) {
    var l = live[id]; if (!l) return;
    Object.keys(l.series).forEach(function (k) { try { G.price.removeSeries(l.series[k]); } catch (e) { /* already gone */ } });
    delete live[id];
  }
  function colorAt(ind, d, key, i, vals) {
    var def = DEFS[ind.type];
    if (def.dirColors) return vals.dir[i] < 0 ? G.tok("--chart-up") : G.tok("--chart-down");
    if (def.volume) return G.bars.c[i] >= G.bars.o[i] ? "rgba(31,122,82,.45)" : "rgba(178,58,50,.45)";
    if (key === "hist" && ind.type === "macd") return vals.hist[i] >= 0 ? "rgba(31,122,82,.55)" : "rgba(178,58,50,.55)";
    return null;
  }
  function build(ind) {
    destroy(ind.id);
    if (ind.visible === false || !G.bars) return;
    var def = DEFS[ind.type], d = G.bars, p = params(ind), vals;
    try { vals = def.calc(d, p); } catch (e) { G.toast("Couldn't calculate " + def.short + ": " + e.message); return; }
    var pane = paneFor(ind), l = { series: {}, values: vals, levels: [] };
    def.lines.forEach(function (ln) {
      var key = ln[0], color = (ind.colors && ind.colors[key]) || ln[2];
      var opts = { color: color, priceLineVisible: false, lastValueVisible: !!def.pane, crosshairMarkerVisible: false, title: "" };
      var s = ln[3] === "hist" ? G.price.addSeries(L.HistogramSeries, opts, pane) : G.price.addSeries(L.LineSeries, Object.assign(opts, { lineWidth: 1.5 }), pane);
      l.series[key] = s;
    });
    if (def.levels) {
      var first = l.series[def.lines[def.lines.length - 1][0]];
      def.levels.forEach(function (lv) { l.levels.push(first.createPriceLine({ price: lv, color: G.tok("--muted"), lineWidth: 1, lineStyle: 2, axisLabelVisible: false })); });
    }
    live[ind.id] = l;
    fill(ind, count);
  }
  function fill(ind, n) {
    var l = live[ind.id]; if (!l) return;
    var def = DEFS[ind.type], d = G.bars;
    def.lines.forEach(function (ln) {
      var key = ln[0], arr = l.values[key], out = [];
      for (var i = 0; i < n && i < arr.length; i++) if (finite(arr[i])) out.push(point(d.t[i], arr[i], colorAt(ind, d, key, i, l.values)));
      l.series[key].setData(out);
    });
  }
  function layoutPanes() {
    var panes = G.price.panes();
    for (var i = 1; i < panes.length; i++) { try { panes[i].setHeight(110); } catch (e) { /* ignore */ } }
    G.setPanes(Math.max(0, panes.length - 1));
  }
  function rebuildAll() {
    Object.keys(live).forEach(destroy);
    list.forEach(build);
    layoutPanes();
    legend();
  }

  // ------------------------------------------------------------- legend (values follow the crosshair)
  var lastParam = null;
  function legend(param) {
    if (param !== undefined) lastParam = param;
    var box = $("ind-legend"); if (!box) return;
    var idx = null;
    if (lastParam && lastParam.time !== undefined && G.bars) idx = G.indexOfTime(lastParam.time);
    if (idx === null || idx < 0) idx = count - 1;
    box.innerHTML = list.map(function (ind) {
      var def = DEFS[ind.type], l = live[ind.id], vals = "";
      if (l && idx >= 0) vals = def.lines.map(function (ln) {
        var v = l.values[ln[0]][idx]; if (!finite(v)) return "";
        var c = (ind.colors && ind.colors[ln[0]]) || ln[2];
        return '<b style="color:' + c + '">' + G.num(v, Math.abs(v) >= 1000 ? 1 : 2) + "</b>";
      }).join(" ");
      return '<span class="ind-chip' + (ind.visible === false ? " off" : "") + '" data-id="' + ind.id + '"><span class="ind-name">' + G.esc(label(ind)) + "</span> " + vals +
        ' <button type="button" class="ind-act" data-act="settings" aria-label="Settings for ' + G.esc(label(ind)) + '">⚙</button>' +
        '<button type="button" class="ind-act" data-act="toggle" aria-pressed="' + (ind.visible !== false) + '" aria-label="' + (ind.visible === false ? "Show " : "Hide ") + G.esc(label(ind)) + '">' + (ind.visible === false ? "◌" : "◉") + "</button>" +
        '<button type="button" class="ind-act" data-act="remove" aria-label="Remove ' + G.esc(label(ind)) + '">✕</button></span>';
    }).join("");
  }

  // ------------------------------------------------------------- add / edit / remove
  function add(type) {
    var ind = { id: "i" + Date.now().toString(36) + Math.floor(Math.random() * 1e4), type: type, inputs: {}, colors: {}, visible: true };
    list.push(ind); save(); build(ind); layoutPanes(); legend();
    G.announce(DEFS[type].name + " added to the chart.");
    return ind;
  }
  function remove(id) {
    list = list.filter(function (x) { return x.id !== id; }); save();
    destroy(id); rebuildAll();
  }
  function renderMenu() {
    var q = ($("ind-search").value || "").toLowerCase();
    $("ind-list").innerHTML = ORDER.filter(function (k) { return !q || (DEFS[k].name + " " + DEFS[k].short).toLowerCase().indexOf(q) >= 0; }).map(function (k) {
      return '<button type="button" class="ind-pick" data-type="' + k + '"><span>' + G.esc(DEFS[k].name) + '</span><small>' + (DEFS[k].pane ? "own pane" : "on price") + "</small></button>";
    }).join("") || '<p class="hint">No indicator matches that search.</p>';
    $("ind-active").innerHTML = list.length ? list.map(function (ind) {
      return '<div class="ind-row"><span>' + G.esc(label(ind)) + '</span><button type="button" class="btn small ghost" data-act="settings" data-id="' + ind.id + '">Settings</button><button type="button" class="btn small ghost" data-act="remove" data-id="' + ind.id + '">Remove</button></div>';
    }).join("") : '<p class="hint">None yet.</p>';
  }
  var editing = null;
  function openSettings(id) {
    var ind = list.find(function (x) { return x.id === id; }); if (!ind) return;
    editing = ind;
    var def = DEFS[ind.type], p = params(ind);
    $("ind-set-title").textContent = def.name;
    $("ind-set-fields").innerHTML = def.inputs.map(function (inp) {
      if (inp.options) return '<label>' + inp.label + '<select data-k="' + inp.k + '">' + inp.options.map(function (o) { return '<option' + (o === p[inp.k] ? " selected" : "") + ">" + o + "</option>"; }).join("") + "</select></label>";
      return '<label>' + inp.label + '<input type="number" data-k="' + inp.k + '" value="' + p[inp.k] + '" min="' + inp.min + '" max="' + inp.max + '" step="' + (inp.int ? 1 : 0.1) + '" inputmode="decimal"></label>';
    }).join("") + def.lines.map(function (ln) {
      return '<label>' + G.esc(ln[1]) + ' colour<input type="color" data-color="' + ln[0] + '" value="' + ((ind.colors && ind.colors[ln[0]]) || ln[2]) + '"></label>';
    }).join("");
    $("ind-set-error").textContent = "";
    var dlg = $("ind-settings"); if (dlg.showModal) dlg.showModal(); else dlg.setAttribute("open", "");
  }
  function applySettings() {
    var ind = editing; if (!ind) return false;
    var def = DEFS[ind.type], next = {}, err = "";
    def.inputs.forEach(function (inp) {
      var el = $("ind-set-fields").querySelector('[data-k="' + inp.k + '"]'); if (!el) return;
      if (inp.options) { next[inp.k] = el.value; return; }
      var v = Number(el.value);
      if (!isFinite(v) || v < inp.min || v > inp.max) err = inp.label + " must be between " + inp.min + " and " + inp.max + ".";
      next[inp.k] = inp.int ? Math.round(v) : v;
    });
    if (err) { $("ind-set-error").textContent = err; return false; }
    ind.inputs = next; ind.colors = ind.colors || {};
    $("ind-set-fields").querySelectorAll("[data-color]").forEach(function (el) { ind.colors[el.dataset.color] = el.value; });
    save(); rebuildAll();
    return true;
  }

  // ------------------------------------------------------------- data hooks
  G.on("bars", function (n) { count = typeof n === "number" ? n : (G.bars ? G.bars.t.length : 0); rebuildAll(); });
  G.on("step", function (n) {
    // replay: one more bar is visible
    count = n;
    list.forEach(function (ind) {
      var l = live[ind.id]; if (!l) return;
      var def = DEFS[ind.type], i = n - 1;
      def.lines.forEach(function (ln) {
        var v = l.values[ln[0]][i];
        if (finite(v)) l.series[ln[0]].update(point(G.bars.t[i], v, colorAt(ind, G.bars, ln[0], i, l.values)));
      });
    });
    legend(null);
  });
  G.on("visible", function (n) { count = n; list.forEach(function (ind) { fill(ind, n); }); legend(null); });
  G.price.subscribeCrosshairMove(function (p) { legend(p && p.time !== undefined ? p : null); });
  G.indicators = { add: add, remove: remove, list: function () { return list; }, live: live, DEFS: DEFS, openSettings: openSettings };

  // ------------------------------------------------------------- wiring
  $("ind-btn").addEventListener("click", function () {
    $("ind-search").value = ""; renderMenu();
    var d = $("ind-dialog"); if (d.showModal) d.showModal(); else d.setAttribute("open", "");
    $("ind-search").focus();
  });
  $("ind-close").addEventListener("click", function () { $("ind-dialog").close(); });
  $("ind-search").addEventListener("input", renderMenu);
  $("ind-list").addEventListener("click", function (e) {
    var b = e.target.closest("button[data-type]"); if (!b) return;
    add(b.dataset.type); renderMenu(); G.toast(DEFS[b.dataset.type].short + " added");
  });
  $("ind-active").addEventListener("click", function (e) {
    var b = e.target.closest("button[data-act]"); if (!b) return;
    if (b.dataset.act === "remove") { remove(b.dataset.id); renderMenu(); }
    else { $("ind-dialog").close(); openSettings(b.dataset.id); }
  });
  $("ind-legend").addEventListener("click", function (e) {
    var b = e.target.closest("button[data-act]"); if (!b) return;
    var id = b.closest("[data-id]").dataset.id, ind = list.find(function (x) { return x.id === id; }); if (!ind) return;
    if (b.dataset.act === "remove") remove(id);
    else if (b.dataset.act === "toggle") { ind.visible = ind.visible === false; save(); rebuildAll(); }
    else openSettings(id);
  });
  $("ind-set-form").addEventListener("submit", function (e) { e.preventDefault(); if (applySettings()) $("ind-settings").close(); });
  $("ind-set-cancel").addEventListener("click", function () { $("ind-settings").close(); });
  $("ind-set-defaults").addEventListener("click", function () {
    if (!editing) return; editing.inputs = {}; editing.colors = {}; save(); rebuildAll(); $("ind-settings").close();
  });
})();
