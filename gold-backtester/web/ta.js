/* Indicator maths for the chart. Each function mirrors goldlab/indicators.py (TradingView's ta.* formulas),
   so a line on the chart has the same value the backtester uses. Inputs and outputs are plain arrays;
   NaN marks bars where an indicator is still warming up. Works in the browser (window.TA) and in Node. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.TA = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";
  var N = NaN;
  function full(n) { var a = new Array(n); for (var i = 0; i < n; i++) a[i] = N; return a; }
  function isn(v) { return v !== v || v === null || v === undefined; }

  function sma(src, len) {
    var n = src.length, out = full(n), sum = 0, bad = 0;
    for (var i = 0; i < n; i++) {
      var v = src[i]; if (isn(v)) bad++; else sum += v;
      if (i >= len) { var o = src[i - len]; if (isn(o)) bad--; else sum -= o; }
      if (i >= len - 1 && bad === 0) {
        // re-sum each window to avoid drift; windows are short
        var s = 0; for (var k = i - len + 1; k <= i; k++) s += src[k];
        out[i] = s / len;
      }
    }
    return out;
  }
  // exponential smoothing seeded with the SMA of the first `len` values (Pine's ta.ema / ta.rma)
  function recursive(src, len, alpha) {
    var n = src.length, out = full(n), prev = N, win = [];
    for (var i = 0; i < n; i++) {
      var v = src[i];
      if (isn(prev)) {
        if (isn(v)) { win = []; continue; }
        win.push(v);
        if (win.length >= len) { var s = 0, w = win.slice(-len); for (var k = 0; k < w.length; k++) s += w[k]; prev = s / len; out[i] = prev; }
        continue;
      }
      if (!isn(v)) prev = alpha * v + (1 - alpha) * prev;
      out[i] = prev;
    }
    return out;
  }
  function ema(src, len) { return recursive(src, len, 2 / (len + 1)); }
  function rma(src, len) { return recursive(src, len, 1 / len); }
  function wma(src, len) {
    var n = src.length, out = full(n), wsum = len * (len + 1) / 2;
    for (var i = len - 1; i < n; i++) {
      var s = 0, ok = true;
      for (var k = 0; k < len; k++) { var v = src[i - len + 1 + k]; if (isn(v)) { ok = false; break; } s += v * (k + 1); }
      if (ok) out[i] = s / wsum;
    }
    return out;
  }
  function stdev(src, len) {
    var n = src.length, out = full(n);
    for (var i = len - 1; i < n; i++) {
      var s = 0, ok = true;
      for (var k = i - len + 1; k <= i; k++) { if (isn(src[k])) { ok = false; break; } s += src[k]; }
      if (!ok) continue;
      var m = s / len, q = 0;
      for (k = i - len + 1; k <= i; k++) q += (src[k] - m) * (src[k] - m);
      out[i] = Math.sqrt(q / len);
    }
    return out;
  }
  function roll(src, len, pick) {
    var n = src.length, out = full(n);
    for (var i = len - 1; i < n; i++) {
      var best = N, ok = true;
      for (var k = i - len + 1; k <= i; k++) { var v = src[k]; if (isn(v)) { ok = false; break; } if (isn(best) || pick(v, best)) best = v; }
      if (ok) out[i] = best;
    }
    return out;
  }
  function highest(src, len) { return roll(src, len, function (a, b) { return a > b; }); }
  function lowest(src, len) { return roll(src, len, function (a, b) { return a < b; }); }
  function tr(h, l, c) {
    var n = c.length, out = new Array(n);
    for (var i = 0; i < n; i++) {
      if (i === 0) { out[i] = h[0] - l[0]; continue; }
      var pc = c[i - 1];
      out[i] = Math.max(h[i] - l[i], Math.abs(h[i] - pc), Math.abs(l[i] - pc));
    }
    return out;
  }
  function atr(h, l, c, len) { return rma(tr(h, l, c), len || 14); }
  function diff(src) { var out = full(src.length); for (var i = 1; i < src.length; i++) out[i] = src[i] - src[i - 1]; return out; }
  function rsi(src, len) {
    len = len || 14;
    var d = diff(src), up = rma(d.map(function (x) { return isn(x) ? N : Math.max(x, 0); }), len),
      dn = rma(d.map(function (x) { return isn(x) ? N : Math.max(-x, 0); }), len), out = full(src.length);
    for (var i = 0; i < src.length; i++) {
      if (isn(up[i]) || isn(dn[i])) continue;
      out[i] = dn[i] === 0 ? 100 : up[i] === 0 ? 0 : 100 - 100 / (1 + up[i] / dn[i]);
    }
    return out;
  }
  function zip(a, b, f) { var out = new Array(a.length); for (var i = 0; i < a.length; i++) out[i] = isn(a[i]) || isn(b[i]) ? N : f(a[i], b[i]); return out; }
  function bb(src, len, mult) {
    var basis = sma(src, len), dev = stdev(src, len);
    return { basis: basis, upper: zip(basis, dev, function (b, d) { return b + mult * d; }), lower: zip(basis, dev, function (b, d) { return b - mult * d; }) };
  }
  function macd(src, fast, slow, signal) {
    var line = zip(ema(src, fast), ema(src, slow), function (a, b) { return a - b; });
    var sig = ema(line, signal);
    return { macd: line, signal: sig, hist: zip(line, sig, function (a, b) { return a - b; }) };
  }
  function stoch(c, h, l, len, smoothK, smoothD) {
    var hh = highest(h, len), ll = lowest(l, len), raw = full(c.length);
    for (var i = 0; i < c.length; i++) if (!isn(hh[i]) && !isn(ll[i])) raw[i] = 100 * (c[i] - ll[i]) / (hh[i] - ll[i]);
    var k = smoothK > 1 ? sma(raw, smoothK) : raw;
    return { k: k, d: sma(k, smoothD || 3) };
  }
  function cci(tp, len) {
    var m = sma(tp, len), out = full(tp.length);
    for (var i = len - 1; i < tp.length; i++) {
      var s = 0; for (var k = i - len + 1; k <= i; k++) s += tp[k];
      var mean = s / len, md = 0; for (k = i - len + 1; k <= i; k++) md += Math.abs(tp[k] - mean);
      md /= len; out[i] = (tp[i] - m[i]) / (0.015 * md);
    }
    return out;
  }
  function dmi(h, l, c, diLen, adxLen) {
    var n = c.length, pdm = new Array(n), mdm = new Array(n);
    for (var i = 0; i < n; i++) {
      if (i === 0) { pdm[i] = 0; mdm[i] = 0; continue; }
      var up = h[i] - h[i - 1], dn = -(l[i] - l[i - 1]);
      pdm[i] = up > dn && up > 0 ? up : 0; mdm[i] = dn > up && dn > 0 ? dn : 0;
    }
    var trur = rma(tr(h, l, c), diLen), p = rma(pdm, diLen), m = rma(mdm, diLen);
    var plus = zip(p, trur, function (a, b) { return 100 * a / b; }), minus = zip(m, trur, function (a, b) { return 100 * a / b; });
    var dx = new Array(n);
    for (i = 0; i < n; i++) {
      var s = plus[i] + minus[i];
      dx[i] = isn(plus[i]) || isn(minus[i]) || s === 0 ? 0 : Math.abs(plus[i] - minus[i]) / s;
    }
    var adx = rma(dx, adxLen).map(function (v) { return isn(v) ? N : 100 * v; });
    return { plus: plus, minus: minus, adx: adx };
  }
  function supertrend(h, l, c, factor, atrLen) {
    var a = atr(h, l, c, atrLen), n = c.length, upper = new Array(n), lower = new Array(n), st = full(n), dir = full(n);
    for (var i = 0; i < n; i++) { var hl2 = (h[i] + l[i]) / 2; upper[i] = hl2 + factor * a[i]; lower[i] = hl2 - factor * a[i]; }
    for (i = 0; i < n; i++) {
      if (isn(a[i])) continue;
      if (i > 0 && !isn(st[i - 1])) {
        lower[i] = (lower[i] > lower[i - 1] || c[i - 1] < lower[i - 1]) ? lower[i] : lower[i - 1];
        upper[i] = (upper[i] < upper[i - 1] || c[i - 1] > upper[i - 1]) ? upper[i] : upper[i - 1];
        if (st[i - 1] === upper[i - 1]) dir[i] = c[i] > upper[i] ? -1 : 1;
        else dir[i] = c[i] < lower[i] ? 1 : -1;
      } else dir[i] = 1;
      st[i] = dir[i] === -1 ? lower[i] : upper[i];
    }
    return { line: st, dir: dir };
  }
  function keltner(h, l, c, len, mult) {
    var basis = ema(c, len), rng = atr(h, l, c, len);
    return { basis: basis, upper: zip(basis, rng, function (b, r) { return b + mult * r; }), lower: zip(basis, rng, function (b, r) { return b - mult * r; }) };
  }
  function donchian(h, l, len) {
    var hi = highest(h, len), lo = lowest(l, len);
    return { upper: hi, lower: lo, mid: zip(hi, lo, function (a, b) { return (a + b) / 2; }) };
  }
  // trading day for the 17:00 New York roll: the New York date of (time + 7 hours)
  var nyFmt = null, offCache = {};
  function nyOffsetHours(t) {
    var key = Math.floor(t / 21600);    // the offset only changes at DST switches; cache per 6 hours
    if (offCache[key] !== undefined) return offCache[key];
    if (!nyFmt) nyFmt = new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
    var p = {}; nyFmt.formatToParts(new Date(t * 1000)).forEach(function (x) { p[x.type] = x.value; });
    var local = Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour % 24, +p.minute) / 1000;
    return (offCache[key] = Math.round((local - t) / 3600));
  }
  function nyDayKey(t) { return Math.floor((t + nyOffsetHours(t) * 3600 + 7 * 3600) / 86400); }
  function vwap(t, h, l, c, v) {
    var n = c.length, out = new Array(n), pv = 0, vv = 0, day = null;
    for (var i = 0; i < n; i++) {
      var k = nyDayKey(t[i]); if (k !== day) { day = k; pv = 0; vv = 0; }
      var tp = (h[i] + l[i] + c[i]) / 3, vol = isn(v[i]) ? 0 : v[i];
      pv += tp * vol; vv += vol;
      out[i] = vv === 0 ? tp : pv / vv;
    }
    return out;
  }
  function source(d, name) {
    var n = d.c.length, out = new Array(n);
    for (var i = 0; i < n; i++) {
      out[i] = name === "open" ? d.o[i] : name === "high" ? d.h[i] : name === "low" ? d.l[i] :
        name === "hl2" ? (d.h[i] + d.l[i]) / 2 : name === "hlc3" ? (d.h[i] + d.l[i] + d.c[i]) / 3 :
        name === "ohlc4" ? (d.o[i] + d.h[i] + d.l[i] + d.c[i]) / 4 : d.c[i];
    }
    return out;
  }
  return { sma: sma, ema: ema, rma: rma, wma: wma, stdev: stdev, highest: highest, lowest: lowest, tr: tr, atr: atr, rsi: rsi,
    bb: bb, macd: macd, stoch: stoch, cci: cci, dmi: dmi, supertrend: supertrend, keltner: keltner, donchian: donchian,
    vwap: vwap, nyDayKey: nyDayKey, source: source };
});
