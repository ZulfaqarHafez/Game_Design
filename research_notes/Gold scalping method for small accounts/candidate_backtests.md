# Candidate backtests on the project's own engine (computed, not sourced from the web)

**Provenance.** Run on 19 Nov 2026 with this project's backtest engine (`goldlab`: TradingView fill rules, orders fill on the
next bar, stops/targets along the in-bar path) on Dukascopy XAUUSD data: 5m and 15m bars 1 Jan 2025 - 3 May 2026, 1h bars
2019 - Sep 2026. "Realistic" costs = recorded bid/ask spread + $7/lot round-turn commission + $0.05 slippage per fill
(about $0.75-0.80/oz all-in). "Gross" = zero costs. Size fixed at 1 oz (0.01 lot) so results are per ounce; R = profit divided
by the initial stop distance. 95% confidence intervals are 1.96 standard errors of the per-trade R. The candidates and their
variants were specified from the research notes BEFORE running (the "pre-registered" rows); "control" rows invert or remove
the directional filter to check that the filter, not luck, produces the result. About 45 strategy runs were made in total
(4 candidate families, their controls, and the stress tests below), which matters for multiple-testing corrections.

## Results in one table

| Candidate (pre-registered version) | Trades | Win % | Net avg R (95% CI) | Net PF | Gross PF | First / second half | Verdict |
|---|---|---|---|---|---|---|---|
| C1 New York ORB 09:30, 5-min range, with the range candle, 2R or 12:00 exit | 252 | 35 | -0.09 ±0.16 | 1.03 | 1.32 | -0.15 / -0.02 R | Gross edge, eaten by costs |
| C1 same, 15-min range | 213 | 41 | -0.05 ±0.15 | 0.89 | 0.96 | -0.17 / +0.08 R | No edge |
| C1 15-min range + 1h EMA200 trend side | 123 | 46 | -0.01 ±0.19 | 1.18 | 1.23 | -0.20 / +0.19 R | Indistinguishable from zero |
| C2 Trend-aligned sweep-and-reclaim (15m), 2R | 235 | 30 | -0.24 ±0.16 | 0.75 | 0.89 | -0.33 / -0.14 R | Loses, even gross |
| **C3 Trend pullback (15m, 1h EMA200 trend), stop 2.5 ATR, 2R** | **215** | **40** | **+0.21 ±0.20** | **1.15** | **1.22** | **+0.36 / +0.08 R** | **Only positive candidate** |
| C4 Asia-hours long drift (1h, 2019-2026), buy 19:00 NY, sell 03:00 NY | 2000 | 49 | -$0.03 ±0.83 per oz | 0.99 | 1.16 | -0.36 / +0.29 $/oz | Real gross drift (+$0.68/oz), zero after costs |
| C5 Momentum into the COMEX close (13:00-13:30 NY) | 341 | 55 | -$0.71 ±0.98 per oz | n/a | n/a | n/a | Gross +$0.11/oz, far below cost |

## What the controls and stress tests say about C3 (the 15-minute trend pullback)

- **The trend filter carries the result.** Trend-aligned +0.21R; no 1h filter +0.03R; counter-trend -0.26R. That ordering is what a
  real effect looks like, and it is the opposite of C1/C2 where controls did as well as or better than the rule.
- **Both sides worked in this sample.** Longs +0.21R (n=158, PF 1.19); shorts +0.21R (n=57, PF 1.08).
- **It weakened in 2026.** 2025H1 +0.34R (PF 1.64), 2025H2 +0.27R (PF 1.30), 2026H1 -0.03R (PF 0.88). Monthly results range from -7.1R to +12.9R.
- **Costs barely matter because the stop is wide.** Median risk $15.6/oz, so the ~$0.80 cost is about 5% of risk. Costs x2: +0.20R, PF 1.14.
  Pessimistic in-bar fills: unchanged.
- **Nearby settings form a plateau, not a spike.** Stops 2.0-3.0 ATR x targets 1.5-2.5R: average R +0.07 to +0.24 in all nine cells;
  profit factor 0.92-1.19 (two cells at or below 1.03). All hours instead of 07:00-16:00 UTC: +0.19R ±0.15, PF 1.25, 364 trades.
  One trade a day: +0.15R, PF 1.02.
- **It is not a scalp.** Average hold 28 bars (7.1 hours); 128 stops, 87 targets; max losing streak 8; max drawdown 15.9R; about 3 trades a week.
- **5-minute execution of the same rule loses** (-0.06R net, PF 0.94; +0.11R gross): on 5m the stop is a third the size, so costs are
  three times the share of risk. 15m is the shortest timeframe where this rule clears costs.
- **Longer history, one timeframe up (1h bars, 4h trend, 2019-2026):** +0.06R ±0.14, PF 1.14, 443 trades; positive in 7 of 8 years but tiny
  (2021 -0.19R); longs +0.15R (PF 1.30), shorts -0.10R (PF 0.92). The controls were about as good (no filter +0.06R), so the long-history
  evidence is weak: mostly long-side drift.
- **Statistical honesty.** The 95% interval (+0.01R to +0.41R) only just excludes zero, on one 16-month bull-then-correction sample, after about
  45 runs. A multiple-testing correction would not call this significant. Treat it as the best available hypothesis, not a proven edge.

## What this means on a $100 account

At 0.1 oz (the size a Singapore retail account can hold at 20% margin, if the broker allows 0.1-unit orders): median risk about $1.56 per
trade (1.6% of the account), a 2R win about +$3.1, expected value about +$0.2-0.3 per trade if the backtest edge is real, about 3 trades a
week, and a historical worst drawdown of about 16R = roughly $25 (25% of the account).

## Raw output: candidates

```
Data: 5m 2025-01-01..2026-05-03 (94,329 bars); 15m 31,446 bars; 1h 2019-01-01..2026-09-30 (45,825 bars)

C1. New York opening-range breakout (09:30 NY), stop order at the range edge, stop at the far side, target 2R, flat at 12:00, max one trade a day, skip ranges wider than 30% of daily ATR
  5-min range, no trend filter, WITH the range candle (pre-registered): n=252 (3.6/wk), win 35%, net avg -0.086R ±0.161, net +0.14 $/oz, PF net 1.03 | gross PF 1.32, gross avg +0.067R | halves -0.15 / -0.02 R | avg risk $9.1/oz
  5-min range, no trend filter, AGAINST it (control): n=227 (3.3/wk), win 36%, net avg -0.070R ±0.166, net -0.14 $/oz, PF net 0.97 | gross PF 1.12, gross avg +0.040R | halves -0.04 / -0.10 R | avg risk $9.0/oz
  5-min range, no trend filter, either side (control): n=283 (4.1/wk), win 32%, net avg -0.158R ±0.149, net -1.33 $/oz, PF net 0.78 | gross PF 1.09, gross avg +0.001R | halves -0.05 / -0.27 R | avg risk $9.2/oz
  5-min range, 1h EMA200 trend side only, WITH the range candle (pre-registered): n=143 (2.1/wk), win 33%, net avg -0.179R ±0.204, net +0.07 $/oz, PF net 1.01 | gross PF 1.25, gross avg -0.016R | halves -0.35 / -0.02 R | avg risk $8.4/oz
  5-min range, 1h EMA200 trend side only, AGAINST it (control): n=104 (1.5/wk), win 37%, net avg -0.066R ±0.241, net +0.44 $/oz, PF net 1.08 | gross PF 1.24, gross avg +0.057R | halves -0.16 / +0.03 R | avg risk $9.8/oz
  5-min range, 1h EMA200 trend side only, either side (control): n=240 (3.4/wk), win 35%, net avg -0.118R ±0.158, net +0.33 $/oz, PF net 1.06 | gross PF 1.27, gross avg +0.033R | halves -0.24 / +0.00 R | avg risk $9.1/oz
  15-min range, no trend filter, WITH the range candle (pre-registered): n=213 (3.1/wk), win 41%, net avg -0.051R ±0.149, net -0.70 $/oz, PF net 0.89 | gross PF 0.96, gross avg +0.010R | halves -0.17 / +0.08 R | avg risk $13.2/oz
  15-min range, no trend filter, AGAINST it (control): n=192 (2.8/wk), win 47%, net avg +0.081R ±0.157, net +1.62 $/oz, PF net 1.31 | gross PF 1.46, gross avg +0.146R | halves +0.08 / +0.08 R | avg risk $13.0/oz
  15-min range, no trend filter, either side (control): n=272 (3.9/wk), win 41%, net avg -0.051R ±0.134, net -0.65 $/oz, PF net 0.90 | gross PF 0.99, gross avg +0.014R | halves -0.09 / -0.01 R | avg risk $13.6/oz
  15-min range, 1h EMA200 trend side only, WITH the range candle (pre-registered): n=123 (1.8/wk), win 46%, net avg -0.009R ±0.194, net +0.91 $/oz, PF net 1.18 | gross PF 1.23, gross avg +0.039R | halves -0.20 / +0.19 R | avg risk $12.9/oz
  15-min range, 1h EMA200 trend side only, AGAINST it (control): n=92 (1.3/wk), win 48%, net avg +0.032R ±0.204, net +1.36 $/oz, PF net 1.27 | gross PF 1.48, gross avg +0.115R | halves -0.09 / +0.14 R | avg risk $13.5/oz
  15-min range, 1h EMA200 trend side only, either side (control): n=210 (3.0/wk), win 48%, net avg +0.021R ±0.143, net +1.17 $/oz, PF net 1.23 | gross PF 1.35, gross avg +0.086R | halves -0.14 / +0.18 R | avg risk $13.2/oz

C2. Sweep-and-reclaim of the previous-day or Asian-range (20:00-00:00 NY) extreme on 15m: bar pokes through the level by <= 0.5 ATR and closes back inside; market entry next bar; stop beyond the sweep extreme; time stop 16 bars; 02:00-05:00 and 07:00-11:00 NY; max two a day
  trend-aligned (pre-registered), target 1.5R: n=238 (3.4/wk), win 34%, net avg -0.252R ±0.140, net -1.05 $/oz, PF net 0.76 | gross PF 0.95, gross avg -0.059R | halves -0.36 / -0.13 R | avg risk $6.9/oz
  trend-aligned (pre-registered), target 2R: n=235 (3.4/wk), win 30%, net avg -0.244R ±0.158, net -1.11 $/oz, PF net 0.75 | gross PF 0.89, gross avg -0.077R | halves -0.33 / -0.14 R | avg risk $6.6/oz
  trend-aligned (pre-registered), target 3R: n=234 (3.4/wk), win 26%, net avg -0.206R ±0.188, net -0.86 $/oz, PF net 0.82 | gross PF 0.98, gross avg -0.021R | halves -0.32 / -0.08 R | avg risk $6.6/oz
  no trend filter (control), target 2R: n=495 (7.1/wk), win 27%, net avg -0.282R ±0.109, net -1.60 $/oz, PF net 0.65 | gross PF 0.79, gross avg -0.108R | halves -0.27 / -0.29 R | avg risk $6.5/oz
  counter-trend (control), target 2R: n=328 (4.7/wk), win 27%, net avg -0.272R ±0.136, net -1.32 $/oz, PF net 0.72 | gross PF 0.87, gross avg -0.096R | halves -0.19 / -0.35 R | avg risk $6.7/oz

C3. Trend pullback on 15m: 1h close beyond a rising/falling EMA200; EMA 9>21>50 stack before the pullback; price tags EMA21; enter when a bar closes back across EMA9; stop 2.5 ATR; target 2R; 07:00-16:00 UTC; max two a day
  trend-aligned (pre-registered): n=215 (3.1/wk), win 40%, net avg +0.209R ±0.198, net +1.83 $/oz, PF net 1.15 | gross PF 1.22, gross avg +0.262R | halves +0.36 / +0.08 R | avg risk $19.2/oz
  no 1h filter (control): n=359 (5.2/wk), win 35%, net avg +0.032R ±0.149, net +1.00 $/oz, PF net 1.08 | gross PF 1.16, gross avg +0.097R | halves +0.01 / +0.05 R | avg risk $19.2/oz
  counter-trend (control): n=149 (2.1/wk), win 26%, net avg -0.263R ±0.217, net -1.66 $/oz, PF net 0.88 | gross PF 1.01, gross avg -0.149R | halves -0.39 / -0.15 R | avg risk $20.0/oz
  trend-aligned, stop 3 ATR, target 2.25R (published variant): n=186 (2.7/wk), win 38%, net avg +0.216R ±0.231, net +1.17 $/oz, PF net 1.07 | gross PF 1.11, gross avg +0.249R | halves +0.42 / +0.04 R | avg risk $23.7/oz

C4. Asia-hours long drift on 1h bars, 2019 - Sep 2026: buy at the stated New York hour, sell at 03:00 New York, long only, no stop (per-ounce results)
  buy 19:00 NY, every day: n=2000 (4.9/wk), win 49%, net avg -0.03 ±0.83 $/oz, net -0.03 $/oz, PF net 0.99 | gross PF 1.16, gross avg +0.68 $/oz | halves -0.36 / +0.29 $/oz
  buy 19:00 NY, only when daily close > 200-day SMA: n=1367 (3.4/wk), win 49%, net avg -0.09 ±1.11 $/oz, net -0.09 $/oz, PF net 0.98 | gross PF 1.13, gross avg +0.64 $/oz | halves -0.63 / +0.27 $/oz
  buy 20:00 NY, every day: n=1999 (4.9/wk), win 48%, net avg -0.21 ±0.77 $/oz, net -0.21 $/oz, PF net 0.96 | gross PF 1.10, gross avg +0.42 $/oz | halves -0.47 / +0.06 $/oz
  buy 20:00 NY, only when daily close > 200-day SMA: n=1367 (3.4/wk), win 49%, net avg -0.25 ±1.03 $/oz, net -0.25 $/oz, PF net 0.95 | gross PF 1.09, gross avg +0.41 $/oz | halves -0.71 / +0.07 $/oz
  buy 21:00 NY, every day: n=2000 (4.9/wk), win 48%, net avg -0.45 ±0.65 $/oz, net -0.45 $/oz, PF net 0.90 | gross PF 1.04, gross avg +0.18 $/oz | halves -0.43 / -0.47 $/oz
  buy 21:00 NY, only when daily close > 200-day SMA: n=1367 (3.4/wk), win 49%, net avg -0.46 ±0.87 $/oz, net -0.46 $/oz, PF net 0.90 | gross PF 1.04, gross avg +0.19 $/oz | halves -0.65 / -0.32 $/oz
    buy 20:00 every day, net $/oz per trade by year: 2019: -0.51 (n=257, win 46%), 2020: -0.77 (n=259, win 50%), 2021: +0.28 (n=258, win 49%), 2022: -0.85 (n=258, win 44%), 2023: -0.49 (n=257, win 47%), 2024: +0.16 (n=259, win 51%), 2025: +1.31 (n=258, win 50%), 2026: -0.97 (n=193, win 48%)
    as % of price by year: 2019: -3.5 bp, 2020: -4.6 bp, 2021: +1.7 bp, 2022: -4.6 bp, 2023: -2.4 bp, 2024: +0.7 bp, 2025: +3.9 bp, 2026: -2.0 bp
    same rule on Jan 2025 - May 2026 only: n=343, net +1.27 $/oz, win 50%
    worst single trade -245.8 $/oz, 5th percentile -21.0, 95th +23.5, std 17.6

C5. Intraday momentum into the COMEX close (13:00 -> 13:30 NY in the direction of the move since the previous 13:30), 5m data, cost = spread + $0.17/oz
  |move since yesterday's close| >= 0.0%: n=341, gross +0.11 $/oz (win 55%), net -0.71 ±0.98
  |move since yesterday's close| >= 0.5%: n=224, gross -0.07 $/oz (win 51%), net -0.92 ±1.39
  |move since yesterday's close| >= 1.0%: n=137, gross +0.24 $/oz (win 51%), net -0.63 ±2.16
  |move since yesterday's close| >= 1.5%: n=74, gross +0.23 $/oz (win 54%), net -0.72 ±3.70
```

## Raw output: stress tests of C3

```
R1. The pre-registered 15m trend pullback (stop 2.5 ATR, target 2R), realistic costs, Jan 2025 - May 2026
  all trades: n=215, win 40%, avg +0.209R ±0.198, +1.83 $/oz, PF 1.15
  longs: n=158, win 41%, avg +0.210R ±0.231, +2.02 $/oz, PF 1.19
  shorts: n=57, win 40%, avg +0.206R ±0.386, +1.30 $/oz, PF 1.08
  2025H1: n=69, win 45%, avg +0.339R ±0.355, +4.59 $/oz, PF 1.64
  2025H2: n=87, win 43%, avg +0.269R ±0.314, +2.78 $/oz, PF 1.30
  2026H1: n=59, win 32%, avg -0.031R ±0.364, -2.81 $/oz, PF 0.88
  entered 07:00-12:00 UTC (London): n=136, win 39%, avg +0.162R ±0.247, +0.93 $/oz, PF 1.08
  entered 12:00-16:00 UTC (New York): n=79, win 43%, avg +0.291R ±0.332, +3.36 $/oz, PF 1.27
  exits: {'stop': 128, 'target': 87}; average bars held 28 (15m bars) = 7.1 h; median risk $15.6/oz; max losing streak 8
  cumulative +45.0R over 215 trades; max drawdown 15.9R; monthly R: 25-01: +1.9, 25-02: +7.9, 25-03: +6.9, 25-04: +4.9, 25-05: +5.9, 25-06: -4.1, 25-07: +0.9, 25-08: +4.9, 25-09: +7.9, 25-10: +12.9, 25-11: +1.9, 25-12: -5.1, 26-01: -3.7, 26-02: +3.0, 26-03: -7.1, 26-04: +6.0

R2. Cost stress on the same rule
  costs x1.5 (slippage 8 ticks, commission $5.25/lot/side, spread as recorded): n=215, win 40%, avg +0.206R ±0.198, +1.77 $/oz, PF 1.14
  costs x2 (slippage 10 ticks, commission $7/lot/side): n=215, win 40%, avg +0.202R ±0.198, +1.73 $/oz, PF 1.14
  pessimistic in-bar fills (stop before target): n=215, win 40%, avg +0.209R ±0.198, +1.83 $/oz, PF 1.15
  zero costs (TradingView default): n=212, win 42%, avg +0.262R ±0.200, +2.63 $/oz, PF 1.22

R3. Nearby settings (a plateau is good, a lone spike is bad). 15m, trend-aligned, realistic costs: average R / profit factor
  stop 2.0 ATR -> target 1.5R: +0.07R / PF 0.92 (n=249, win 43%); target 2.0R: +0.20R / PF 1.14 (n=238, win 40%); target 2.5R: +0.24R / PF 1.19 (n=234, win 35%)
  stop 2.5 ATR -> target 1.5R: +0.20R / PF 1.09 (n=225, win 48%); target 2.0R: +0.21R / PF 1.15 (n=215, win 40%); target 2.5R: +0.18R / PF 1.03 (n=203, win 34%)
  stop 3.0 ATR -> target 1.5R: +0.18R / PF 1.13 (n=206, win 48%); target 2.0R: +0.17R / PF 1.03 (n=188, win 40%); target 2.5R: +0.23R / PF 1.10 (n=179, win 36%)
  one trade a day instead of two: n=184, win 39%, avg +0.150R ±0.212, +0.22 $/oz, PF 1.02
  all hours instead of 07:00-16:00 UTC: n=364, win 40%, avg +0.186R ±0.152, +3.16 $/oz, PF 1.25

R4. Same idea one timeframe up, for a longer history: 1h bars with the 4h trend (EMA200 rising/falling), 2019 - Sep 2026, realistic costs
  trend-aligned: n=443, win 36%, avg +0.060R ±0.135, +1.65 $/oz, PF 1.14
    by year: 2019: +0.10R (n=45), 2020: +0.01R (n=59), 2021: -0.19R (n=55), 2022: +0.07R (n=61), 2023: +0.03R (n=62), 2024: +0.04R (n=63), 2025: +0.13R (n=58), 2026: +0.38R (n=40)
    longs: n=280, win 39%, avg +0.150R ±0.173, +3.20 $/oz, PF 1.30 | shorts: n=163, win 31%, avg -0.096R ±0.215, -1.01 $/oz, PF 0.92
  no trend filter (control): n=680, win 36%, avg +0.055R ±0.109, +1.27 $/oz, PF 1.11
  counter-trend (control): n=234, win 35%, avg +0.024R ±0.184, -1.16 $/oz, PF 0.92

R5. And on 5m bars with the 15m... skipped: the 1h EMA200 filter needs 1h bars; 5m execution with the same 1h trend filter:
  5m execution, 1h trend, stop 2.5 ATR(5m), target 2R: n=418, win 32%, avg -0.058R ±0.134, -0.47 $/oz, PF 0.94
    same at zero cost: n=418, win 37%, avg +0.112R ±0.139, +1.03 $/oz, PF 1.15
```
