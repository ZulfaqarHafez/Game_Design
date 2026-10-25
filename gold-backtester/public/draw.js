/* Drawing tools on the price chart: trend line, ray, horizontal and vertical lines, rectangle, Fibonacci
   retracement, long/short position and text. Drawings are anchored to time and price, so they stay put
   when you change timeframe, and are saved in this browser. Also draws the draggable stop/target lines
   used by bar replay. Rendered with a Lightweight Charts series primitive. */
(function () {
  "use strict";
  var G = window.GSL, $ = function (id) { return document.getElementById(id); };
  if (!G || !G.price) return;
  var chartEl = $("chart");
  var TOOLS = {
    cursor: "Select", trend: "Trend line", ray: "Ray", hline: "Horizontal line", vline: "Vertical line",
    rect: "Rectangle", fib: "Fibonacci retracement", long: "Long position", short: "Short position", text: "Text",
  };
  var POINTS = { trend: 2, ray: 2, rect: 2, fib: 2, hline: 1, vline: 1, long: 1, short: 1, text: 1 };
  var COLORS = ["#3d7bd9", "#d0801f", "#1f7a52", "#b23a32", "#a65fc4", "#6b7380"];
  var DEFAULT_COLOR = { trend: "#3d7bd9", ray: "#3d7bd9", hline: "#d0801f", vline: "#6b7380", rect: "#a65fc4", fib: "#d0801f", long: "#1f7a52", short: "#b23a32", text: "#3d7bd9" };
  var FIB = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];

  var D = {
    items: G.store.get("drawings", []).filter(function (d) { return d && TOOLS[d.type] && Array.isArray(d.pts); }),
    tool: "cursor", pending: null, selected: null, drag: null, magnet: !!G.store.get("magnet", false), undo: [],
    orders: [], onOrderDrag: null, hoverPt: null,
  };
  var requestUpdate = function () {};
  function save() { G.store.set("drawings", D.items); }
  function snapshot() { D.undo.push(JSON.stringify(D.items)); if (D.undo.length > 60) D.undo.shift(); }
  function uid() { return "d" + Date.now().toString(36) + Math.floor(Math.random() * 1e5).toString(36); }

  // ------------------------------------------------------------- coordinates
  function ts() { return G.price.timeScale(); }
  function xOf(t) { var lg = G.timeToLogical(t); return lg === null ? null : ts().logicalToCoordinate(lg); }
  function yOf(p) { return G.candles.priceToCoordinate(p); }
  function paneBox() {
    var h = 0; try { h = G.price.panes()[0].getHeight(); } catch (e) { h = chartEl.clientHeight; }
    return { w: ts().width(), h: h };
  }
  function fromEvent(e) {
    var r = chartEl.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top, b = paneBox();
    if (x < 0 || y < 0 || x > b.w || y > b.h) return null;
    var lg = ts().coordinateToLogical(x); if (lg === null) return null;
    var i = Math.round(lg), t = G.logicalToTime(i), p = G.candles.coordinateToPrice(y);
    if (t === null || p === null) return null;
    if (D.magnet) {
      var bi = G.indexOfTime(t);
      if (bi !== null && bi >= 0) {
        var best = p, bd = 14;
        [G.bars.o[bi], G.bars.h[bi], G.bars.l[bi], G.bars.c[bi]].forEach(function (v) { var dy = Math.abs(yOf(v) - y); if (dy < bd) { bd = dy; best = v; } });
        p = best;
      }
    }
    return { x: x, y: y, t: t, p: p, i: i };
  }

  // ------------------------------------------------------------- geometry and hit testing
  function distSeg(px, py, x1, y1, x2, y2) {
    var dx = x2 - x1, dy = y2 - y1, len2 = dx * dx + dy * dy;
    var u = len2 ? Math.max(0, Math.min(1, ((px - x1) * dx + (py - y1) * dy) / len2)) : 0;
    var cx = x1 + u * dx, cy = y1 + u * dy;
    return Math.hypot(px - cx, py - cy);
  }
  function rayEnd(x1, y1, x2, y2, w) {
    if (x2 === x1) return [x2, y2];
    var k = (y2 - y1) / (x2 - x1), xe = x2 > x1 ? w : 0;
    return [xe, y1 + k * (xe - x1)];
  }
  function screen(d) {
    return d.pts.map(function (q) { return { x: q.t !== undefined ? xOf(q.t) : null, y: q.p !== undefined ? yOf(q.p) : null }; });
  }
  function handles(d) {
    var s = screen(d), b = paneBox();
    if (d.type === "hline") return s[0].y === null ? [] : [{ k: 0, x: b.w / 2, y: s[0].y }];
    if (d.type === "vline") return s[0].x === null ? [] : [{ k: 0, x: s[0].x, y: b.h / 2 }];
    if (d.type === "long" || d.type === "short") return s.map(function (q, k) { return { k: k, x: k === 0 ? q.x : s[1].x, y: q.y }; });
    if (d.type === "text") return [];
    return s.map(function (q, k) { return { k: k, x: q.x, y: q.y }; });
  }
  function hit(d, x, y, tol) {
    var s = screen(d), b = paneBox();
    var hs = handles(d);
    for (var k = 0; k < hs.length; k++) if (hs[k].x !== null && hs[k].y !== null && Math.hypot(x - hs[k].x, y - hs[k].y) <= tol + 2) return { part: "pt", k: hs[k].k };
    if (s.some(function (q, k) { return (d.type !== "vline" && q.y === null) || (d.type !== "hline" && q.x === null); })) return null;
    switch (d.type) {
      case "hline": return Math.abs(y - s[0].y) <= tol ? { part: "body" } : null;
      case "vline": return Math.abs(x - s[0].x) <= tol ? { part: "body" } : null;
      case "trend": return distSeg(x, y, s[0].x, s[0].y, s[1].x, s[1].y) <= tol ? { part: "body" } : null;
      case "ray": var e = rayEnd(s[0].x, s[0].y, s[1].x, s[1].y, b.w); return distSeg(x, y, s[0].x, s[0].y, e[0], e[1]) <= tol ? { part: "body" } : null;
      case "rect": case "fib": case "long": case "short":
        var xa = Math.min(s[0].x, s[1].x), xb = Math.max(s[0].x, s[1].x);
        var ys = s.map(function (q) { return q.y; }), ya = Math.min.apply(null, ys), yb = Math.max.apply(null, ys);
        return x >= xa - tol && x <= xb + tol && y >= ya - tol && y <= yb + tol ? { part: "body" } : null;
      case "text": var w = Math.max(30, (d.text || "").length * 7.2 + 12);
        return x >= s[0].x - 4 && x <= s[0].x + w && y >= s[0].y - 18 && y <= s[0].y + 6 ? { part: "body" } : null;
    }
    return null;
  }
  function hitOrder(x, y, tol) {
    for (var i = 0; i < D.orders.length; i++) {
      var o = D.orders[i]; if (!o.draggable) continue;
      var yy = yOf(o.price); if (yy !== null && Math.abs(y - yy) <= tol) return o;
    }
    return null;
  }
  function pick(x, y, tol) {
    var o = hitOrder(x, y, tol); if (o) return { order: o };
    for (var i = D.items.length - 1; i >= 0; i--) { var h = hit(D.items[i], x, y, tol); if (h) return { d: D.items[i], h: h }; }
    return null;
  }

  // ------------------------------------------------------------- rendering
  function alpha(hex, a) {
    var m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex || ""); if (!m) return hex;
    return "rgba(" + parseInt(m[1], 16) + "," + parseInt(m[2], 16) + "," + parseInt(m[3], 16) + "," + a + ")";
  }
  function inkFor(hex) {
    var m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex || ""); if (!m) return "#ffffff";
    var lum = [m[1], m[2], m[3]].map(function (h) { var v = parseInt(h, 16) / 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); });
    return 0.2126 * lum[0] + 0.7152 * lum[1] + 0.0722 * lum[2] > 0.3 ? "#11151b" : "#ffffff";
  }
  function label(ctx, text, x, y, color, bg, align) {
    ctx.font = "600 11px 'JetBrains Mono', monospace";
    var w = ctx.measureText(text).width + 10, xx = align === "right" ? x - w : x;
    ctx.fillStyle = bg; ctx.fillRect(xx, y - 9, w, 18);
    ctx.fillStyle = color; ctx.textBaseline = "middle"; ctx.fillText(text, xx + 5, y);
  }
  function fmt(p) { return G.num(p, 2); }
  function drawItem(ctx, d, b, sel) {
    var s = screen(d), c = d.color || DEFAULT_COLOR[d.type], lw = d.width || (d.type === "rect" ? 1 : 1.5);
    ctx.strokeStyle = c; ctx.lineWidth = sel ? lw + 0.75 : lw; ctx.setLineDash([]);
    var ink = G.tok("--ink"), panel = G.tok("--panel");
    function line(x1, y1, x2, y2) { ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke(); }
    switch (d.type) {
      case "trend": if (s[0].x === null || s[1].x === null) return; line(s[0].x, s[0].y, s[1].x, s[1].y); break;
      case "ray": if (s[0].x === null || s[1].x === null) return; var e = rayEnd(s[0].x, s[0].y, s[1].x, s[1].y, b.w); line(s[0].x, s[0].y, e[0], e[1]); break;
      case "hline": if (s[0].y === null) return; line(0, s[0].y, b.w, s[0].y); break;
      case "vline": if (s[0].x === null) return; line(s[0].x, 0, s[0].x, b.h); break;
      case "rect":
        if (s[0].x === null || s[1].x === null) return;
        ctx.fillStyle = alpha(c, 0.12); ctx.fillRect(Math.min(s[0].x, s[1].x), Math.min(s[0].y, s[1].y), Math.abs(s[1].x - s[0].x), Math.abs(s[1].y - s[0].y));
        ctx.strokeRect(Math.min(s[0].x, s[1].x), Math.min(s[0].y, s[1].y), Math.abs(s[1].x - s[0].x), Math.abs(s[1].y - s[0].y));
        break;
      case "fib":
        if (s[0].x === null || s[1].x === null) return;
        var xa = Math.min(s[0].x, s[1].x), xb = Math.max(s[0].x, s[1].x), p1 = d.pts[0].p, p2 = d.pts[1].p;
        ctx.setLineDash([4, 3]); line(s[0].x, s[0].y, s[1].x, s[1].y); ctx.setLineDash([]);
        FIB.forEach(function (lv) {
          var pr = p2 + (p1 - p2) * lv, y = yOf(pr); if (y === null) return;
          ctx.globalAlpha = lv === 0 || lv === 1 ? 1 : 0.8; line(xa, y, xb, y); ctx.globalAlpha = 1;
          label(ctx, lv + " (" + fmt(pr) + ")", xa, y - 10, c, alpha(panel, 0.85));
        });
        break;
      case "long": case "short":
        if (s[0].x === null || s[1].x === null) return;
        var x1 = s[0].x, x2 = s[1].x, ye = s[0].y, yt = s[1].y, ys = s[2].y, up = G.tok("--chart-up"), dn = G.tok("--chart-down");
        var entry = d.pts[0].p, tgt = d.pts[1].p, stop = d.pts[2].p, risk = Math.abs(entry - stop), rr = risk ? Math.abs(tgt - entry) / risk : 0;
        ctx.fillStyle = alpha(up, 0.16); ctx.fillRect(Math.min(x1, x2), Math.min(ye, yt), Math.abs(x2 - x1), Math.abs(yt - ye));
        ctx.fillStyle = alpha(dn, 0.16); ctx.fillRect(Math.min(x1, x2), Math.min(ye, ys), Math.abs(x2 - x1), Math.abs(ys - ye));
        ctx.strokeStyle = ink; ctx.lineWidth = 1; line(x1, ye, x2, ye);
        label(ctx, "Target " + fmt(tgt) + " (" + (d.type === "long" ? "+" : "−") + fmt(Math.abs(tgt - entry)) + ")", Math.min(x1, x2) + 2, yt + (yt < ye ? 11 : -11), ink, alpha(up, 0.28));
        label(ctx, "Stop " + fmt(stop) + " (" + fmt(risk) + ")", Math.min(x1, x2) + 2, ys + (ys < ye ? 11 : -11), ink, alpha(dn, 0.28));
        label(ctx, (d.type === "long" ? "Long" : "Short") + " " + fmt(entry) + " · R:R " + rr.toFixed(2), Math.min(x1, x2) + 2, ye + (d.type === "long" ? 11 : -11), ink, alpha(panel, 0.85));
        break;
      case "text":
        if (s[0].x === null || s[0].y === null) return;
        ctx.font = "600 13px Archivo, sans-serif"; ctx.textBaseline = "alphabetic";
        var tw = ctx.measureText(d.text || "").width;
        ctx.fillStyle = alpha(panel, 0.8); ctx.fillRect(s[0].x - 3, s[0].y - 15, tw + 8, 20);
        ctx.fillStyle = c; ctx.fillText(d.text || "", s[0].x + 1, s[0].y);
        if (sel) { ctx.strokeStyle = c; ctx.strokeRect(s[0].x - 3, s[0].y - 15, tw + 8, 20); }
        break;
    }
    if (sel) handles(d).forEach(function (h) {
      if (h.x === null || h.y === null) return;
      ctx.beginPath(); ctx.arc(h.x, h.y, 5, 0, Math.PI * 2); ctx.fillStyle = panel; ctx.fill(); ctx.strokeStyle = c; ctx.lineWidth = 2; ctx.stroke();
    });
  }
  function drawOrders(ctx, b) {
    D.orders.forEach(function (o) {
      var y = yOf(o.price); if (y === null) return;
      ctx.strokeStyle = o.color; ctx.lineWidth = 1.5; ctx.setLineDash(o.dash ? [6, 4] : []);
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(b.w, y); ctx.stroke(); ctx.setLineDash([]);
      label(ctx, o.label + (o.draggable ? "  ⇕" : ""), 8, y, inkFor(o.color), o.color);
    });
  }
  function render(ctx) {
    var b = paneBox();
    ctx.save();
    ctx.beginPath(); ctx.rect(0, 0, b.w, b.h); ctx.clip();
    D.items.forEach(function (d) { drawItem(ctx, d, b, D.selected === d.id); });
    if (D.pending) drawItem(ctx, D.pending, b, true);
    drawOrders(ctx, b);
    ctx.restore();
  }
  var renderer = { draw: function (target) { target.useMediaCoordinateSpace(function (scope) { render(scope.context); }); } };
  var paneView = { zOrder: function () { return "top"; }, renderer: function () { return renderer; } };
  function axisView(price, color, text) {
    return { coordinate: function () { var y = yOf(price); return y === null ? -100 : y; }, text: function () { return text || fmt(price); },
      textColor: function () { return inkFor(color); }, backColor: function () { return color; }, visible: function () { return true; }, tickVisible: function () { return true; } };
  }
  var primitive = {
    attached: function (p) { requestUpdate = p.requestUpdate; },
    detached: function () { requestUpdate = function () {}; },
    updateAllViews: function () {},
    paneViews: function () { return [paneView]; },
    priceAxisViews: function () {
      var v = [];
      D.items.forEach(function (d) { if (d.type === "hline") v.push(axisView(d.pts[0].p, d.color || DEFAULT_COLOR.hline)); });
      D.orders.forEach(function (o) { v.push(axisView(o.price, o.color)); });
      return v;
    },
  };
  G.candles.attachPrimitive(primitive);
  function redraw() { requestUpdate(); }

  // ------------------------------------------------------------- tools and selection
  function setTool(t) {
    D.tool = TOOLS[t] ? t : "cursor"; D.pending = null;
    document.querySelectorAll("#draw-rail button[data-tool]").forEach(function (b) { b.setAttribute("aria-pressed", b.dataset.tool === D.tool ? "true" : "false"); });
    var drawing = D.tool !== "cursor";
    G.price.applyOptions({ handleScroll: !drawing, handleScale: !drawing });
    chartEl.classList.toggle("dr-draw", drawing);
    if (drawing) { select(null); G.announce(TOOLS[D.tool] + ": " + (POINTS[D.tool] === 2 ? "click two points on the chart." : "click a point on the chart.")); }
    redraw();
  }
  function select(id) {
    D.selected = id;
    var d = D.items.find(function (x) { return x.id === id; });
    $("sel-tools").hidden = !d;
    if (d) {
      $("sel-name").textContent = TOOLS[d.type];
      $("sel-colors").innerHTML = COLORS.map(function (c) {
        return '<button type="button" class="swatch" data-color="' + c + '" style="background:' + c + '" aria-label="Colour ' + c + '" aria-pressed="' + ((d.color || DEFAULT_COLOR[d.type]) === c) + '"></button>';
      }).join("");
      $("sel-text").hidden = d.type !== "text";
    }
    redraw();
  }
  function selected() { return D.items.find(function (x) { return x.id === D.selected; }); }
  function removeSelected() {
    var d = selected(); if (!d) return;
    snapshot(); D.items = D.items.filter(function (x) { return x !== d; }); save(); select(null);
    G.announce(TOOLS[d.type] + " deleted.");
  }
  function atrAt(i) {
    if (!D._atr || D._atrFor !== G.bars) { D._atr = window.TA.atr(G.bars.h, G.bars.l, G.bars.c, 14); D._atrFor = G.bars; }
    var v = D._atr[Math.max(0, Math.min(i, D._atr.length - 1))];
    return v === v ? v : null;
  }
  function create(pt) {
    var type = D.tool, d = { id: uid(), type: type, color: DEFAULT_COLOR[type], pts: [] };
    if (type === "hline") d.pts = [{ p: pt.p }];
    else if (type === "vline") d.pts = [{ t: pt.t }];
    else if (type === "long" || type === "short") {
      var bi = G.indexOfTime(pt.t), a = atrAt(bi !== null && bi >= 0 ? bi : G.bars.t.length - 1) || Math.abs(pt.p) * 0.003;
      var dir = type === "long" ? 1 : -1, stop = pt.p - dir * 1.5 * a, tgt = pt.p + dir * 3 * a, t2 = G.logicalToTime(pt.i + 25);
      d.pts = [{ t: pt.t, p: pt.p }, { t: t2, p: tgt }, { t: t2, p: stop }];
    } else d.pts = [{ t: pt.t, p: pt.p }];
    return d;
  }
  function commit(d) {
    snapshot(); D.items.push(d); save(); D.pending = null;
    setTool("cursor"); select(d.id);
    G.announce(TOOLS[d.type] + " added. Drag its points to adjust; press Delete to remove it.");
  }
  function askText(cb, initial) {
    var dlg = $("text-dialog"); $("text-input").value = initial || "";
    D._textCb = cb; if (dlg.showModal) dlg.showModal(); else dlg.setAttribute("open", "");
    $("text-input").focus();
  }

  // ------------------------------------------------------------- pointer handling
  var touchTol = function (e) { return e.pointerType === "touch" ? 14 : 7; };
  function consume() { G.clickConsumedAt = Date.now(); }
  chartEl.addEventListener("pointerdown", function (e) {
    if (e.button !== undefined && e.button !== 0) return;
    var pt = fromEvent(e); if (!pt) return;
    if (D.tool !== "cursor") {
      consume(); e.preventDefault();
      if (POINTS[D.tool] === 2) {
        if (!D.pending) { D.pending = { id: uid(), type: D.tool, color: DEFAULT_COLOR[D.tool], pts: [{ t: pt.t, p: pt.p }, { t: pt.t, p: pt.p }] }; redraw(); }
        else { D.pending.pts[1] = { t: pt.t, p: pt.p }; if (D.pending.pts[0].t === pt.t && D.pending.pts[0].p === pt.p) return; commit(D.pending); }
      } else if (D.tool === "text") {
        var d0 = create(pt); askText(function (txt) { if (txt) { d0.text = txt.slice(0, 120); commit(d0); } else setTool("cursor"); });
      } else commit(create(pt));
      return;
    }
    var h = pick(pt.x, pt.y, touchTol(e));
    if (!h) { if (D.selected) select(null); return; }
    consume();
    G.price.applyOptions({ handleScroll: false, handleScale: false });
    if (h.order) { D.drag = { order: h.order, start: pt }; }
    else {
      select(h.d.id); snapshot();
      D.drag = { d: h.d, part: h.h.part, k: h.h.k, start: pt, orig: JSON.parse(JSON.stringify(h.d.pts)) };
    }
    try { chartEl.setPointerCapture(e.pointerId); } catch (err) { /* ignore */ }
    e.preventDefault(); e.stopPropagation();
  }, true);
  chartEl.addEventListener("pointermove", function (e) {
    var pt = fromEvent(e);
    if (D.drag && pt) {
      e.preventDefault();
      if (D.drag.order) { D.drag.order.price = pt.p; D.drag.order.moved = true; redraw(); return; }
      var d = D.drag.d, o = D.drag.orig, dt = pt.i - D.drag.start.i, dp = pt.p - D.drag.start.p;
      if (D.drag.part === "body") {
        d.pts = o.map(function (q) { var n = {}; if (q.t !== undefined) n.t = G.shiftTime(q.t, dt); if (q.p !== undefined) n.p = q.p + dp; return n; });
      } else {
        var k = D.drag.k;
        if (d.type === "long" || d.type === "short") {
          if (k === 0) d.pts = o.map(function (q) { return { t: G.shiftTime(q.t, dt), p: q.p + dp }; });
          else { d.pts[k] = { t: o[k].t, p: pt.p }; d.pts[1].t = d.pts[2].t = pt.t > d.pts[0].t ? pt.t : o[1].t; }
        } else if (d.type === "hline") d.pts[0] = { p: pt.p };
        else if (d.type === "vline") d.pts[0] = { t: pt.t };
        else d.pts[k] = { t: pt.t, p: pt.p };
      }
      redraw(); return;
    }
    if (D.pending && pt) { D.pending.pts[1] = { t: pt.t, p: pt.p }; redraw(); return; }
    if (D.tool === "cursor" && pt && e.pointerType !== "touch") {
      var h = pick(pt.x, pt.y, 7);
      chartEl.classList.toggle("dr-hover", !!h && !(h.h && h.h.part === "pt") && !h.order);
      chartEl.classList.toggle("dr-handle", !!h && ((h.h && h.h.part === "pt") || !!h.order));
    }
  }, true);
  function endDrag(e) {
    if (!D.drag) return;
    var drag = D.drag; D.drag = null;
    G.price.applyOptions({ handleScroll: D.tool === "cursor", handleScale: D.tool === "cursor" });
    try { chartEl.releasePointerCapture(e.pointerId); } catch (err) { /* ignore */ }
    consume();
    if (drag.order) { if (drag.order.moved && D.onOrderDrag) D.onOrderDrag(drag.order.key, drag.order.price); drag.order.moved = false; return; }
    if (JSON.stringify(drag.orig) === JSON.stringify(drag.d.pts)) D.undo.pop(); else save();
  }
  // The chart library pans on mouse/touch events, which follow the pointer events above. While a shape is
  // being dragged, or a drawing tool is active, keep those presses away from it so the chart doesn't move.
  ["mousedown", "touchstart", "mousemove", "touchmove"].forEach(function (type) {
    chartEl.addEventListener(type, function (e) {
      if (D.drag || (D.tool !== "cursor" && /down|start/.test(type))) e.stopPropagation();
    }, true);
  });
  chartEl.addEventListener("pointerup", endDrag, true);
  chartEl.addEventListener("pointercancel", endDrag, true);
  chartEl.addEventListener("dblclick", function (e) {
    var pt = fromEvent(e); if (!pt) return;
    var h = pick(pt.x, pt.y, 7); if (!h || !h.d || h.d.type !== "text") return;
    var d = h.d; askText(function (txt) { if (txt) { snapshot(); d.text = txt.slice(0, 120); save(); redraw(); } }, d.text);
  });
  G.price.timeScale().subscribeVisibleLogicalRangeChange(redraw);

  // ------------------------------------------------------------- toolbar wiring
  $("draw-rail").addEventListener("click", function (e) { var b = e.target.closest("button[data-tool]"); if (b) setTool(b.dataset.tool === D.tool && b.dataset.tool !== "cursor" ? "cursor" : b.dataset.tool); });
  $("magnet").setAttribute("aria-pressed", String(D.magnet));
  $("magnet").addEventListener("click", function () { D.magnet = !D.magnet; G.store.set("magnet", D.magnet); this.setAttribute("aria-pressed", String(D.magnet)); G.toast(D.magnet ? "Magnet on: points snap to open, high, low or close" : "Magnet off"); });
  $("undo-draw").addEventListener("click", function () { undo(); });
  $("clear-draw").addEventListener("click", function () {
    if (!D.items.length) { G.toast("No drawings to clear"); return; }
    snapshot(); D.items = []; save(); select(null); G.toast("All drawings cleared. Undo brings them back.");
  });
  $("sel-colors").addEventListener("click", function (e) {
    var b = e.target.closest("button[data-color]"), d = selected(); if (!b || !d) return;
    snapshot(); d.color = b.dataset.color; save(); select(d.id);
  });
  $("sel-delete").addEventListener("click", removeSelected);
  $("sel-text").addEventListener("click", function () { var d = selected(); if (d) askText(function (txt) { if (txt) { snapshot(); d.text = txt.slice(0, 120); save(); redraw(); } }, d.text); });
  $("text-form").addEventListener("submit", function (e) {
    e.preventDefault(); var cb = D._textCb; D._textCb = null; $("text-dialog").close(); if (cb) cb($("text-input").value.trim());
  });
  $("text-cancel").addEventListener("click", function () { var cb = D._textCb; D._textCb = null; $("text-dialog").close(); if (cb) cb(""); });
  if ($("draw-toggle")) $("draw-toggle").addEventListener("click", function () {
    var open = this.getAttribute("aria-expanded") !== "true";
    this.setAttribute("aria-expanded", String(open)); $("draw-rail").classList.toggle("open", open);
    if (!open) setTool("cursor");
  });
  function undo() {
    if (!D.undo.length) { G.toast("Nothing to undo"); return; }
    D.items = JSON.parse(D.undo.pop()); save(); select(null); G.toast("Undone");
  }
  document.addEventListener("keydown", function (e) {
    var tag = (document.activeElement && document.activeElement.tagName) || "";
    if (/INPUT|TEXTAREA|SELECT/.test(tag) || document.querySelector("dialog[open]")) return;
    if (e.key === "Escape" && (D.tool !== "cursor" || D.pending || D.selected)) { setTool("cursor"); select(null); }
    else if ((e.key === "Delete" || e.key === "Backspace") && D.selected) { e.preventDefault(); removeSelected(); }
    else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") { e.preventDefault(); undo(); }
  });
  G.on("bars", redraw); G.on("step", redraw);

  G.draw = {
    state: D, setTool: setTool, select: select, redraw: redraw, undo: undo, TOOLS: TOOLS,
    setOrderLines: function (lines, onDrag) { D.orders = lines || []; D.onOrderDrag = onDrag || null; redraw(); },
    list: function () { return D.items; },
  };
  setTool("cursor");
})();
