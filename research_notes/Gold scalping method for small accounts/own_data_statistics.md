# Own-data statistics: what our 5-minute gold data says (computed, not sourced from the web)

**Provenance.** Computed on 19 Nov 2026 by this project's own code (`goldlab`) from Dukascopy XAUUSD bid bars with the
recorded bid/ask spread: 5-minute bars 1 Jan 2025 - 3 May 2026 (94,329 bars, 343 trading days) and 1-hour bars 2019 - Sep 2026.
Times are New York time. Moves are in dollars per ounce on bid prices (at 0.01 lot = 1 oz, $1 move = $1).
All-in round-trip cost used: spread + $0.07/oz commission ($7/lot) + $0.10/oz slippage; the median is about $0.75-0.80/oz in this
data (Dukascopy's recorded spread, median $0.58-0.76; tighter raw-spread retail accounts would be cheaper).
This is a single 16-month sample from an unusually volatile bull-then-correction regime (median price 3,053 in 2025H1,
3,843 in 2025H2, 4,804 in 2026H1; median 5-minute true range $2.24, $2.80, $6.01). Treat every number as exploratory.

## What it shows (summary)

1. **Cost is a large fraction of a 5-minute bar.** All-in cost is 17-31% of the median 5-minute true range in liquid hours
   (London 03-08 NY: range $2.7-3.0, cost ~$0.75; New York 08-11: range $3.9-5.2, cost $0.76-0.89) and 57-62% in the
   17:00-19:00 rollover/Asia-open hours, when the spread roughly doubles (median $0.97-1.36, 90th percentile $1.66-3.20).
   On 15-minute bars cost is 10-17% of the median range in liquid hours. A $2-3 target on 5m gives away 25-40% to costs.
2. **5-minute returns are close to a random walk in every session.** Variance ratios 0.90-1.03 and lag-1 autocorrelation
   between -0.02 and +0.02. London hours lean slightly mean-reverting (VR 0.90-0.97); Asia and the New York morning
   lean very slightly trending (1.01-1.03). Nothing here is large enough to trade on its own.
3. **One window does not predict the next.** London morning vs New York morning: same sign 50%. First 30 or 60 minutes of
   New York vs the rest of the morning: 49-53%. Morning vs afternoon: 52%.
4. **Asian-range London breakout: a coin flip.** London broke the Asian high on 42% of days and the low on 28%; after the first
   break, London closed beyond the level 50% of the time with mean follow-through +$0.72 (median +$0.07); 66% of breaks
   closed back inside within three 5-minute bars. Small or large Asian ranges made no difference.
5. **Opening-range breakouts with full costs: indistinguishable from zero.** Best cases: US cash open 09:30 5-minute range
   traded in the range's own direction, +0.08R ±0.32 (95% CI), PF 1.04, 25% winners; London 03:00 30-minute range, PF 1.15 in
   dollars but -0.05R ±0.16. COMEX 08:20 15-minute range lost (PF 0.81). No variant's confidence interval excludes zero,
   and results flip sign between half-years.
6. **Chasing strength failed; fading weakness looked better but is not statistically reliable.** Buying a new 1-hour or
   4-hour high close had negative mean forward returns for the next hour. Buying RSI(14) < 25-30 dips in a 1-hour uptrend
   looked strong bar-by-bar (+$3.11 after 60 minutes, 65% winners) but that is inflated by overlapping bars: counted as
   separate episodes it is +$0.70 ±1.91 at 60 minutes (380 episodes), and with a 2-ATR stop and 2-ATR target net of $0.80
   cost the profit factor is 1.24 with average net +$0.90/oz. The mirror (selling RSI > 70 rallies in a 1-hour downtrend)
   lost (PF 0.66-0.69), consistent with the bull regime. By half-year the long side was +1.84, -0.29, +0.33 $/oz.
   On 1-hour bars 2019-2026, buying 1h RSI < 30 in a daily uptrend had no edge over baseline drift (+0.016% vs +0.023% per 8h).
7. **Other common signals:** Bollinger-band fades, 3-ATR VWAP fades, EMA20 trend pullbacks, previous-day high/low
   sweep-and-reclaim and big-bar continuation all had mean forward moves smaller than the cost, or of the wrong sign.
8. **Earlier engine backtests on the same data (full strategy cards, realistic costs):** Asian-range London breakout 15m
   PF 0.80 (0.82 at zero cost, 128 trades); New York COMEX ORB 5m PF 0.96 (1.00 at zero cost, 324 trades); 1h RSI(2) pullback
   with 200-SMA filter 2019-2026 PF 0.82 (1.09 at zero cost, 2,066 trades); 1h Asia-session long drift PF 0.98 (1.12 at zero cost).

**Implication for choosing a method.** On this data no simple 5-minute rule shows a statistically reliable edge after
realistic costs. Any chosen method should be treated as a hypothesis to test at minimum size, should take few trades with
targets several times the cost (cost under ~10% of the target), should avoid 16:00-19:00 New York, and should be judged over
100+ trades. The least-bad family in this sample was buying deep pullbacks in the direction of the higher-timeframe trend
during London and New York hours; breakout chasing was the worst.

## Raw output

```
bars 94,329  2025-01-01 18:00:00-05:00 .. 2026-05-03 19:55:00-04:00  median close 3476
round-trip cost per oz = spread + 0.17 (commission 0.07 + slippage 0.10)

A. By New York hour: median 5m and 15m true range ($/oz), median and 90th pct spread, all-in cost, cost as % of median range
      tr5_med  tr15_med  spread_med  spread_p90  cost  cost_pct_tr5  cost_pct_tr15
hour                                                                              
0        2.35      4.08        0.63        0.83  0.80          34.0           20.0
1        2.94      5.36        0.64        0.86  0.81          28.0           15.0
2        3.14      5.69        0.62        0.83  0.78          25.0           14.0
3        3.30      5.82        0.58        0.79  0.76          23.0           13.0
4        2.92      5.16        0.58        0.80  0.75          26.0           15.0
5        2.79      5.01        0.58        0.79  0.75          27.0           15.0
6        2.66      4.81        0.58        0.80  0.75          28.0           16.0
7        2.90      5.13        0.58        0.80  0.75          26.0           15.0
8        4.28      7.61        0.59        0.82  0.76          18.0           10.0
9        5.19      9.13        0.72        1.17  0.89          17.0           10.0
10       5.06      9.00        0.70        1.20  0.87          17.0           10.0
11       3.86      6.81        0.59        0.83  0.76          20.0           11.0
12       3.10      5.45        0.58        0.79  0.75          24.0           14.0
13       2.75      4.91        0.58        0.86  0.76          27.0           15.0
14       2.43      4.39        0.59        0.84  0.76          31.0           17.0
15       2.50      4.45        0.56        0.79  0.73          29.0           16.0
16       1.85      3.28        0.97        1.66  1.14          62.0           35.0
18       2.67      4.81        1.36        3.20  1.53          57.0           32.0
19       2.50      4.44        0.78        1.17  0.95          38.0           21.0
20       3.47      6.21        0.63        0.91  0.80          23.0           13.0
21       3.77      6.82        0.64        0.90  0.82          22.0           12.0
22       2.96      5.34        0.64        0.86  0.82          28.0           15.0
23       2.42      4.24        0.63        0.84  0.80          33.0           19.0

Median 5m TR / median spread by half-year: 2025H1: TR 2.24, spread 0.59, close 3053; 2025H2: TR 2.80, spread 0.60, close 3843; 2026H1: TR 6.01, spread 0.76, close 4804

B. Variance ratio of k-bar vs 1-bar 5m log returns by session (VR<1 = mean-reverting, >1 = trending); lag-1 autocorr
  Asia 18-02: ac1 +0.024, VR3 1.03, VR6 1.03, VR12 1.02
  London 03-08: ac1 +0.008, VR3 0.97, VR6 0.91, VR12 0.90
  NY AM 08-12: ac1 +0.010, VR3 1.01, VR6 1.03, VR12 1.02
  NY PM 12-17: ac1 -0.017, VR3 0.98, VR6 0.98, VR12 0.98

C. Does one window predict the next? (same-sign %, mean $ move of the later window in the earlier window's direction)
  london -> ny_am: same sign 50% (n=343), mean follow-through +1.78 $/oz, corr +0.05
  ny_first30 -> ny_rest: same sign 49% (n=343), mean follow-through +0.70 $/oz, corr +0.16
  ny_first60 -> ny_rest: same sign 53% (n=343), mean follow-through +2.42 $/oz, corr +0.08
  ny_am -> ny_pm: same sign 52% (n=343), mean follow-through +0.19 $/oz, corr -0.07
  cash30 -> cash_rest: same sign 47% (n=343), mean follow-through +1.87 $/oz, corr +0.15

D. Asian range (18:00-03:00 NY) and what London (03:00-08:00 NY) does with it
  days 343; median Asian range $36.9; London breaks high 42%, low 28%, both 2%, neither 32%
  after the FIRST break: London closes beyond the level 50% of days; mean follow-through to 08:00 +0.72 $/oz (median +0.07); mean max favourable 14.2, mean max adverse 12.9
  a 5m close back inside within 3 bars of the break: 66% of breaks; follow-through to 12:00 NY: mean +2.41, win 52%
  small Asian range (bottom third): n=78, London holds the break 49%, mean follow-through +0.31
  large Asian range (top third): n=78, London holds the break 46%, mean follow-through +0.47

E. Opening range breakout follow-through (first break of the range; move measured from the range edge to the exit time, in the break direction)
  COMEX open 08:20, 15-min range, exit 12:00: median range $9.4
    all first breaks: n=342, hold-to-exit win 49%, mean +0.61; with stop at far side of range: win 31%, mean -0.72 $/oz (-0.06 R), stopped 65%, after ~0.80 cost -1.52
    break in direction of the opening range's own move: n=249, hold-to-exit win 50%, mean +0.79; with stop at far side of range: win 31%, mean -0.70 $/oz (-0.06 R), stopped 65%, after ~0.80 cost -1.50
    break against the opening range's move: n=93, hold-to-exit win 47%, mean +0.15; with stop at far side of range: win 32%, mean -0.76 $/oz (-0.07 R), stopped 63%, after ~0.80 cost -1.56
  COMEX open 08:20, 30-min range, exit 13:30: median range $11.9
    all first breaks: n=341, hold-to-exit win 49%, mean -1.95; with stop at far side of range: win 36%, mean -1.57 $/oz (-0.10 R), stopped 56%, after ~0.80 cost -2.37
    break in direction of the opening range's own move: n=239, hold-to-exit win 48%, mean -1.13; with stop at far side of range: win 37%, mean -1.85 $/oz (-0.11 R), stopped 56%, after ~0.80 cost -2.66
    break against the opening range's move: n=102, hold-to-exit win 50%, mean -3.86; with stop at far side of range: win 35%, mean -0.91 $/oz (-0.06 R), stopped 56%, after ~0.80 cost -1.71
  US cash open 09:30, 15-min range, exit 16:00: median range $11.5
    all first breaks: n=342, hold-to-exit win 53%, mean +1.08; with stop at far side of range: win 39%, mean +1.25 $/oz (+0.08 R), stopped 55%, after ~0.98 cost +0.27
    break in direction of the opening range's own move: n=246, hold-to-exit win 50%, mean +0.40; with stop at far side of range: win 37%, mean -0.12 $/oz (-0.01 R), stopped 56%, after ~0.96 cost -1.08
    break against the opening range's move: n=96, hold-to-exit win 59%, mean +2.83; with stop at far side of range: win 43%, mean +4.76 $/oz (+0.33 R), stopped 52%, after ~1.04 cost +3.72
  US cash open 09:30, 5-min range, exit 16:00: median range $7.1
    all first breaks: n=343, hold-to-exit win 49%, mean +2.16; with stop at far side of range: win 25%, mean +1.44 $/oz (+0.16 R), stopped 73%, after ~0.98 cost +0.46
    break in direction of the opening range's own move: n=252, hold-to-exit win 50%, mean +2.95; with stop at far side of range: win 26%, mean +1.73 $/oz (+0.20 R), stopped 72%, after ~0.97 cost +0.76
    break against the opening range's move: n=91, hold-to-exit win 48%, mean -0.04; with stop at far side of range: win 23%, mean +0.65 $/oz (+0.07 R), stopped 77%, after ~1.02 cost -0.37
  London open 03:00, 30-min range, exit 08:00: median range $8.5
    all first breaks: n=341, hold-to-exit win 50%, mean +2.05; with stop at far side of range: win 39%, mean +1.70 $/oz (+0.15 R), stopped 49%, after ~0.79 cost +0.91
    break in direction of the opening range's own move: n=239, hold-to-exit win 48%, mean +1.23; with stop at far side of range: win 37%, mean +1.23 $/oz (+0.11 R), stopped 52%, after ~0.79 cost +0.44
    break against the opening range's move: n=102, hold-to-exit win 57%, mean +3.99; with stop at far side of range: win 44%, mean +2.82 $/oz (+0.24 R), stopped 41%, after ~0.79 cost +2.03

F. What happens after common 5m 'signals' (mean forward move in the stated direction, $/oz, before cost; median all-in cost is ~0.80)
  RSI(14) < 25 -> buy (fade): n=1313; +15m +0.13 (win 56%), +30m +0.87 (win 57%), +60m +2.74 (win 59%), +120m +5.90 (win 64%)
  RSI(14) > 75 -> sell (fade): n=2050; +15m -0.45 (win 47%), +30m -0.87 (win 48%), +60m -1.54 (win 45%), +120m -2.39 (win 45%)
  RSI(14) < 25 in a 1h uptrend -> buy: n=430; +15m +0.15 (win 59%), +30m +0.67 (win 61%), +60m +3.11 (win 65%), +120m +5.36 (win 68%)
  RSI(14) > 75 in a 1h downtrend -> sell: n=345; +15m +0.91 (win 55%), +30m +1.34 (win 57%), +60m +1.73 (win 53%), +120m +1.99 (win 60%)
  RSI(2) < 5 in a 1h uptrend -> buy: n=3365; +15m +0.19 (win 55%), +30m +0.23 (win 55%), +60m +0.45 (win 55%), +120m +1.21 (win 57%)
  RSI(2) > 95 in a 1h downtrend -> sell: n=2520; +15m +0.03 (win 51%), +30m -0.02 (win 50%), +60m +0.26 (win 49%), +120m +0.07 (win 47%)
  close below lower Bollinger(20,2) -> buy (fade): n=5623; +15m +0.23 (win 56%), +30m +0.24 (win 55%), +60m +0.29 (win 55%), +120m +0.98 (win 56%)
  close above upper Bollinger(20,2) -> sell (fade): n=5877; +15m -0.12 (win 50%), +30m -0.21 (win 50%), +60m -0.63 (win 48%), +120m -1.71 (win 47%)
  close below lower Bollinger in 1h uptrend -> buy: n=3169; +15m +0.24 (win 56%), +30m +0.26 (win 56%), +60m +0.33 (win 55%), +120m +1.04 (win 57%)
  close above upper Bollinger in 1h downtrend -> sell: n=2021; +15m -0.16 (win 52%), +30m -0.17 (win 51%), +60m -0.37 (win 50%), +120m -1.62 (win 48%)
  big up bar (TR > 3 ATR) -> buy (continuation): n=362; +15m +0.09 (win 50%), +30m +0.72 (win 51%), +60m +1.86 (win 52%), +120m +3.27 (win 54%)
  big down bar (TR > 3 ATR) -> sell (continuation): n=517; +15m -0.55 (win 41%), +30m -0.85 (win 39%), +60m -2.19 (win 41%), +120m -2.62 (win 39%)
  new 1h (12-bar) high close, liquid hours -> buy (momentum): n=4485; +15m -0.19 (win 48%), +30m -0.23 (win 49%), +60m -0.39 (win 50%), +120m +0.36 (win 52%)
  new 1h low close, liquid hours -> sell (momentum): n=3368; +15m -0.33 (win 44%), +30m -0.35 (win 44%), +60m -0.48 (win 43%), +120m -1.12 (win 43%)
  new 4h (48-bar) high close, liquid hours -> buy: n=2162; +15m -0.28 (win 47%), +30m -0.24 (win 49%), +60m -0.27 (win 51%), +120m +1.20 (win 54%)
  new 4h low close, liquid hours -> sell: n=1311; +15m -0.34 (win 44%), +30m +0.07 (win 44%), +60m -0.25 (win 43%), +120m -1.38 (win 43%)
  1h uptrend, EMA20>EMA50, bar dips to EMA20 and closes back above, bullish -> buy (trend pullback): n=2603; +15m -0.16 (win 50%), +30m -0.14 (win 51%), +60m -0.21 (win 51%), +120m -0.07 (win 52%)
  mirror in 1h downtrend -> sell: n=1547; +15m +0.32 (win 49%), +30m +0.65 (win 51%), +60m +0.72 (win 50%), +120m +0.32 (win 46%)
  price > 3 ATR(5m) above session VWAP -> sell (fade to VWAP): n=23759; +15m -0.06 (win 48%), +30m -0.14 (win 48%), +60m -0.38 (win 48%), +120m -0.84 (win 47%)
  price > 3 ATR below session VWAP -> buy (fade): n=14350; +15m +0.01 (win 52%), +30m +0.02 (win 53%), +60m +0.07 (win 54%), +120m +0.15 (win 56%)
  price above VWAP & 1h uptrend & pullback touches VWAP then closes above -> buy: n=1089; +15m -0.36 (win 49%), +30m -0.97 (win 48%), +60m -1.24 (win 50%), +120m -0.70 (win 54%)
  sweep above previous-day high, 5m close back below -> sell (sweep and reclaim): n=583; +15m +0.14 (win 49%), +30m -0.15 (win 46%), +60m -0.76 (win 46%), +120m -1.01 (win 49%)
  sweep below previous-day low, close back above -> buy: n=482; +15m -0.72 (win 50%), +30m -0.04 (win 55%), +60m -0.68 (win 54%), +120m -2.18 (win 50%)
  5m close above previous-day high (first close) -> buy (breakout): n=727; +15m +0.37 (win 51%), +30m +0.50 (win 52%), +60m +1.05 (win 52%), +120m +1.11 (win 50%)
  5m close below previous-day low -> sell (breakout): n=451; +15m -0.26 (win 46%), +30m +0.11 (win 47%), +60m +1.12 (win 46%), +120m +3.13 (win 49%)

All moves are in $/oz on bid prices; at 0.01 lot (1 oz) $1 = $1. A signal needs a mean forward move well above the all-in cost to be tradable.

G. Baseline drift (unconditional mean forward move, $/oz): +30m +0.13, +60m +0.25, +120m +0.51; in a 1h uptrend: +60m +0.38, +120m +0.72; in a 1h downtrend: +60m +0.05, +120m +0.18

H. The same signals counted as separate episodes, with 95% confidence intervals on the mean
  RSI(14) < 25 in a 1h uptrend -> buy: 158 separate episodes (first bar, at least 1h apart); +30m +0.09 ±3.38 (win 59%), +60m +0.83 ±3.25 (win 62%), +120m +1.41 ±3.69 (win 66%)
  RSI(14) < 30 in a 1h uptrend -> buy: 380 separate episodes (first bar, at least 1h apart); +30m +0.01 ±1.86 (win 60%), +60m +0.70 ±1.91 (win 61%), +120m +0.55 ±2.12 (win 59%)
  RSI(14) > 75 in a 1h downtrend -> sell: 104 separate episodes (first bar, at least 1h apart); +30m +0.71 ±1.69 (win 57%), +60m +0.77 ±2.24 (win 46%), +120m -1.42 ±3.42 (win 48%)
  RSI(14) > 70 in a 1h downtrend -> sell: 256 separate episodes (first bar, at least 1h apart); +30m -0.94 ±1.18 (win 45%), +60m -0.90 ±1.48 (win 47%), +120m -2.76 ±2.46 (win 46%)
  RSI(14) < 25 in a 1h DOWNtrend -> buy (counter-trend): 210 separate episodes (first bar, at least 1h apart); +30m -1.65 ±2.39 (win 54%), +60m -0.59 ±2.51 (win 52%), +120m +0.77 ±3.21 (win 59%)
  RSI(14) > 75 in a 1h UPtrend -> sell (counter-trend): 325 separate episodes (first bar, at least 1h apart); +30m -0.96 ±1.19 (win 47%), +60m -2.11 ±1.54 (win 45%), +120m -4.21 ±2.18 (win 46%)

I. Stability of 'RSI(14) < 30 in a 1h uptrend -> buy' and its mirror, +60m, by half-year and by session
  buy dip in uptrend: 2025H1: n=150, mean +1.84, win 63%; 2025H2: n=140, mean -0.29, win 56%; 2026H1: n=90, mean +0.33, win 67%
    by session: Asia 18-03: n=167, mean -0.44, win 57%; London 03-08: n=75, mean +4.16, win 64%; NY 08-12: n=87, mean -1.25, win 63%; NY PM 12-17: n=51, mean +2.68, win 67%
  sell rally in downtrend: 2025H1: n=95, mean -1.31, win 46%; 2025H2: n=86, mean -0.15, win 48%; 2026H1: n=75, mean -1.25, win 48%
    by session: Asia 18-03: n=127, mean -0.64, win 49%; London 03-08: n=53, mean -1.46, win 45%; NY 08-12: n=42, mean -0.56, win 40%; NY PM 12-17: n=34, mean -1.44, win 53%

J. Bracket outcomes from the signal bar's close: stop S x ATR(14, 5m), target T x ATR, time stop 2h; stop assumed hit first if both in one bar. Net of a fixed $0.80/oz cost.
  stop 1.5 ATR / target 1.5 ATR: buy dip in 1h uptrend (RSI<30): n=380, win 55%, avg +0.25 $/oz (-0.09R), PF 1.08, avg risk $6.6 | sell rally in 1h downtrend (RSI>70): n=256, win 46%, avg -1.50 $/oz (-0.23R), PF 0.66, avg risk $7.4
  stop 1.5 ATR / target 3.0 ATR: buy dip in 1h uptrend (RSI<30): n=380, win 40%, avg +0.21 $/oz (-0.07R), PF 1.05, avg risk $6.6 | sell rally in 1h downtrend (RSI>70): n=256, win 30%, avg -2.33 $/oz (-0.35R), PF 0.58, avg risk $7.4
  stop 2.0 ATR / target 2.0 ATR: buy dip in 1h uptrend (RSI<30): n=380, win 56%, avg +0.90 $/oz (-0.01R), PF 1.24, avg risk $8.7 | sell rally in 1h downtrend (RSI>70): n=256, win 46%, avg -1.65 $/oz (-0.17R), PF 0.69, avg risk $9.8
  stop 2.0 ATR / target 4.0 ATR: buy dip in 1h uptrend (RSI<30): n=380, win 44%, avg -0.12 $/oz (-0.03R), PF 0.97, avg risk $8.7 | sell rally in 1h downtrend (RSI>70): n=256, win 34%, avg -2.31 $/oz (-0.25R), PF 0.63, avg risk $9.8
  stop 3.0 ATR / target 3.0 ATR: buy dip in 1h uptrend (RSI<30): n=380, win 55%, avg -0.07 $/oz (-0.01R), PF 0.99, avg risk $13.1 | sell rally in 1h downtrend (RSI>70): n=256, win 44%, avg -2.23 $/oz (-0.18R), PF 0.66, avg risk $14.7

K. Long-history cross-check, one timeframe up: 1h RSI(14) extremes in the direction of the DAILY trend (close vs 50-day EMA), 2019 - Sep 2026, forward 8h move as % of price, separate episodes
  buy 1h RSI<30 in daily uptrend: 2019: n=26, -0.114%; 2020: n=34, -0.026%; 2021: n=22, -0.090%; 2022: n=19, -0.024%; 2023: n=33, +0.099%; 2024: n=41, +0.033%; 2025: n=39, +0.106%; 2026: n=21, +0.056% | all: n=235, mean +0.016%, win 53% (baseline 8h drift +0.023%)
  sell 1h RSI>70 in daily downtrend: 2019: n=19, -0.056%; 2020: n=17, -0.098%; 2021: n=37, -0.002%; 2022: n=25, +0.092%; 2023: n=27, -0.153%; 2024: n=15, +0.107%; 2025: n=6, +0.148%; 2026: n=20, +0.113% | all: n=166, mean +0.001%, win 51% (baseline 8h drift +0.023%)

L. Opening-range breakouts with full costs (buy at ask, spread on exit for shorts, $0.05 slippage each side, $0.07/oz commission), stop at the far side of the range unless stated, exit at the stated time
  US cash open 09:30 NY, 5-min range, hold to 16:00 | all: n=343, win 24%, mean +0.013R ±0.257 (95% CI), +0.26 $/oz, PF 1.04, avg risk $9.0; by half-year: 2025H1 -0.14R (n=127), 2025H2 +0.10R (n=131), 2026H1 +0.10R (n=85)
      with the opening range's direction: n=252, win 25%, mean +0.078R ±0.319 (95% CI), +0.28 $/oz, PF 1.04, avg risk $8.7; by half-year: 2025H1 -0.11R (n=101), 2025H2 +0.18R (n=93), 2026H1 +0.24R (n=58)
      against the opening range's direction: n=91, win 22%, mean -0.165R ±0.395 (95% CI), +0.19 $/oz, PF 1.03, avg risk $9.8; by half-year: 2025H1 -0.26R (n=26), 2025H2 -0.08R (n=38), 2026H1 -0.19R (n=27)
  US cash open 09:30, 15-min range, hold to 16:00 | all: n=342, win 37%, mean +0.006R ±0.168 (95% CI), +0.30 $/oz, PF 1.04, avg risk $14.8; by half-year: 2025H1 +0.03R (n=127), 2025H2 -0.04R (n=130), 2026H1 +0.04R (n=85)
      with the opening range's direction: n=246, win 35%, mean -0.032R ±0.198 (95% CI), -1.12 $/oz, PF 0.87, avg risk $14.9; by half-year: 2025H1 +0.02R (n=95), 2025H2 -0.08R (n=92), 2026H1 -0.04R (n=59)
      against the opening range's direction: n=96, win 41%, mean +0.104R ±0.314 (95% CI), +3.93 $/oz, PF 1.54, avg risk $14.6; by half-year: 2025H1 +0.06R (n=32), 2025H2 +0.06R (n=38), 2026H1 +0.22R (n=26)
  COMEX open 08:20, 15-min range, hold to 12:00 | all: n=342, win 29%, mean -0.071R ±0.193 (95% CI), -1.54 $/oz, PF 0.81, avg risk $11.6; by half-year: 2025H1 -0.23R (n=127), 2025H2 +0.26R (n=131), 2026H1 -0.35R (n=84)
      with the opening range's direction: n=249, win 29%, mean -0.049R ±0.237 (95% CI), -1.59 $/oz, PF 0.81, avg risk $11.6; by half-year: 2025H1 -0.22R (n=91), 2025H2 +0.29R (n=104), 2026H1 -0.42R (n=54)
      against the opening range's direction: n=93, win 30%, mean -0.129R ±0.319 (95% CI), -1.38 $/oz, PF 0.82, avg risk $11.6; by half-year: 2025H1 -0.24R (n=36), 2025H2 +0.14R (n=27), 2026H1 -0.23R (n=30)
  London open 03:00 NY, 30-min range, hold to 08:00 | all: n=341, win 37%, mean -0.051R ±0.158 (95% CI), +0.84 $/oz, PF 1.15, avg risk $11.4; by half-year: 2025H1 -0.05R (n=126), 2025H2 -0.05R (n=130), 2026H1 -0.05R (n=85)
      with the opening range's direction: n=239, win 37%, mean -0.083R ±0.184 (95% CI), +0.49 $/oz, PF 1.09, avg risk $11.3; by half-year: 2025H1 -0.20R (n=95), 2025H2 +0.05R (n=87), 2026H1 -0.10R (n=57)
      against the opening range's direction: n=102, win 38%, mean +0.023R ±0.305 (95% CI), +1.69 $/oz, PF 1.31, avg risk $11.6; by half-year: 2025H1 +0.41R (n=31), 2025H2 -0.27R (n=43), 2026H1 +0.04R (n=28)
  London open 03:00 NY, 15-min range, hold to 08:00 | all: n=342, win 29%, mean -0.082R ±0.204 (95% CI), +0.49 $/oz, PF 1.09, avg risk $8.6; by half-year: 2025H1 -0.09R (n=126), 2025H2 -0.08R (n=131), 2026H1 -0.07R (n=85)
      with the opening range's direction: n=258, win 31%, mean -0.123R ±0.205 (95% CI), +0.44 $/oz, PF 1.08, avg risk $8.7; by half-year: 2025H1 -0.08R (n=98), 2025H2 -0.07R (n=97), 2026H1 -0.27R (n=63)
      against the opening range's direction: n=84, win 25%, mean +0.045R ±0.544 (95% CI), +0.65 $/oz, PF 1.12, avg risk $8.2; by half-year: 2025H1 -0.10R (n=28), 2025H2 -0.13R (n=34), 2026H1 +0.51R (n=22)
  Asia/Tokyo 19:00 NY, 30-min range, hold to 02:00 | all: n=336, win 38%, mean -0.138R ±0.122 (95% CI), +0.51 $/oz, PF 1.10, avg risk $14.3; by half-year: 2025H1 -0.24R (n=127), 2025H2 -0.24R (n=128), 2026H1 +0.18R (n=81)
      with the opening range's direction: n=231, win 35%, mean -0.193R ±0.146 (95% CI), -0.55 $/oz, PF 0.91, avg risk $14.2; by half-year: 2025H1 -0.24R (n=84), 2025H2 -0.36R (n=92), 2026H1 +0.16R (n=55)
      against the opening range's direction: n=105, win 43%, mean -0.018R ±0.219 (95% CI), +2.83 $/oz, PF 1.69, avg risk $14.6; by half-year: 2025H1 -0.23R (n=43), 2025H2 +0.06R (n=36), 2026H1 +0.23R (n=26)
  US cash open 09:30, 5-min range, target 2R | all: n=343, win 37%, mean -0.006R ±0.151 (95% CI), +0.31 $/oz, PF 1.05, avg risk $9.0; by half-year: 2025H1 -0.07R (n=127), 2025H2 -0.07R (n=131), 2026H1 +0.19R (n=85)
  London open 03:00, 30-min range, target 1R | all: n=341, win 51%, mean -0.033R ±0.100 (95% CI), +0.57 $/oz, PF 1.12, avg risk $11.4; by half-year: 2025H1 +0.00R (n=126), 2025H2 -0.00R (n=130), 2026H1 -0.14R (n=85)
  London open 03:00, 30-min range, stop at mid-range | all: n=341, win 19%, mean -0.235R ±0.252 (95% CI), -0.34 $/oz, PF 0.93, avg risk $5.7; by half-year: 2025H1 -0.31R (n=126), 2025H2 -0.19R (n=130), 2026H1 -0.19R (n=85)
```
