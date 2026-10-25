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
  const tabs = ["overview", "performance", "analysis", "trades", "monthly", "checks", "properties", "compare"];
  for (const t of tabs) {
    await p.click(`.tabs button[data-tab="${t}"]`);
    for (const u of tabs) eq(await p.isVisible(`#tab-${u}`), u === t, `${t} selected: ${u} visibility`);
    eq(await p.getAttribute(`.tabs button[data-tab="${t}"]`, "aria-selected"), "true", `${t} aria-selected`);
  }
  await p.focus('.tabs button[data-tab="compare"]');
  await p.keyboard.press("Home"); eq(await p.evaluate(() => document.activeElement.dataset.tab), "overview", "Home");
  await p.keyboard.press("ArrowRight"); eq(await p.evaluate(() => document.activeElement.dataset.tab), "performance", "ArrowRight");
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
  for (let i = 0; i < 60; i++) { await p.keyboard.press("Tab"); seen.add(await p.evaluate(() => document.activeElement.id || document.activeElement.dataset.tf || document.activeElement.dataset.tab || document.activeElement.tagName)); }
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
    server = spawn("python3", ["-m", "goldlab", "serve", "--port", String(port), "--dir", pub], { cwd: ROOT, stdio: "ignore" });
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
    catch (e) { results.push([t.name, false, e.message]); console.log(`  FAIL  ${t.name}\n        ${e.message.split("\n")[0].slice(0, 600)}`); }
  }
  await browser.close();
  if (server) server.kill();
  const failed = results.filter(r => !r[1]);
  console.log(`\n${results.length - failed.length}/${results.length} passed in ${((Date.now() - t0) / 1000).toFixed(0)}s`);
  process.exit(failed.length ? 1 : 0);
})().catch(e => { console.error(e); if (server) server.kill(); process.exit(2); });
