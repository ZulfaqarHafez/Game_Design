#!/usr/bin/env node
/* End-to-end tests for the Gold Strategy Lab website.

   node tests/e2e/run.cjs                       # starts `python -m goldlab serve` on public/ and tests it
   BASE=https://gold-strategy-lab-eight.vercel.app/ node tests/e2e/run.cjs   # test the live site
   ONLY=mobile,a11y node tests/e2e/run.cjs      # run tests whose name contains one of these words

   Needs Node 18+ and Playwright's Chromium (preinstalled in Claude Code cloud sessions; elsewhere:
   npm i -D playwright && npx playwright install chromium). axe-core is loaded from jsDelivr.
*/
"use strict";
const { chromium } = require("playwright");
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");
const http = require("http");

const ROOT = path.resolve(__dirname, "..", "..");
const AXE = "https://cdn.jsdelivr.net/npm/axe-core@4.10.2/axe.min.js";
let BASE = process.env.BASE || "";
const ONLY = (process.env.ONLY || "").split(",").filter(Boolean);
const results = [];
let browser, server;

// ------------------------------------------------------------------ tiny test harness
const tests = [];
function test(name, fn, opts) { tests.push({ name, fn, opts: opts || {} }); }
function assert(cond, msg) { if (!cond) throw new Error(msg); }
function eq(a, b, msg) { if (a !== b) throw new Error(`${msg}: expected ${JSON.stringify(b)}, got ${JSON.stringify(a)}`); }

async function newPage(opts) {
  opts = opts || {};
  const ctx = await browser.newContext({
    viewport: opts.viewport || { width: 1366, height: 900 }, colorScheme: opts.dark ? "dark" : "light",
    isMobile: !!opts.mobile, hasTouch: !!opts.mobile, acceptDownloads: true, reducedMotion: "reduce",
    serviceWorkers: opts.sw ? "allow" : "block",     // the worker is tested on its own; elsewhere requests must stay interceptable
  });
  const page = await ctx.newPage();
  page.errors = [];
  page.on("pageerror", e => page.errors.push("pageerror: " + e.message));
  page.on("console", m => {
    if (m.type() !== "error") return;
    const t = m.text();
    if (/status of 400|status of 500|Failed to load resource|net::ERR_FAILED/.test(t)) return;   // expected in error tests
    page.errors.push("console: " + t);
  });
  page.ctx = ctx;
  return page;
}
async function close(page) { const errs = page.errors; await page.ctx.close(); if (errs.length) throw new Error("Browser errors: " + errs.join(" | ")); }
async function settled(page, timeout) {
  await page.waitForFunction(() => window.__gsl && document.getElementById("busy").hidden &&
    (window.__gsl.result || !document.getElementById("banner").hidden), null, { timeout: timeout || 45000 });
}
async function open(page, hash) {
  await page.goto(BASE + (hash ? "#" + hash : ""), { waitUntil: "domcontentloaded" });
  await settled(page);
}
async function afterChange(page) { await page.waitForTimeout(750); await settled(page); }
const R = page => page.evaluate(() => window.__gsl.result);
async function axe(page, label) {
  await page.addScriptTag({ url: AXE });
  const v = await page.evaluate(async () => (await window.axe.run(document, { runOnly: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"] })).violations
    .map(x => ({ id: x.id, impact: x.impact, n: x.nodes.length, where: x.nodes.slice(0, 3).map(n => n.target.join(" ")).join(" | ") })));
  const bad = v.filter(x => x.impact === "serious" || x.impact === "critical");
  const minor = v.filter(x => !(x.impact === "serious" || x.impact === "critical"));
  if (minor.length) console.log(`      (${label}) minor axe notes: ` + minor.map(x => `${x.id}x${x.n}`).join(", "));
  assert(!bad.length, `${label}: axe serious/critical: ` + bad.map(x => `${x.id} x${x.n} [${x.where}]`).join("; "));
}
async function noHorizontalScroll(page, label) {
  const [sw, w] = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
  assert(sw <= w + 1, `${label}: page scrolls sideways (${sw} > ${w})`);
}

// ------------------------------------------------------------------ tests
test("boot: page loads, shows a strategy and results", async () => {
  const p = await newPage();
  await open(p);
  eq(await p.title(), "Gold Strategy Lab", "title");
  assert(await p.$("h1"), "has an h1");
  const opts = await p.$$eval("#strategy option", o => o.length);
  assert(opts >= 7, `at least 7 strategies in the picker (got ${opts})`);
  eq(await p.$$eval("#kpis .kpi", k => k.length), 8, "8 stat tiles");
  assert(/O .* H .* L .* C/.test(await p.textContent("#legend")), "chart legend shows OHLC");
  assert(/bars/.test(await p.textContent("#chart-note")), "chart note shows bar count");
  assert((await p.locator("#chart canvas").count()) > 0, "chart canvas drawn");
  assert(await p.isHidden("#overlay"), "loading overlay hidden after load");
  await close(p);
});

test("strategies: every strategy runs without errors", async () => {
  const p = await newPage();
  await open(p);
  const ids = await p.$$eval("#strategy option", o => o.map(x => x.value));
  for (const id of ids) {
    await p.selectOption("#strategy", id);
    await afterChange(p);
    assert(await p.isHidden("#banner"), `${id}: no error banner (${await p.textContent("#banner")})`);
    const r = await R(p);
    assert(r && r.candles.length > 50, `${id}: candles returned`);
    assert(/\$/.test(await p.textContent("#kpis .kpi .v")), `${id}: net profit shown`);
    eq(await p.evaluate(() => decodeURIComponent(location.hash.slice(1))), id, `${id}: URL hash follows the strategy`);
  }
  await close(p);
});

test("timeframes: each timeframe button runs and is marked pressed", async () => {
  const p = await newPage();
  await open(p, "ema_trend_4h");
  const tfs = await p.$$eval("#tf button", b => b.map(x => x.dataset.tf));
  assert(tfs.length >= 5, "at least 5 timeframes");
  for (const tf of tfs) {
    await p.click(`#tf button[data-tf="${tf}"]`);
    await afterChange(p);
    eq((await R(p)).data.timeframe, tf, "result timeframe");
    eq(await p.getAttribute(`#tf button[data-tf="${tf}"]`, "aria-pressed"), "true", `${tf} pressed`);
    assert(await p.isHidden("#banner"), `${tf}: no error`);
  }
  await close(p);
});

test("date range: chips and custom dates change the tested period", async () => {
  const p = await newPage();
  await open(p, "rsi2_mean_reversion_1h");
  await p.click('#range button[data-days="90"]'); await afterChange(p);
  let r = await R(p);
  const span = (Date.parse(r.data.end) - Date.parse(r.data.start)) / 864e5;
  assert(span > 80 && span < 95, `3M covers about 90 days (got ${span.toFixed(1)})`);
  await p.click('#range button[data-days="0"]'); await afterChange(p);
  r = await R(p);
  assert((Date.parse(r.data.end) - Date.parse(r.data.start)) / 864e5 > 2000, "All covers the full history");
  await p.fill("#start", "2025-01-01"); await p.fill("#end", "2025-06-30"); await p.dispatchEvent("#end", "change");
  await afterChange(p);
  r = await R(p);
  assert(r.data.start >= "2025-01-01" && r.data.end < "2025-07-01", `custom dates respected (${r.data.start} → ${r.data.end})`);
  eq(await p.$$eval('#range button[aria-pressed="true"]', b => b.length), 0, "no range chip pressed for custom dates");
  await p.fill("#start", "2025-06-30"); await p.fill("#end", "2025-01-01"); await p.dispatchEvent("#end", "change");
  await p.waitForTimeout(900);
  assert(/start date is after the end date/.test(await p.textContent("#banner")), "inverted dates explained");
  await close(p);
});

test("cost model: TradingView preset removes costs and locks cost fields", async () => {
  const p = await newPage();
  await open(p, "ema_trend_4h");
  await p.click('#preset button[data-preset="tradingview"]'); await afterChange(p);
  let r = await R(p);
  eq(r.settings.spread_mode, "none", "no spread"); eq(r.settings.commission_value, 0, "no commission");
  eq(r.metrics.commission_paid, 0, "commission paid is 0");
  assert(await p.isDisabled("#p-comm"), "commission field locked");
  assert(await p.isVisible("#tv-note") || await p.evaluate(() => !document.getElementById("tv-note").hidden), "explains why fields are locked");
  await p.click('#preset button[data-preset="realistic"]'); await afterChange(p);
  r = await R(p);
  eq(r.settings.spread_mode, "data", "spread back on");
  assert(!(await p.isDisabled("#p-comm")), "commission editable again");
  await close(p);
});

test("inputs: plain-language labels, changes rerun, reset restores", async () => {
  const p = await newPage();
  await open(p, "ema_trend_4h");
  const labels = await p.$$eval("#inputs label", l => l.map(x => x.childNodes[0].textContent.trim()));
  assert(labels.every(t => !/_/.test(t)), "no code names in labels: " + labels.join(", "));
  assert(labels.includes("Fast EMA length (bars)"), "card label used");
  await p.fill('#inputs input[data-param="fast"]', "30"); await afterChange(p);
  eq((await R(p)).strategy.params.fast, 30, "new input used");
  await p.click("#reset-inputs"); await afterChange(p);
  eq((await R(p)).strategy.params.fast, 50, "reset to default");
  eq(await p.inputValue('#inputs input[data-param="fast"]'), "50", "field reset");
  await close(p);
});

test("account settings: capital, sizing type and fixed spread", async () => {
  const p = await newPage();
  await open(p, "ema_trend_4h");
  await p.fill("#p-capital", "50000"); await p.dispatchEvent("#p-capital", "change"); await afterChange(p);
  eq((await R(p)).settings.initial_capital, 50000, "account size applied");
  await p.selectOption("#p-qtytype", "lots"); await afterChange(p);
  assert(/Lots/.test(await p.textContent("#p-qtyvalue-label")), "size label follows sizing type");
  eq((await R(p)).settings.qty_type, "lots", "sizing type applied");
  assert(await p.isHidden("#p-spreadfixed-wrap"), "fixed spread hidden by default");
  await p.selectOption("#p-spread", "fixed"); await afterChange(p);
  assert(await p.isVisible("#p-spreadfixed-wrap"), "fixed spread field shown");
  eq((await R(p)).settings.spread_mode, "fixed", "fixed spread applied");
  await close(p);
});

test("tabs: click and keyboard (arrows, Home, End) switch panels", async () => {
  const p = await newPage();
  await open(p, "ema_trend_4h");
  const tabs = ["overview", "outlook", "performance", "analysis", "trades", "monthly", "checks", "properties", "compare"];
  for (const t of tabs) {
    if (t === "outlook") continue;                       // its content loads from the network; covered by its own test
    await p.click(`.tabs button[data-tab="${t}"]`);
    for (const u of tabs) eq(await p.isVisible(`#tab-${u}`), u === t, `${t} selected: ${u} visibility`);
    eq(await p.getAttribute(`.tabs button[data-tab="${t}"]`, "aria-selected"), "true", `${t} aria-selected`);
  }
  await p.focus('.tabs button[data-tab="compare"]');
  await p.keyboard.press("Home"); eq(await p.evaluate(() => document.activeElement.dataset.tab), "overview", "Home");
  await p.keyboard.press("ArrowRight"); eq(await p.evaluate(() => document.activeElement.dataset.tab), "outlook", "ArrowRight");
  await p.keyboard.press("ArrowRight"); eq(await p.evaluate(() => document.activeElement.dataset.tab), "performance", "ArrowRight again");
  assert(await p.isVisible("#tab-performance"), "panel follows keyboard");
  await p.keyboard.press("End"); eq(await p.evaluate(() => document.activeElement.dataset.tab), "compare", "End");
  await p.keyboard.press("ArrowRight"); eq(await p.evaluate(() => document.activeElement.dataset.tab), "overview", "wraps around");
  eq(await p.$$eval('.tabs button[tabindex="0"]', b => b.length), 1, "one tab stop (roving tabindex)");
  await close(p);
});

test("numbers agree: performance table, stat tiles and trade list", async () => {
  const p = await newPage();
  await open(p, "donchian_breakout_4h");
  const r = await R(p);
  eq(r.sides.all.trades, r.sides.long.trades + r.sides.short.trades, "long + short = all");
  assert(Math.abs(r.sides.all.net_profit - r.metrics.net_profit) < 0.01, "side table net = headline net");
  const sum = r.trades.reduce((a, t) => a + t.pnl, 0);
  assert(Math.abs(sum - r.metrics.net_profit) < 0.05, `sum of trades = net profit (${sum} vs ${r.metrics.net_profit})`);
  const tile = await p.textContent("#kpis .kpi .v");
  eq(tile, "$" + Math.round(r.metrics.net_profit).toLocaleString("en-US"), "net profit tile");
  await p.click('.tabs button[data-tab="trades"]');
  eq(await p.$$eval("#trades tbody tr[data-n]", x => x.length), Math.min(r.trades.length, 1500), "every trade listed");
  await close(p);
});

test("trades: filters, select a trade, next/previous, keyboard Enter", async () => {
  const p = await newPage();
  await open(p, "donchian_breakout_4h");
  await p.click('.tabs button[data-tab="trades"]');
  const all = await p.$$eval("#trades tbody tr[data-n]", x => x.length);
  await p.click('#trade-filter button[data-f="long"]');
  const sides = await p.$$eval("#trades tbody tr[data-n] .side", x => x.map(e => e.textContent));
  assert(sides.length && sides.every(s => s === "long"), "long filter");
  await p.click('#trade-filter button[data-f="short"]');
  const shorts = await p.$$eval("#trades tbody tr[data-n]", x => x.length);
  eq(sides.length + shorts, all, "long + short rows = all rows");
  await p.click('#trade-filter button[data-f="win"]');
  const wins = await p.$$eval('#trades tbody tr[data-n] td[data-label="P&L $"]', x => x.map(e => parseFloat(e.textContent.replace(/,/g, ""))));
  assert(wins.every(v => v > 0), "wins filter shows only winners");
  await p.click('#trade-filter button[data-f="all"]');
  const first = p.locator("#trades tbody tr[data-n]").nth(3);
  const n = Number(await first.getAttribute("data-n"));
  await first.click();
  assert(await p.isVisible("#trade-nav"), "trade navigator shown");
  assert((await p.textContent("#trade-nav-label")).startsWith("#" + n), "navigator shows the trade");
  eq(await p.evaluate(() => window.__gsl.selected), n, "trade selected");
  await p.click("#next-trade"); eq(await p.evaluate(() => window.__gsl.selected), n + 1, "next trade");
  await p.click("#prev-trade"); eq(await p.evaluate(() => window.__gsl.selected), n, "previous trade");
  await p.click("#close-trade"); assert(await p.isHidden("#trade-nav"), "navigator closes");
  await p.locator("#trades tbody tr[data-n]").nth(5).focus(); await p.keyboard.press("Enter");
  assert(await p.isVisible("#trade-nav"), "Enter on a row selects it");
  await close(p);
});

test("monthly: selecting a month lists that month's trades", async () => {
  const p = await newPage();
  await open(p, "donchian_breakout_4h");
  const r = await R(p);
  const month = new Date(r.trades[r.trades.length - 3].entry_time * 1000).toISOString().slice(0, 7);
  const expected = r.trades.filter(t => new Date(t.entry_time * 1000).toISOString().slice(0, 7) === month).length;
  await p.click('.tabs button[data-tab="monthly"]');
  await p.click(`#tab-monthly td[data-month="${month}"]`);
  assert(await p.isVisible("#tab-trades"), "jumps to Trades");
  assert((await p.textContent("#extra-filter")).includes(month), "filter chip names the month");
  eq(await p.$$eval("#trades tbody tr[data-n]", x => x.length), expected, "rows for that month");
  await p.click("#clear-extra");
  assert(await p.isHidden("#extra-filter"), "filter cleared");
  await close(p);
});

test("analysis: R histogram, sessions, heatmap filter, time zone remembered", async () => {
  const p = await newPage();
  await open(p, "ema_trend_4h");
  await p.click('.tabs button[data-tab="analysis"]');
  eq(await p.$$eval("#r-hist .bar-row", x => x.length), 10, "10 R buckets");
  eq(await p.$$eval("#sessions tbody tr", x => x.length), 3, "3 sessions");
  const r = await R(p);
  const sessTotal = await p.$$eval("#sessions tbody tr td:nth-of-type(1)", x => x.reduce((a, e) => a + Number(e.textContent), 0));
  eq(sessTotal, r.trades.length, "sessions add up to all trades");
  const cell = p.locator("#heat td[data-wd]").first();
  const cnt = Number((await cell.locator('[aria-hidden="true"]').textContent()).trim());
  await cell.click();
  eq(await p.$$eval("#trades tbody tr[data-n]", x => x.length), cnt, "heatmap cell count = listed trades");
  await p.click('.tabs button[data-tab="analysis"]');
  await p.selectOption("#tz", "America/New_York");
  await p.reload({ waitUntil: "domcontentloaded" }); await settled(p);
  eq(await p.inputValue("#tz"), "America/New_York", "time zone remembered after reload");
  await close(p);
});

test("equity chart: buy & hold toggle is remembered", async () => {
  const p = await newPage();
  await open(p, "tsmom_daily");
  assert(await p.isHidden("#bh-key"), "buy & hold off by default");
  await p.check("#bh-toggle");
  assert(await p.isVisible("#bh-key"), "buy & hold shown");
  await p.reload({ waitUntil: "domcontentloaded" }); await settled(p);
  assert(await p.isChecked("#bh-toggle"), "toggle remembered");
  assert((await p.locator("#equity canvas").count()) > 0, "equity chart drawn");
  await close(p);
});

test("properties: run details match the request", async () => {
  const p = await newPage();
  await open(p, "london_breakout_15m");
  await p.click('.tabs button[data-tab="properties"]');
  const text = await p.textContent("#tab-properties");
  const r = await R(p);
  assert(text.includes(r.strategy.name) && text.includes(r.strategy.fingerprint), "strategy and rules version");
  assert(text.includes("Target (R multiple)"), "inputs use plain labels");
  assert(text.includes("Account size") && text.includes("Spread"), "broker settings listed");
  await close(p);
});

test("checklist: runs on the server and shows a verdict", async () => {
  const p = await newPage();
  await open(p, "tsmom_daily");
  await p.click('.tabs button[data-tab="checks"]');
  await p.click("#run-checks");
  await p.waitForSelector("#checks .verdict, #checks .error-box", { timeout: 90000 });
  assert(await p.$("#checks .verdict"), "verdict shown: " + await p.textContent("#checks"));
  assert((await p.$$eval("#checks tbody tr", x => x.length)) >= 10, "at least 10 checks");
  await close(p);
}, { slow: true });

test("compare: every run is recorded and history can be cleared", async () => {
  const p = await newPage();
  await open(p, "ema_trend_4h");
  await p.click('#tf button[data-tf="1d"]'); await afterChange(p);
  await p.click('.tabs button[data-tab="compare"]');
  assert((await p.$$eval("#compare tbody tr", x => x.length)) >= 2, "runs listed");
  await p.click("#clear-history");
  assert(/No runs yet/.test(await p.textContent("#compare")), "history cleared");
  await close(p);
});

test("rules editor: error feedback, custom run, save and reload", async () => {
  const p = await newPage();
  await open(p, "ema_trend_4h");
  await p.click("#rules-block summary");
  await p.fill("#yaml", "name: Broken\nlong:\n  when: close[-1] > close\n");
  await p.click("#apply-yaml"); await afterChange(p);
  assert(/future/.test(await p.textContent("#banner")), "explains the error");
  eq(await p.getAttribute("#yaml", "aria-invalid"), "true", "editor marked invalid");
  assert(await p.evaluate(() => document.getElementById("results").classList.contains("stale")), "old results marked stale");
  const card = "name: E2E crossover\ntimeframe: 4h\nparams: {fast: 20, slow: 80}\nlabels: {fast: Fast line, slow: Slow line}\n" +
    "long:\n  when: crossover(ema(close, fast), ema(close, slow))\n  sl_dist: 2 * atr(14)\n  tp_r: 2\nsettings: {qty_type: lots, qty_value: 0.1}\n";
  await p.fill("#yaml", card);
  await p.click("#apply-yaml"); await afterChange(p);
  assert(await p.isHidden("#banner"), "custom rules ran: " + await p.textContent("#banner"));
  eq((await R(p)).strategy.name, "E2E crossover", "results are for the custom rules");
  await p.click("#save-yaml"); await afterChange(p);
  await p.waitForFunction(() => /Saved as/.test(document.getElementById("yaml-status").textContent));
  eq(await p.inputValue("#strategy"), "saved:e2e-crossover", "saved strategy selected");
  await p.reload({ waitUntil: "domcontentloaded" }); await settled(p);
  assert(await p.$('#strategy optgroup[label="Saved in this browser"] option[value="saved:e2e-crossover"]'), "saved strategy survives reload");
  await p.selectOption("#strategy", "saved:e2e-crossover"); await afterChange(p);
  eq((await R(p)).strategy.name, "E2E crossover", "saved strategy runs");
  const labels = await p.$$eval("#inputs label", l => l.map(x => x.childNodes[0].textContent.trim()));
  assert(labels.includes("Fast line"), "saved labels used");
  await close(p);
});

test("pine export: dialog shows code, Escape closes and returns focus", async () => {
  const p = await newPage();
  await open(p, "london_breakout_15m");
  await p.click("#rules-block summary");
  await p.click("#pine-btn");
  await p.waitForFunction(() => document.getElementById("pine-dialog").open);
  const code = await p.textContent("#pine-code");
  assert(code.includes("//@version=6") && code.includes("strategy(") && code.includes("strategy.entry("), "valid-looking Pine");
  await p.keyboard.press("Escape");
  assert(!(await p.evaluate(() => document.getElementById("pine-dialog").open)), "Escape closes");
  eq(await p.evaluate(() => document.activeElement.id), "pine-btn", "focus returns to the button");
  await close(p);
});

test("CSV export: downloads every trade", async () => {
  const p = await newPage();
  await open(p, "ema_trend_4h");
  await p.click('.tabs button[data-tab="trades"]');
  const [dl] = await Promise.all([p.waitForEvent("download"), p.click("#csv")]);
  assert(/\.csv$/.test(dl.suggestedFilename()), "csv filename");
  const text = fs.readFileSync(await dl.path(), "utf8").trim().split("\n");
  eq(text[0].split(",")[0], "n", "header");
  eq(text.length - 1, (await R(p)).trades.length, "one line per trade");
  await close(p);
});

test("links: URL #strategy switches strategy without reload", async () => {
  const p = await newPage();
  await open(p, "ema_trend_4h");
  await p.evaluate(() => { location.hash = "#tsmom_daily"; });
  await afterChange(p);
  eq((await R(p)).strategy.name.startsWith("Time-series momentum"), true, "strategy switched");
  eq(await p.inputValue("#strategy"), "tsmom_daily", "picker follows");
  await close(p);
});

test("errors: server failure keeps previous results, marked stale", async () => {
  const p = await newPage();
  await open(p, "ema_trend_4h");
  await p.route("**/api/lab?op=backtest", r => r.fulfill({ status: 500, contentType: "application/json", body: '{"error":"Simulated outage"}' }));
  await p.click("#run"); await settled(p);
  assert(/previous run.*Simulated outage/.test(await p.textContent("#banner")), "banner explains");
  assert(await p.evaluate(() => document.getElementById("results").classList.contains("stale")), "results dimmed");
  await p.unroute("**/api/lab?op=backtest");
  await p.route("**/api/lab?op=backtest", r => r.abort());
  await p.click("#run"); await settled(p);
  assert(/Can't reach the backtest server/.test(await p.textContent("#banner")), "offline message");
  await p.unroute("**/api/lab?op=backtest");
  await p.click("#run"); await settled(p);
  assert(await p.isHidden("#banner"), "recovers on the next good run");
  await close(p);
});

test("errors: first load failure shows a clear message", async () => {
  const p = await newPage();
  await p.route("**/api/lab?op=strategies", r => r.fulfill({ status: 503, body: "Service Unavailable" }));
  await p.goto(BASE, { waitUntil: "domcontentloaded" });
  await p.waitForFunction(() => !document.getElementById("banner").hidden, null, { timeout: 15000 });
  assert(/unexpected response \(503\)/.test(await p.textContent("#banner")), "explains the failure");
  assert(await p.isVisible("#overlay"), "chart shows the failure");
  await close(p);
});

test("empty state: a strategy that never trades explains what to do", async () => {
  const p = await newPage();
  await open(p, "ema_trend_4h");
  await p.click("#rules-block summary");
  await p.fill("#yaml", "name: Never\nlong:\n  when: close < 0\n  sl_dist: 5\n");
  await p.click("#apply-yaml"); await afterChange(p);
  assert(await p.isVisible("#empty"), "empty state visible");
  assert(/No closed trades/.test(await p.textContent("#empty")), "empty state text");
  await p.click('.tabs button[data-tab="analysis"]');
  await p.click('.tabs button[data-tab="trades"]');
  assert(/No trades match/.test(await p.textContent("#trades")), "trade list empty message");
  await close(p);
});

test("skipped signals: notice explains them and one tap trades the minimum lot", async () => {
  const p = await newPage();
  await open(p, "ema_trend_4h");
  const before = (await R(p)).metrics;
  assert(before.rejected_orders > 0, "default EMA run has skipped signals (1% risk on $10k is under 0.01 lot at today's gold price)");
  assert(await p.isVisible("#skip-note"), "notice visible");
  const text = await p.textContent("#skip-note");
  assert(/signals? (was|were) skipped/.test(text) && /Last trade closed \d{1,2} [A-Z][a-z]{2,3} \d{4}/.test(text), "notice says what happened and when: " + text);
  await p.click("#use-min-lot"); await afterChange(p);
  const after = await R(p);
  eq(after.settings.qty_type, "lots", "sizing switched to lots"); eq(after.settings.qty_value, 0.01, "0.01 lot");
  eq(after.metrics.rejected_orders, 0, "nothing skipped at the minimum lot");
  assert(after.metrics.total_trades > before.total_trades, "more trades once nothing is skipped");
  assert(!(await p.isVisible("#skip-note")), "notice hidden after the fix");
  eq(await p.inputValue("#p-qtytype"), "lots", "Settings shows the new sizing");
  await close(p);
});

test("mobile: no sideways scroll, result strip, 44px targets", async () => {
  for (const w of [320, 390, 768]) {
    const p = await newPage({ viewport: { width: w, height: 844 }, mobile: true });
    await open(p, "london_breakout_15m");
    await noHorizontalScroll(p, `${w}px`);
    assert(await p.isVisible("#summary"), `${w}px: result strip visible`);
    eq(await p.$$eval("#summary .v", x => x.length), 4, `${w}px: 4 headline numbers`);
    const small = await p.evaluate(() => {
      const sel = ".toolbar button, .tabs button, #run, #open-settings, #trade-filter button";
      return [...document.querySelectorAll(sel)].filter(e => {
        const r = e.getBoundingClientRect(); return r.width && (r.height < 44 || r.width < 44);
      }).map(e => `${e.textContent.trim()} ${Math.round(e.getBoundingClientRect().width)}x${Math.round(e.getBoundingClientRect().height)}`);
    });
    assert(!small.length, `${w}px: targets under 44px: ${small.join(", ")}`);
    const fs16 = await p.evaluate(() => [...document.querySelectorAll("input, select, textarea")].every(e => parseFloat(getComputedStyle(e).fontSize) >= 16));
    assert(fs16, `${w}px: form fields are 16px (no iOS zoom)`);
    await close(p);
  }
});

test("mobile: settings sheet opens, traps focus, closes with Escape", async () => {
  const p = await newPage({ viewport: { width: 390, height: 844 }, mobile: true });
  await open(p, "ema_trend_4h");
  assert(!(await p.isVisible("#panel")), "sheet hidden at first");
  const reachable = await p.evaluate(() => { const el = document.getElementById("p-capital"); el.focus(); return document.activeElement === el; });
  assert(!reachable, "fields in the closed sheet can't take focus");
  await p.click("#open-settings"); await p.waitForTimeout(400);
  assert(await p.isVisible("#panel"), "sheet open");
  eq(await p.evaluate(() => document.activeElement.id), "close-settings", "focus moves into the sheet");
  eq(await p.getAttribute("#open-settings", "aria-expanded"), "true", "button reports expanded");
  assert(await p.evaluate(() => document.querySelector(".chart-area").inert), "page behind is inert");
  await p.fill('#inputs input[data-param="fast"]', "40"); await afterChange(p);
  eq((await R(p)).strategy.params.fast, 40, "edits in the sheet rerun the backtest");
  await p.keyboard.press("Escape"); await p.waitForTimeout(400);
  assert(!(await p.isVisible("#panel")), "Escape closes the sheet");
  eq(await p.evaluate(() => document.activeElement.id), "open-settings", "focus returns to Settings");
  await p.click("#open-settings"); await p.waitForTimeout(400);
  await p.click("#backdrop", { position: { x: 20, y: 20 } }); await p.waitForTimeout(400);
  assert(!(await p.isVisible("#panel")), "tapping outside closes the sheet");
  await close(p);
});

test("mobile: trade cards and navigator", async () => {
  const p = await newPage({ viewport: { width: 390, height: 844 }, mobile: true });
  await open(p, "donchian_breakout_4h");
  await p.click('.tabs button[data-tab="trades"]');
  const disp = await p.$eval("#trades tbody tr[data-n]", e => getComputedStyle(e).display);
  eq(disp, "grid", "trades shown as cards");
  await p.locator("#trades tbody tr[data-n]").first().tap();
  assert(await p.isVisible("#trade-nav"), "navigator visible on phone");
  await noHorizontalScroll(p, "trades tab");
  await close(p);
});

test("dark mode: renders without overflow and passes axe", async () => {
  for (const mobile of [false, true]) {
    const p = await newPage({ dark: true, mobile, viewport: mobile ? { width: 390, height: 844 } : undefined });
    await open(p, "tsmom_daily");
    await noHorizontalScroll(p, "dark");
    const bg = await p.evaluate(() => getComputedStyle(document.body).backgroundColor);
    eq(bg, "rgb(15, 19, 24)", "dark background");
    await axe(p, mobile ? "dark phone" : "dark desktop");
    await close(p);
  }
});

test("a11y: axe scan of every view has no serious or critical issues", async () => {
  const p = await newPage();
  await open(p, "ema_trend_4h");
  await axe(p, "overview");
  for (const t of ["performance", "analysis", "trades", "monthly", "properties", "compare"]) {
    await p.click(`.tabs button[data-tab="${t}"]`); await axe(p, t);
  }
  await p.click("#rules-block summary"); await p.click("#pine-btn");
  await p.waitForFunction(() => document.getElementById("pine-dialog").open);
  await axe(p, "pine dialog");
  await close(p);
  const m = await newPage({ viewport: { width: 390, height: 844 }, mobile: true });
  await open(m, "ema_trend_4h");
  await axe(m, "phone");
  await m.click("#open-settings"); await m.waitForTimeout(400);
  await axe(m, "phone settings sheet");
  await close(m);
});

test("a11y: keyboard reaches every control in a sensible order", async () => {
  const p = await newPage();
  await open(p, "ema_trend_4h");
  await p.keyboard.press("Tab");
  eq(await p.evaluate(() => document.activeElement.className), "skip", "skip link first");
  await p.keyboard.press("Enter");
  eq(await p.evaluate(() => document.activeElement.id), "results", "skip link jumps to results");
  const seen = new Set();
  await p.focus("#strategy");
  for (let i = 0; i < 120; i++) { await p.keyboard.press("Tab"); seen.add(await p.evaluate(() => document.activeElement.id || document.activeElement.dataset.tf || document.activeElement.dataset.tab || document.activeElement.tagName)); }
  for (const want of ["run", "4h", "start", "p-capital", "t-overview"]) assert(seen.has(want), `Tab reaches ${want}`);
  await close(p);
});

test("pages: library, research and every strategy report load", async () => {
  const p = await newPage();
  await p.goto(BASE + "library.html", { waitUntil: "domcontentloaded" });
  const links = await p.$$eval('a[href^="strategies/"]', a => a.map(x => x.getAttribute("href")));
  assert(links.length >= 7, "library lists strategies");
  assert(await p.$('a[href="./"]'), "library links back to the backtester");
  await axe(p, "library");
  for (const href of links) {
    const resp = await p.goto(BASE + href, { waitUntil: "domcontentloaded" });
    eq(resp.status(), 200, href);
    assert(await p.$("a.back"), `${href}: back link`);
    await p.waitForSelector("#price canvas", { timeout: 15000 });
  }
  await axe(p, "strategy report");
  const resp = await p.goto(BASE + "research.html", { waitUntil: "domcontentloaded" });
  eq(resp.status(), 200, "research page");
  assert((await p.textContent("h1")).length > 10, "research has a title");
  await axe(p, "research");
  await close(p);
});

test("api: contract, errors and speed", async () => {
  const p = await newPage();
  await p.goto(BASE + "library.html");
  const out = await p.evaluate(async () => {
    const post = (op, body) => fetch("/api/lab?op=" + op, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
      .then(async r => ({ status: r.status, body: await r.json() }));
    const res = {};
    res.list = await fetch("/api/lab?op=strategies").then(r => r.status);
    res.bad = await post("backtest", { strategy: "nope" });
    res.badParam = await post("backtest", { strategy: "ema_trend_4h", params: { fast: "x" } });
    res.unsafe = await post("backtest", { card: "name: x\nlong:\n  when: __import__('os')\n" });
    res.unknownOp = await post("hack", {});
    res.getBacktest = await fetch("/api/lab?op=backtest").then(r => r.status);
    const times = [];
    for (const s of ["ema_trend_4h", "tsmom_daily", "london_breakout_15m"]) {
      const t0 = performance.now(); const r = await post("backtest", { strategy: s }); times.push([s, r.status, Math.round(performance.now() - t0)]);
    }
    res.times = times;
    res.pine = (await post("pine", { strategy: "ema_trend_4h" })).status;
    return res;
  });
  eq(out.list, 200, "strategies endpoint");
  eq(out.bad.status, 400, "unknown strategy is a 400"); assert(/Unknown strategy/.test(out.bad.body.error), "error message");
  eq(out.badParam.status, 400, "bad parameter is a 400");
  eq(out.unsafe.status, 400, "unsafe expression refused");
  eq(out.unknownOp.status, 404, "unknown operation is a 404");
  assert(out.getBacktest === 405, "backtest needs POST (got " + out.getBacktest + ")");
  eq(out.pine, 200, "pine endpoint");
  for (const [s, st, ms] of out.times) { eq(st, 200, s); assert(ms < 8000, `${s} took ${ms} ms`); }
  console.log("      timings: " + out.times.map(t => `${t[0]} ${t[2]}ms`).join(", "));
  await close(p);
});

// ------------------------------------------------------------------ chart tools: indicators, drawings, bar replay
const { execFileSync } = require("child_process");
function pyReference() {
  const script = `
import json
from goldlab.webapi import _data
from goldlab import indicators as ta
d = _data("1h").iloc[:3000]
o, h, l, c, v = d.open, d.high, d.low, d.close, d.volume
L = lambda s: [None if x != x else float(x) for x in s.to_numpy(float)]
st, sd = ta.supertrend(h, l, c, 3, 10)
print(json.dumps({"t": [int(x) for x in d.index.as_unit("s").asi8], "o": L(o), "h": L(h), "l": L(l), "c": L(c), "v": L(v),
  "ema": L(ta.ema(c, 20)), "sma": L(ta.sma(c, 50)), "wma": L(ta.wma(c, 20)), "rsi": L(ta.rsi(c, 14)), "atr": L(ta.atr(h, l, c, 14)),
  "bbu": L(ta.bb(c, 20, 2)[1]), "bbl": L(ta.bb(c, 20, 2)[2]), "macd": L(ta.macd(c, 12, 26, 9)[0]), "macds": L(ta.macd(c, 12, 26, 9)[1]),
  "stoch": L(ta.sma(ta.stoch(c, h, l, 14), 3)), "adx": L(ta.adx(h, l, c, 14)), "pdi": L(ta.dmi(h, l, c, 14, 14)[0]),
  "cci": L(ta.cci((h + l + c) / 3, 20)), "st": L(st), "sd": L(sd), "kcu": L(ta.keltner(h, l, c, 20, 1.5)[1]),
  "dch": L(ta.highest(h, 20)), "vwap": L(ta.vwap(h, l, c, v))}))
`;
  return JSON.parse(execFileSync("python3", ["-c", script], { cwd: ROOT, maxBuffer: 64 << 20 }).toString());
}

test("indicators: chart maths matches the Python engine (14 indicators)", async () => {
  const TA = require(path.join(ROOT, "web", "ta.js"));
  const ref = pyReference(), d = { t: ref.t, o: ref.o, h: ref.h, l: ref.l, c: ref.c, v: ref.v };
  const st = TA.supertrend(d.h, d.l, d.c, 3, 10), dmi = TA.dmi(d.h, d.l, d.c, 14, 14), mac = TA.macd(d.c, 12, 26, 9);
  const mine = { ema: TA.ema(d.c, 20), sma: TA.sma(d.c, 50), wma: TA.wma(d.c, 20), rsi: TA.rsi(d.c, 14), atr: TA.atr(d.h, d.l, d.c, 14),
    bbu: TA.bb(d.c, 20, 2).upper, bbl: TA.bb(d.c, 20, 2).lower, macd: mac.macd, macds: mac.signal, stoch: TA.stoch(d.c, d.h, d.l, 14, 3, 3).k,
    adx: dmi.adx, pdi: dmi.plus, cci: TA.cci(d.c.map((x, i) => (d.h[i] + d.l[i] + x) / 3), 20), st: st.line, sd: st.dir,
    kcu: TA.keltner(d.h, d.l, d.c, 20, 1.5).upper, dch: TA.donchian(d.h, d.l, 20).upper, vwap: TA.vwap(d.t, d.h, d.l, d.c, d.v) };
  const report = [];
  for (const k of Object.keys(mine)) {
    let worst = 0, nanMismatch = 0;
    for (let i = 0; i < ref.t.length; i++) {
      const a = ref[k][i], b = mine[k][i], bn = b !== b || b === null || b === undefined;
      if (a === null || bn) { if ((a === null) !== bn) nanMismatch++; continue; }
      worst = Math.max(worst, Math.abs(a - b) / Math.max(1, Math.abs(a)));
    }
    if (worst > 1e-9 || nanMismatch) report.push(`${k}: worst rel diff ${worst.toExponential(2)}, warm-up mismatch on ${nanMismatch} bars`);
  }
  assert(!report.length, "indicators differ from Python: " + report.join("; "));
});

test("indicators: add, change settings, hide, remove, panes, saved after reload", async () => {
  const p = await newPage();
  await open(p, "ema_trend_4h");
  await p.click("#ind-btn");
  assert(await p.evaluate(() => document.getElementById("ind-dialog").open), "menu opens");
  await p.fill("#ind-search", "relative");
  eq(await p.$$eval("#ind-list button", b => b.map(x => x.dataset.type).join()), "rsi", "search narrows the list");
  await p.click('#ind-list button[data-type="rsi"]');
  await p.fill("#ind-search", "");
  await p.click('#ind-list button[data-type="ema"]'); await p.click('#ind-list button[data-type="bb"]'); await p.click('#ind-list button[data-type="macd"]');
  await p.click("#ind-close");
  eq(await p.evaluate(() => GSL.price.panes().length), 3, "price pane + RSI pane + MACD pane");
  const ema = await p.evaluate(() => {
    const ind = GSL.indicators.list().find(x => x.type === "ema"), l = GSL.indicators.live[ind.id];
    const ref = TA.ema(GSL.bars.c, 20), n = GSL.bars.c.length;
    return { id: ind.id, last: l.values.value[n - 1], ref: ref[n - 1], points: l.series.value.data().length, finite: ref.filter(x => x === x).length };
  });
  eq(ema.last, ema.ref, "EMA value matches ta.js"); eq(ema.points, ema.finite, "one point per bar after warm-up");
  assert(/EMA 20/.test(await p.textContent("#ind-legend")) && /RSI 14/.test(await p.textContent("#ind-legend")), "legend lists indicators with values");
  // settings: EMA 20 -> 50
  await p.click(`#ind-legend [data-id="${ema.id}"] button[data-act="settings"]`);
  await p.fill('#ind-set-fields input[data-k="length"]', "0"); await p.click('#ind-set-form button[type="submit"]');
  assert(/between 1 and 1000/.test(await p.textContent("#ind-set-error")), "out-of-range length is refused");
  await p.fill('#ind-set-fields input[data-k="length"]', "50"); await p.click('#ind-set-form button[type="submit"]');
  assert(/EMA 50/.test(await p.textContent("#ind-legend")), "legend shows the new length");
  eq(await p.evaluate(id => { const n = GSL.bars.c.length; return GSL.indicators.live[id].values.value[n - 1] === TA.ema(GSL.bars.c, 50)[n - 1]; }, ema.id), true, "values recomputed");
  // hide and remove
  await p.click(`#ind-legend [data-id="${ema.id}"] button[data-act="toggle"]`);
  eq(await p.evaluate(id => !GSL.indicators.live[id], ema.id), true, "hidden indicator has no series");
  const rsiId = await p.evaluate(() => GSL.indicators.list().find(x => x.type === "rsi").id);
  await p.click(`#ind-legend [data-id="${rsiId}"] button[data-act="remove"]`);
  eq(await p.evaluate(() => GSL.price.panes().length), 2, "removing RSI removes its pane");
  await p.reload(); await settled(p);
  const after = await p.evaluate(() => GSL.indicators.list().map(x => x.type + (x.visible === false ? "-off" : "")).join());
  eq(after, "ema-off,bb,macd", "indicators are remembered");
  assert(/EMA 50/.test(await p.textContent("#ind-legend")), "settings are remembered");
  await close(p);
});

async function chartPoint(p, t, price) {
  return p.evaluate(([t, price]) => {
    const r = document.getElementById("chart").getBoundingClientRect();
    return { x: r.left + GSL.price.timeScale().logicalToCoordinate(GSL.timeToLogical(t)), y: r.top + GSL.candles.priceToCoordinate(price) };
  }, [t, price]);
}
async function barAt(p, frac) {
  return p.evaluate(frac => {
    const r = GSL.price.timeScale().getVisibleLogicalRange(), i = Math.round(r.from + (r.to - r.from) * frac);
    return { t: GSL.bars.t[i], c: GSL.bars.c[i], i: i };
  }, frac);
}

test("drawings: every tool draws; select, drag, recolour, delete, undo; saved and kept across timeframes", async () => {
  const p = await newPage({ viewport: { width: 1440, height: 950 } });
  await open(p, "ema_trend_4h");
  const box = await p.locator("#chart").boundingBox();
  const at = (fx, fy) => [box.x + box.width * fx, box.y + box.height * fy];
  const plan = [["trend", [0.30, 0.45], [0.45, 0.30]], ["ray", [0.30, 0.70], [0.40, 0.60]], ["rect", [0.50, 0.40], [0.60, 0.55]],
    ["fib", [0.15, 0.80], [0.25, 0.45]], ["hline", [0.40, 0.50]], ["vline", [0.70, 0.50]], ["long", [0.62, 0.50]], ["short", [0.75, 0.40]], ["text", [0.55, 0.75]]];
  for (const [tool, a, b] of plan) {
    await p.click(`#draw-rail button[data-tool="${tool}"]`);
    eq(await p.getAttribute(`#draw-rail button[data-tool="${tool}"]`, "aria-pressed"), "true", tool + " button pressed");
    await p.mouse.click(...at(...a));
    if (b) { await p.mouse.move(...at(...b), { steps: 3 }); await p.mouse.click(...at(...b)); }
    if (tool === "text") { await p.fill("#text-input", "Breakout zone"); await p.click('#text-form button[type="submit"]'); }
    eq(await p.evaluate(() => GSL.draw.state.tool), "cursor", tool + ": back to the select tool after drawing");
  }
  const types = await p.evaluate(() => GSL.draw.list().map(d => d.type).join());
  eq(types, plan.map(x => x[0]).join(), "one drawing per tool");
  eq(await p.evaluate(() => GSL.draw.list().find(d => d.type === "text").text), "Breakout zone", "text saved");
  // the long position defaults to a 1.5 ATR stop and a 2R target
  const lp = await p.evaluate(() => { const d = GSL.draw.list().find(x => x.type === "long"); return [d.pts[0].p, d.pts[1].p, d.pts[2].p]; });
  assert(lp[1] > lp[0] && lp[2] < lp[0] && Math.abs((lp[1] - lp[0]) / (lp[0] - lp[2]) - 2) < 1e-6, "long position: target above, stop below, 2R");
  // drag the trend line's end point
  const tr = await p.evaluate(() => GSL.draw.list().find(d => d.type === "trend").pts[1]);
  const from = await chartPoint(p, tr.t, tr.p);
  await p.mouse.move(from.x, from.y); await p.mouse.down(); await p.mouse.move(from.x + 60, from.y + 40, { steps: 6 }); await p.mouse.up();
  const moved = await p.evaluate(() => GSL.draw.list().find(d => d.type === "trend").pts[1]);
  assert(moved.t > tr.t && moved.p < tr.p, "dragging the handle moves the end point");
  const range = await p.evaluate(() => GSL.price.timeScale().getVisibleLogicalRange());
  // the chart didn't pan while dragging
  await p.mouse.move(from.x + 300, from.y + 100);
  const range2 = await p.evaluate(() => GSL.price.timeScale().getVisibleLogicalRange());
  eq(Math.round(range2.from), Math.round(range.from), "chart did not pan during the drag");
  // recolour, delete, undo
  assert(await p.isVisible("#sel-tools"), "selection toolbar shows");
  await p.click('#sel-colors button[data-color="#b23a32"]');
  eq(await p.evaluate(() => GSL.draw.list().find(d => d.type === "trend").color), "#b23a32", "colour changed");
  await p.keyboard.press("Delete");
  assert(!(await p.evaluate(() => GSL.draw.list().some(d => d.type === "trend"))), "Delete removes the selected drawing");
  await p.keyboard.press("Control+z");
  assert(await p.evaluate(() => GSL.draw.list().some(d => d.type === "trend")), "Ctrl+Z brings it back");
  await p.click("#clear-draw"); eq(await p.evaluate(() => GSL.draw.list().length), 0, "clear all");
  await p.click("#undo-draw"); eq(await p.evaluate(() => GSL.draw.list().length), plan.length, "undo clear all");
  // Escape cancels a half-drawn line
  await p.click('#draw-rail button[data-tool="trend"]'); await p.mouse.click(...at(0.2, 0.2)); await p.keyboard.press("Escape");
  eq(await p.evaluate(() => GSL.draw.list().length), plan.length, "Escape cancels a pending drawing");
  // saved; and anchored in time so they survive a timeframe change
  await p.reload(); await settled(p);
  eq(await p.evaluate(() => GSL.draw.list().length), plan.length, "drawings are remembered");
  await p.click('#tf button[data-tf="1h"]'); await afterChange(p);
  eq(await p.evaluate(() => GSL.draw.list().length), plan.length, "drawings kept on another timeframe");
  await close(p);
});

async function startReplay(p, date) {
  await p.click("#replay-btn");
  assert(await p.isVisible("#rp-pick"), "replay asks where to start");
  await p.fill("#rp-date", date); await p.click("#rp-go");
  await p.waitForFunction(() => GSL.replay.state.active, null, { timeout: 30000 });
}
test("replay: hides the future, steps bar by bar, locks the backtest controls", async () => {
  const p = await newPage();
  await open(p, "ema_trend_4h");
  await p.click("#ind-btn"); await p.click('#ind-list button[data-type="ema"]'); await p.click("#ind-close");
  await startReplay(p, "2025-06-02");
  const s = await p.evaluate(() => {
    const R = GSL.replay.state, t = R.bars.t[R.cur], ind = Object.values(GSL.indicators.live)[0].series.value.data();
    return { cur: R.cur, t: t, last: GSL.candles.data().slice(-1)[0].time, n: GSL.candles.data().length, indLast: ind[ind.length - 1].time,
      plots: GSL.state.plotSeries.every(x => x.data().length === 0), locked: document.getElementById("run").disabled && document.getElementById("strategy").disabled };
  });
  eq(s.t, Date.UTC(2025, 5, 2) / 1000, "starts at the chosen date");
  eq(s.last, s.t, "no candle after the start bar"); eq(s.n, s.cur + 1, "only past bars are on the chart");
  assert(s.indLast <= s.t, "indicators stop at the start bar too"); assert(s.plots, "strategy lines are hidden (they would show the future)");
  assert(s.locked, "backtest controls are locked during replay");
  await p.click("#rp-step");
  await p.locator("body").focus(); await p.evaluate(() => document.activeElement.blur()); await p.keyboard.press("ArrowRight");
  const s2 = await p.evaluate(() => ({ cur: GSL.replay.state.cur, last: GSL.candles.data().slice(-1)[0].time, t: GSL.replay.state.bars.t[GSL.replay.state.cur] }));
  eq(s2.cur, s.cur + 2, "Next bar button and → key each add one bar"); eq(s2.last, s2.t, "new bar drawn");
  assert(/2025-06-02/.test(await p.textContent("#rp-time")), "current replay time shown");
  // play runs on its own; pause stops it
  await p.selectOption("#rp-speed", "10"); await p.click("#rp-play"); await p.waitForTimeout(800); await p.click("#rp-play");
  const played = await p.evaluate(() => GSL.replay.state.cur); assert(played > s2.cur + 3, "Play steps forward on its own");
  await p.waitForTimeout(400); eq(await p.evaluate(() => GSL.replay.state.cur), played, "Pause stops it");
  await p.click("#rp-exit");
  assert(!(await p.evaluate(() => GSL.replayActive)) && !(await p.isDisabled("#run")), "Exit restores the backtest");
  eq(await p.evaluate(() => GSL.candles.data().length), await p.evaluate(() => window.__gsl.result.candles.length), "full chart restored");
  await close(p);
});

test("replay: buy, sell, stops, targets and closes fill exactly like the engine; review matches", async () => {
  const p = await newPage();
  await open(p, "ema_trend_4h");
  await startReplay(p, "2025-06-02");
  const R = () => p.evaluate(() => ({ pos: GSL.replay.state.pos, n: GSL.replay.state.session.trades.length }));
  const stepUntilFlat = async max => { for (let i = 0; i < max && (await R()).pos; i++) await p.click("#rp-step"); };
  // 1) buy with the suggested stop and target and let one of them hit
  await p.fill("#rp-note", "breakout above the range");
  await p.click("#rp-buy");
  assert((await R()).pos && await p.isVisible("#rp-position"), "position opened");
  eq(await p.evaluate(() => GSL.draw.state.orders.map(o => o.key).join()), "entry,sl,tp", "entry, stop and target lines drawn");
  await stepUntilFlat(80);
  if ((await R()).pos) await p.click("#rp-close");
  // 2) sell with no target, move the stop through the form, then close by hand
  await p.fill("#rp-tp", ""); await p.click("#rp-sell");
  for (let i = 0; i < 3; i++) await p.click("#rp-step");
  if ((await R()).pos) {
    const newSl = await p.evaluate(() => { const R = GSL.replay.state; return Math.round((R.bars.c[R.cur] + R.bars.sp[R.cur] + 80) * 100) / 100; });
    await p.fill("#rp-pos-sl", String(newSl)); await p.click('#rp-position button[type="submit"]');
    eq(await p.evaluate(() => GSL.replay.state.pos.sl), newSl, "stop moved");
    await p.click("#rp-step"); if ((await R()).pos) await p.click("#rp-close");
  }
  // 3) drag a stop line on the chart
  await p.fill("#rp-sl", "40"); await p.fill("#rp-tp", "80"); await p.click("#rp-buy");
  const sl = await p.evaluate(() => GSL.replay.state.pos.sl);
  const pt = await chartPoint(p, await p.evaluate(() => GSL.replay.state.bars.t[GSL.replay.state.cur]), sl);
  await p.mouse.move(pt.x - 200, pt.y); await p.mouse.down(); await p.mouse.move(pt.x - 200, pt.y + 25, { steps: 5 }); await p.mouse.up();
  const sl2 = await p.evaluate(() => GSL.replay.state.pos.sl);
  assert(sl2 < sl, `dragging the stop line moves the stop (${sl} -> ${sl2})`);
  await p.click("#rp-step"); await p.click("#rp-step"); if ((await R()).pos) await p.click("#rp-close");
  // 4) quick round trip with Shift+B / Shift+C
  await p.evaluate(() => document.activeElement.blur());
  await p.keyboard.press("Shift+B"); assert((await R()).pos, "Shift+B buys"); await p.keyboard.press("ArrowRight"); await p.keyboard.press("Shift+C");
  const client = await p.evaluate(() => GSL.replay.state.session.trades);
  assert(client.length >= 4, "four trades recorded (got " + client.length + ")");
  eq(client[0].note, "breakout above the range", "note saved with the trade");
  assert(/net/.test(await p.textContent("#rp-stats")), "session stats shown");
  await p.click("#rp-finish");
  await p.waitForFunction(() => window.__gsl.result && window.__gsl.result.strategy.manual, null, { timeout: 45000 });
  const server = await p.evaluate(() => window.__gsl.result.trades);
  eq(server.length, client.length, "same number of trades after review");
  const kind = { SL: "stop", TP: "target", Close: "close" };
  client.forEach((c, i) => {
    const s = server[i];
    assert(Math.abs(s.entry_price - c.entry_price) < 1e-6 && Math.abs(s.exit_price - c.exit_price) < 1e-6, `trade ${i + 1}: prices match (${c.entry_price}/${c.exit_price} vs ${s.entry_price}/${s.exit_price})`);
    assert(Math.abs(s.pnl - c.pnl) < 1e-4, `trade ${i + 1}: P&L matches (${c.pnl} vs ${s.pnl})`);
    eq(s.exit_time, c.exit_time, `trade ${i + 1}: exit time`); eq(s.exit_kind, kind[c.exit_by], `trade ${i + 1}: exit type`);
  });
  assert(await p.evaluate(() => document.getElementById("report-dialog").open), "report card opens after the review");
  const card = await p.textContent("#report-body");
  assert(/Average .*R per trade|per trade over/.test(card) && /stop loss/.test(card), "report card grades the session and reviews habits: " + card.slice(0, 200));
  await p.click("#report-close");
  assert(await p.isVisible("#mode-note") && /replay session/i.test(await p.textContent("#mode-note")), "results say they are from replay");
  assert(!(await p.isDisabled("#run")), "controls unlocked after review");
  await p.click('.tabs button[data-tab="trades"]');
  assert(/Take profit|Stop loss|Closed/.test(await p.textContent("#trades")), "trade list says how each trade ended");
  await p.click("#mode-back"); await settled(p);
  assert(!(await p.evaluate(() => window.__gsl.result.strategy.manual)) && await p.isHidden("#mode-note"), "back to the strategy backtest");
  await close(p);
});

test("replay: sessions are saved, exported, imported and resumed", async () => {
  const p = await newPage();
  await open(p, "ema_trend_4h");
  await startReplay(p, "2025-03-03");
  await p.click("#rp-buy"); await p.click("#rp-step"); await p.click("#rp-step");
  if (await p.evaluate(() => !!GSL.replay.state.pos)) await p.click("#rp-close");
  await p.click("#rp-sell"); await p.click("#rp-step");
  const before = await p.evaluate(() => ({ id: GSL.replay.state.session.id, t: GSL.replay.state.session.current_time, n: GSL.replay.state.session.trades.length, pos: !!GSL.replay.state.pos }));
  await p.click("#rp-exit");
  await p.click("#sessions-btn");
  assert(await p.isVisible(`#sessions-list tr[data-id="${before.id}"]`), "session listed");
  const [dl] = await Promise.all([p.waitForEvent("download"), p.click(`#sessions-list tr[data-id="${before.id}"] button[data-act="export"]`)]);
  const file = await dl.path(), json = JSON.parse(fs.readFileSync(file, "utf8"));
  eq(json.format, "goldlab-replay-session", "export format"); eq(json.trades.length, before.n, "exported trades");
  p.once("dialog", d => d.accept());
  await p.click(`#sessions-list tr[data-id="${before.id}"] button[data-act="delete"]`);
  eq(await p.$$eval("#sessions-list tr[data-id]", r => r.length), 0, "deleted");
  await p.setInputFiles("#sessions-import", file);
  await p.waitForSelector("#sessions-list tr[data-id]");
  await p.click('#sessions-list tr[data-id] button[data-act="resume"]');
  await p.waitForFunction(() => GSL.replay.state.active, null, { timeout: 30000 });
  const after = await p.evaluate(() => ({ t: GSL.replay.state.bars.t[GSL.replay.state.cur], n: GSL.replay.state.session.trades.length, pos: !!GSL.replay.state.pos }));
  eq(after.t, before.t, "resumes at the bar you stopped on"); eq(after.n, before.n, "trades restored"); eq(after.pos, before.pos, "open position restored");
  await p.click("#rp-exit");
  await close(p);
});

test("replay: builds a strategy from your trades and backtests it", async () => {
  const p = await newPage();
  await open(p, "ema_trend_4h");
  // a session whose 1h entries all follow one rule: close crosses above the 20 EMA while above the 200 EMA
  await p.evaluate(async () => {
    const raw = await GSL.api("bars", { timeframe: "1h", at: "2024-01-02", before: 400, after: 1500 });
    const b = Object.assign({ index: raw.index }, GSL.unpackBars(raw.bars).cols);
    const e20 = TA.ema(b.c, 20), e200 = TA.ema(b.c, 200), atr = TA.atr(b.h, b.l, b.c, 14), trades = [];
    let busy = -1;
    for (let i = b.index; i < b.t.length - 12; i++) {
      if (i <= busy || !(b.c[i] > e20[i] && b.c[i - 1] <= e20[i - 1] && b.c[i] > e200[i])) continue;
      const e = b.c[i] + b.sp[i] + 0.05, sl = e - 1.5 * atr[i];
      trades.push({ id: "M" + (trades.length + 1), side: "long", lots: 0.1, entry_time: b.t[i], entry_price: e, sl: sl, tp: e + 2 * (e - sl),
        exit_time: b.t[i + 10], exit_price: b.c[i + 10], exit_by: "Close", pnl: 0, r: null, note: "EMA pullback", mods: [] });
      busy = i + 10;
    }
    localStorage.setItem("gsl:sessions", JSON.stringify([{ format: "goldlab-replay-session", version: 1, id: "stest", name: "Replay 1h test", created: new Date().toISOString(),
      timeframe: "1h", preset: "realistic", settings: {}, start_time: b.t[b.index], current_time: b.t[b.t.length - 1], trades: trades, position: null, swap: 0, events: [] }]));
  });
  await p.click("#sessions-btn");
  await p.click('#sessions-list tr[data-id="stest"] button[data-act="learn"]');
  await p.waitForFunction(() => document.getElementById("learn-dialog").open, null, { timeout: 60000 });
  const text = await p.textContent("#learn-body");
  assert(/Close crosses above the 20 EMA/.test(text) && /Price above the 200 EMA/.test(text), "finds the rule behind the entries: " + text.slice(0, 300));
  assert(/repeats \d+ of your \d+ entries/.test(text), "says how many entries it reproduces");
  await axe(p, "learn dialog");
  await p.click("#learn-run");
  await p.waitForFunction(() => window.__gsl.result && /My setup/.test(window.__gsl.result.strategy.name) && document.getElementById("busy").hidden, null, { timeout: 60000 });
  eq(await p.evaluate(() => window.__gsl.tf), "1h", "switched to the session's timeframe");
  assert(/crossover\(close, ema\(close, 20\)\)/.test(await p.inputValue("#yaml")), "card loaded in the rules editor");
  assert(await p.evaluate(() => window.__gsl.result.metrics.total_trades) > 0, "the learned strategy trades");
  await close(p);
});

test("chart tools: phone layout, tap targets and accessibility", async () => {
  for (const w of [320, 390]) {
    const p = await newPage({ viewport: { width: w, height: 844 }, mobile: true });
    await open(p, "ema_trend_4h");
    await p.click("#draw-toggle");
    assert(await p.isVisible("#draw-rail"), `${w}px: Draw shows the tools`);
    const small = await p.$$eval(".chart-head .btn, #draw-rail button", els => els.filter(e => e.offsetParent).map(e => { const r = e.getBoundingClientRect(); return [e.id || e.dataset.tool, Math.round(r.width), Math.round(r.height)]; }).filter(x => x[1] < 44 || x[2] < 44));
    assert(!small.length, `${w}px: chart tool targets under 44px: ${JSON.stringify(small)}`);
    await startReplay(p, "2025-06-02");
    await noHorizontalScroll(p, `${w}px replay`);
    assert(await p.isVisible("#rp-mobile"), `${w}px: the trade bar is pinned to the bottom`);
    const bar = await p.evaluate(() => { const r = document.getElementById("rp-mobile").getBoundingClientRect(); return { bottom: Math.round(r.bottom), vh: innerHeight }; });
    assert(Math.abs(bar.bottom - bar.vh) <= 1, `${w}px: trade bar sits at the bottom of the screen (${bar.bottom} vs ${bar.vh})`);
    const chart = await p.evaluate(() => { const r = document.getElementById("chart").getBoundingClientRect(); return [Math.round(r.top), Math.round(r.bottom)]; });
    assert(chart[0] >= 0 && chart[1] <= bar.vh - 100, `${w}px: the chart stays fully in view above the bar (${chart})`);
    const bs = await p.$$eval("#rpm-sell, #rpm-buy, #rpm-ticket, #rpm-step", els => els.map(e => Math.round(e.getBoundingClientRect().height)));
    assert(bs.every(h => h >= 44), `${w}px: trade bar buttons at least 44px tall (${bs})`);
    if (w === 390) { await axe(p, "replay dock (phone)"); }
    await close(p);
  }
  const p = await newPage();
  await open(p, "ema_trend_4h");
  await p.click("#ind-btn"); await axe(p, "indicators dialog"); await p.click('#ind-list button[data-type="rsi"]'); await p.click("#ind-close");
  await axe(p, "chart with indicator legend");
  await p.click("#sessions-btn"); await axe(p, "sessions dialog"); await p.click("#sessions-close");
  await startReplay(p, "2025-06-02"); await p.click("#rp-buy"); await axe(p, "replay with a position");
  await close(p);
});

test("replay on a phone: ticket sheet, risk-based sizing, presets, trade from the bar", async () => {
  const p = await newPage({ viewport: { width: 390, height: 844 }, mobile: true });
  await open(p, "ema_trend_4h");
  await startReplay(p, "2025-06-02");
  eq(await p.evaluate(() => document.getElementById("rp-ticket").parentNode.id), "rpm-sheet-body", "ticket lives in the bottom sheet on phones");
  assert(await p.isHidden("#rpm-sheet"), "sheet starts closed");
  await p.tap("#rpm-ticket"); assert(await p.isVisible("#rpm-sheet"), "Ticket opens the sheet");
  await p.selectOption("#rp-sizemode", "risk"); await p.fill("#rp-riskpct", "1");
  await p.tap('#rp-ticket button[data-atr="1.5"]'); await p.tap('#rp-ticket button[data-r="2"]');
  const t = await p.evaluate(() => ({ sl: Number(document.getElementById("rp-sl").value), tp: Number(document.getElementById("rp-tp").value), computed: document.getElementById("rp-computed").textContent, atr: GSL.replay.state._atr[GSL.replay.state.cur] }));
  assert(Math.abs(t.sl - Math.round(t.atr * 1.5 * 10) / 10) < 1e-9, "stop preset = 1.5 × ATR");
  assert(Math.abs(t.tp - Math.round(t.sl * 2 * 10) / 10) < 1e-9, "target preset = 2R");
  const lots = Math.max(0.01, Math.floor(10000 * 0.01 / (t.sl * 100) * 100) / 100);
  assert(t.computed.indexOf(lots.toFixed(2)) >= 0, `risk sizing shows ${lots} lots (${t.computed})`);
  await p.tap("#rpm-sheet-close"); assert(await p.isHidden("#rpm-sheet"), "Done closes the sheet");
  await p.tap("#rpm-buy");
  const pos = await p.evaluate(() => GSL.replay.state.pos);
  assert(pos && Math.abs(pos.lots - lots) < 1e-9, "bought the risk-based size from the bar");
  assert(await p.isVisible("#rpm-close") && await p.isHidden("#rpm-buy"), "bar shows Close while in a position");
  await p.tap("#rpm-ticket"); assert(await p.isVisible("#rp-position") && /Stop and target/.test(await p.textContent("#rpm-sheet-title")), "sheet shows the position's stop and target");
  await p.tap("#rpm-sheet-close");
  await p.tap("#rpm-step"); eq(await p.evaluate(() => GSL.replay.state.cur), 1501, "› steps one bar");
  assert(/bal|open/.test(await p.textContent("#rpm-status")), "status line shows balance");
  if (await p.evaluate(() => !!GSL.replay.state.pos)) await p.tap("#rpm-close");
  eq(await p.evaluate(() => GSL.replay.state.session.trades.length), 1, "trade recorded");
  await p.tap("#rp-exit");
  assert(await p.isHidden("#rp-mobile") && !(await p.evaluate(() => document.body.classList.contains("replaying"))), "bar goes away on exit");
  eq(await p.evaluate(() => document.getElementById("rp-ticket").parentNode.id), "rp-run", "ticket returns to the dock");
  await close(p);
});

test("replay coach: the strategy's own trades show up as you step", async () => {
  const p = await newPage();
  await open(p, "ema_trend_4h");
  const strat = await p.evaluate(() => window.__gsl.result.trades);
  const t = strat[strat.length - 10];
  const date = new Date((t.entry_time - 5 * 14400) * 1000).toISOString().slice(0, 10);
  await startReplay(p, date);
  await p.check("#rp-coach");
  const before = await p.evaluate(() => GSL.markers.markers().filter(m => /^S /.test(m.text)).length);
  for (let i = 0; i < 12; i++) await p.click("#rp-step");
  const after = await p.evaluate(() => GSL.markers.markers().filter(m => /^S /.test(m.text)));
  assert(after.length > before, "strategy markers appear once their bar is revealed");
  const cur = await p.evaluate(() => GSL.replay.state.bars.t[GSL.replay.state.cur]);
  assert(after.every(m => m.time <= cur), "no marker from the future");
  assert(/Strategy: (long|short|flat)/.test(await p.textContent("#rp-coach-text")), "coach text describes the strategy's position");
  await p.uncheck("#rp-coach");
  eq(await p.evaluate(() => GSL.markers.markers().filter(m => /^S /.test(m.text)).length), 0, "unchecking removes them");
  await p.click("#rp-exit");
  await close(p);
});

test("journal: every replay trade across sessions, with CSV export", async () => {
  const p = await newPage();
  await open(p, "ema_trend_4h");
  for (const d of ["2025-03-03", "2025-06-02"]) {
    await startReplay(p, d); await p.fill("#rp-note", "note for " + d); await p.click("#rp-buy"); await p.click("#rp-step");
    if (await p.evaluate(() => !!GSL.replay.state.pos)) await p.click("#rp-close");
    await p.click("#rp-exit");
  }
  await p.click("#sessions-btn"); await p.click('.sessions-tabs button[data-view="journal"]');
  eq(await p.$$eval("#journal tbody tr", r => r.length), 2, "two trades from two sessions");
  assert(/note for 2025-06-02/.test(await p.textContent("#journal")), "notes are shown");
  const [dl] = await Promise.all([p.waitForEvent("download"), p.click("#journal-csv")]);
  const csv = fs.readFileSync(await dl.path(), "utf8").trim().split("\n");
  eq(csv.length, 3, "CSV has a header and two rows"); assert(/^session,timeframe,side/.test(csv[0]) && /note for/.test(csv[1]), "CSV columns");
  await axe(p, "journal");
  await close(p);
});

test("share link: a strategy card travels in the URL; theme toggle; shortcuts dialog", async () => {
  const p = await newPage();
  await open(p, "ema_trend_4h");
  await p.context().grantPermissions(["clipboard-read", "clipboard-write"]);
  await p.click("#rules-block summary");
  await p.fill("#yaml", "name: Shared idea\ntimeframe: 1h\nlong:\n  when: crossover(close, ema(close, 20))\n  sl_dist: 2 * atr(14)\n");
  await p.click("#share-btn");
  const url = await p.evaluate(() => navigator.clipboard.readText());
  assert(/#card=[A-Za-z0-9_-]+$/.test(url), "link holds the card: " + url.slice(0, 80));
  const q = await newPage();
  await q.goto(url, { waitUntil: "domcontentloaded" }); await settled(q);
  eq(await q.evaluate(() => window.__gsl.result.strategy.name), "Shared idea", "opening the link runs the shared rules");
  eq(await q.evaluate(() => window.__gsl.tf), "1h", "and switches to its timeframe");
  assert(/shared link/.test(await q.textContent("#yaml-status")), "status says where it came from");
  await q.goto(BASE + "#card=!!!not-base64", { waitUntil: "domcontentloaded" }); await settled(q);
  assert(!(await q.isHidden("#banner")) && /damaged/.test(await q.textContent("#banner")), "a broken link gets a clear message");
  await close(q);
  // theme
  await p.click("#theme-btn"); eq(await p.evaluate(() => document.documentElement.getAttribute("data-theme")), "light", "auto → light");
  await p.click("#theme-btn"); eq(await p.evaluate(() => document.documentElement.getAttribute("data-theme")), "dark", "light → dark");
  await p.reload({ waitUntil: "domcontentloaded" });
  eq(await p.evaluate(() => document.documentElement.getAttribute("data-theme")), "dark", "theme remembered before the app loads");
  await settled(p);
  await p.click("#theme-btn"); eq(await p.evaluate(() => document.documentElement.getAttribute("data-theme")), null, "dark → follows the device");
  // shortcuts
  await p.keyboard.press("?");
  assert(await p.evaluate(() => document.getElementById("keys-dialog").open), "? opens the shortcuts");
  await axe(p, "shortcuts dialog");
  await p.keyboard.press("Escape"); assert(!(await p.evaluate(() => document.getElementById("keys-dialog").open)), "Escape closes it");
  await p.click("#keys-btn"); assert(await p.evaluate(() => document.getElementById("keys-dialog").open), "button opens it too"); await p.click("#keys-close");
  await close(p);
});

test("outlook: the analyst's view loads with drivers, numbers, strategies, news and a track record", async () => {
  const p = await newPage();
  await open(p, "ema_trend_4h");
  await p.click('.tabs button[data-tab="outlook"]');
  await p.waitForSelector(".ol-head", { timeout: 120000 });
  const word = await p.textContent(".ol-word");
  assert(/^(bullish|bearish|neutral)$/.test(word.trim()), "direction shown: " + word);
  assert(/\d+% · \d+ days/.test(await p.textContent(".ol-conf")), "confidence and horizon shown");
  const sub = await p.textContent(".ol-title .hint");
  assert(/Written by the analyst|Stand-in view/.test(sub), "says who wrote it: " + sub);
  assert((await p.$$eval("table.ol-drivers tbody tr", r => r.length)) >= 3, "at least three drivers");
  assert((await p.$$eval(".ol-kpis div", r => r.length)) >= 8, "technical and macro numbers shown");
  assert((await p.$$eval(".ol-strats li", r => r.length)) >= 7, "every strategy's current position is listed");
  assert((await p.$$eval(".ol-news li a", r => r.length)) >= 5, "headlines with links");
  assert(/Track record/.test(await p.textContent(".ol-score")), "track record section");
  const btn = await p.textContent("#ol-refresh");
  assert(await p.isDisabled("#ol-refresh") && /Next refresh/.test(btn), "a fresh view can't be refreshed again for an hour: " + btn);
  const api = await p.evaluate(() => fetch("/api/outlook?refresh=1", { method: "POST" }).then(r => r.json().then(j => [r.status, j.error])));
  eq(api[0], 429, "early refresh is refused by the API too"); assert(/60 minutes/.test(api[1]), api[1]);
  await axe(p, "outlook tab");
  await close(p);
  const m = await newPage({ viewport: { width: 390, height: 844 }, mobile: true });
  await open(m, "ema_trend_4h");
  await m.click('.tabs button[data-tab="outlook"]');
  await m.waitForSelector(".ol-head", { timeout: 60000 });
  await noHorizontalScroll(m, "outlook on a phone");
  await close(m);
});

test("speed: first result, payload size, history on scroll, repeat visits", async () => {
  const p = await newPage();
  const t0 = Date.now();
  await open(p, "ema_trend_4h");
  const first = Date.now() - t0;
  const res = await p.evaluate(() => performance.getEntriesByType("resource").map(r => ({ name: r.name.replace(/^https?:\/\/[^/]+/, ""), transfer: r.transferSize, raw: r.decodedBodySize, ms: Math.round(r.duration) })));
  const bt = res.find(r => /op=backtest/.test(r.name)), js = res.filter(r => /\.js$/.test(r.name) && !/\/npm\//.test(r.name));
  assert(bt, "backtest response recorded");
  console.log(`      first result ${first} ms · backtest ${Math.round(bt.raw / 1024)} KB raw / ${Math.round(bt.transfer / 1024)} KB on the wire · own JS ${Math.round(js.reduce((a, r) => a + r.raw, 0) / 1024)} KB raw`);
  assert(first < 8000, `first result took ${first} ms`);
  assert(bt.raw < 400 * 1024, `backtest payload is ${Math.round(bt.raw / 1024)} KB raw (budget 400)`);
  assert(js.reduce((a, r) => a + r.raw, 0) < 220 * 1024, "own JavaScript stays under 220 KB raw");
  if (BASE.startsWith("https")) assert(bt.transfer < 120 * 1024, `backtest payload is ${Math.round(bt.transfer / 1024)} KB on the wire (budget 120)`);
  // the first result carries a 3,000-bar window; older bars arrive when you scroll left
  const r0 = await R(p);
  eq(r0.candles.length, 3000, "first paint shows the last 3,000 bars"); assert(r0.data.more_history, "more history is available");
  const firstBar = r0.candles[0][0];
  await p.evaluate(() => GSL.price.timeScale().setVisibleLogicalRange({ from: -10, to: 200 }));
  await p.waitForFunction(() => window.__gsl.result.candles.length > 3000, null, { timeout: 20000 });
  const r1 = await R(p);
  assert(r1.candles[0][0] < firstBar && r1.candles.length >= 5900, "older bars prepended (" + r1.candles.length + ")");
  const times = r1.candles.map(c => c[0]); assert(times.every((t, i) => !i || t > times[i - 1]), "bars stay in order");
  const plot = Object.values(r1.plots)[0]; assert(plot[0][0] < firstBar, "strategy lines cover the older bars too");
  const vr = await p.evaluate(() => GSL.price.timeScale().getVisibleLogicalRange());
  assert(vr.from > 2000, "view stays where it was after bars are prepended (from=" + Math.round(vr.from) + ")");
  // picking the oldest trade loads history back to it
  await p.click('.tabs button[data-tab="trades"]');
  const oldest = await p.evaluate(() => window.__gsl.result.trades[0].n);
  await p.click(`#trades tr[data-n="${oldest}"]`);
  await p.waitForFunction(n => window.__gsl.selected === n, oldest, { timeout: 60000 });
  await close(p);
  if (BASE.startsWith("https")) {
    const q = await newPage({ sw: true });
    await open(q, "ema_trend_4h");
    await q.evaluate(() => navigator.serviceWorker.ready);
    await q.waitForFunction(() => !!navigator.serviceWorker.controller, null, { timeout: 15000 }).catch(() => {});
    await q.reload({ waitUntil: "domcontentloaded" }); await settled(q);
    const cdn = await q.evaluate(() => performance.getEntriesByType("resource").filter(r => /jsdelivr|gstatic/.test(r.name)).map(r => r.transferSize));
    assert(cdn.length && cdn.every(x => x === 0), "chart library and fonts come from the worker's cache on a repeat visit (" + cdn.join(",") + ")");
    await close(q);
  }
});

// ------------------------------------------------------------------ runner
function waitFor(url, ms) {
  const until = Date.now() + ms;
  return new Promise((resolve, reject) => {
    const tick = () => http.get(url, r => { r.resume(); resolve(); }).on("error", () => Date.now() > until ? reject(new Error("server did not start")) : setTimeout(tick, 300));
    tick();
  });
}
(async () => {
  if (!BASE) {
    const pub = path.join(ROOT, "public");
    for (const f of fs.readdirSync(path.join(ROOT, "web"))) fs.copyFileSync(path.join(ROOT, "web", f), path.join(pub, f));
    const port = 8800 + Math.floor(Math.random() * 100);
    const outlookDir = path.join(require("os").tmpdir(), "gsl-outlook-" + Date.now());
    server = spawn("python3", ["-m", "goldlab", "serve", "--port", String(port), "--dir", pub], { cwd: ROOT, stdio: "ignore", env: { ...process.env, GSL_OUTLOOK_DIR: outlookDir } });
    BASE = `http://127.0.0.1:${port}/`;
    await waitFor(BASE, 20000);
  }
  if (!BASE.endsWith("/")) BASE += "/";
  console.log(`Testing ${BASE}\n`);
  browser = await chromium.launch();
  const t0 = Date.now();
  for (const t of tests) {
    if (ONLY.length && !ONLY.some(w => t.name.toLowerCase().includes(w.toLowerCase()))) continue;
    const s = Date.now();
    try { await t.fn(); results.push([t.name, true]); console.log(`  PASS  ${t.name}  (${((Date.now() - s) / 1000).toFixed(1)}s)`); }
    catch (e) {
      results.push([t.name, false, e.message]);
      const where = (e.stack || "").split("\n").find(l => l.includes("run.cjs:")) || "";
      console.log(`  FAIL  ${t.name}\n        ${e.message.split("\n")[0].slice(0, 600)}\n        ${where.trim()}`);
    }
  }
  await browser.close();
  if (server) server.kill();
  const failed = results.filter(r => !r[1]);
  console.log(`\n${results.length - failed.length}/${results.length} passed in ${((Date.now() - t0) / 1000).toFixed(0)}s`);
  process.exit(failed.length ? 1 : 0);
})().catch(e => { console.error(e); if (server) server.kill(); process.exit(2); });
