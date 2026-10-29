# Research log

Each entry follows the loop in `CLAUDE.md`: result → why → research →
suggestions → decision.

---

## Run 1: baseline z-score mean reversion (no filter, no sizing)

**Setup:** SPY daily bars, 2005-01-03 to 2026-10-28. 20-day z-score; buy at
z < −2, sell at z ≥ 0, stop below −3.5, 10-day time stop. Full position.
Costs: $0.005/share ($1 minimum) commission plus 2 bps slippage per side.
Trades fill at the next day's open.

| Metric (after costs) | Mean reversion | Buy & hold |
|---|---|---|
| Net profit | $35,013 | $852,259 |
| Sharpe ratio | 0.18 | 0.64 |
| CAGR | 1.39% | 10.90% |
| Max drawdown | −32.3% | −55.2% |
| Trades | 103 | — |
| Win rate | 63.1% | — |
| Costs paid | $5,205 | $26 |

**Verdict: FAIL.** Both targets were missed by a wide margin.

### Why it failed
1. **Mostly in cash.** The bot was invested only 13.7% of days. Its Sharpe
   while invested is 0.59, about the same as buy-and-hold, but the long idle
   stretches drag the full-period Sharpe down to 0.18 and keep net profit tiny.
2. **Buying dips in downtrends has no edge.** Entries with price below the
   200-day average: 37 trades, −$1,149 total. Entries above it: 66 trades,
   +$36,161, 68% win rate.
3. **Crash regimes cause the worst losses.** Entries with 20-day volatility
   above 40%: 4 trades, −$10,704, 25% win rate. The worst trades are in
   2008, 2009, Feb 2020 and April 2025.
4. **The 10-day time stop sells near the bottom.** 44 time exits lost $100,991
   in total. On average SPY rose +1.31% over the 10 days *after* those sales,
   so the bot sold too early and missed the rebound.
5. The −3.5 stop almost never fires (2 times), so it isn't the main problem.

### Research
- Regime-switching HMMs flag turbulent, crash-prone periods well ahead of the
  worst losses (Daniel, Jagannathan & Kim, NBER w18169), which supports gating
  entries on regime.
- HMM regime gating beat buy-and-hold Sharpe in 3 of 5 Asian equity indices,
  but failed when the model got stuck misreading a structural break as a bear
  regime (PMR journal study). Lesson: compare against a simpler filter.
- HMMs can flip back and forth between states, so a persistence or
  probability threshold is needed (Rainmaker S&P 500 HMM write-up).
- A 200-day-average trend gate is a well-known, simple regime filter for
  mean reversion in indices (StockCharts SystemTrader studies).

### Suggested improvements (ranked)
1. **Regime filter.** Build the planned HMM (calm / trending / crisis) and
   test it *against* a simple 200-day-average filter. Keep the HMM only if it
   beats the simple one.
2. **Rethink the time stop.** Test longer holds or no time stop. Risk:
   overfitting, so confirm in walk-forward.
3. **Low exposure** gets addressed later by sizing (step 6) and possibly more
   assets or pairs (v2).

**Decision:** pending owner approval.

**Decision (run 1):** superseded. The owner switched the project to a
**day-trading** bot. Run 1's lesson (dips in bad regimes lose) carries over.

---

## Run 2: day-trading baseline, VWAP z-score mean reversion (5-minute bars)

**Setup:** SPY 5-minute bars from Alpaca (full-market SIP feed), 2016-01-04 to
2026-10-27: 211,390 bars over 2,720 sessions, trimmed to the official calendar
(21 half-days). z = (close − VWAP) / volume-weighted σ, both reset daily. Buy at
z < −2 (10:00–15:30 only), sell at z ≥ 0, stop below −3.5, 1-hour time stop,
always flat at the open of the day's last bar. Full position. Costs:
$0.005/share ($1 minimum) commission plus 2 bps slippage per side. Fills at the
next bar's open.

| Metric (after costs) | VWAP reversion | Buy & hold |
|---|---|---|
| Net profit | −$72,934 | +$284,208 |
| Sharpe ratio | −2.61 | 0.79 |
| CAGR | −11.43% | 13.24% |
| Max drawdown | −73.5% | −34.2% |
| Trades | 2,408 | — |
| Win rate | 48.8% | — |
| Costs paid | $62,696 | $22 |

**Verdict: FAIL.**

### Why it failed
1. **There's no reversion to capture.** After price crosses below −2σ from
   VWAP, SPY's average move over the next 5, 15 and 30 minutes is −0.08, −0.08
   and −0.28 basis points. That's zero, and *worse* than an average bar. After
   +2σ crossings, the next moves are slightly *positive*. If anything, SPY
   drifts the same direction (momentum), not back.
2. **It loses even with zero costs.** With $0 commission and 0 slippage: net
   −$21,179, Sharpe −0.47. Costs make it much worse:

   | Commission | Slippage/side | Net profit | Sharpe |
   |---|---|---|---|
   | $0 | 0 bp | −$21,179 | −0.47 |
   | $0 | 0.5 bp | −$37,972 | −0.95 |
   | $0 | 1 bp | −$51,216 | −1.44 |
   | $0.005/sh | 1 bp | −$55,365 | −1.62 |
   | $0.005/sh | 2 bp | −$72,934 | −2.61 |

3. **Costs dominate.** Average cost is $26 per trade, against an average gross
   result of −$4. A winning "target" exit averages only +$103.
4. **No regime rescues it.** It lost in **every** year (2016–2026), **every**
   entry hour (10:00–15:00), every volatility bucket (<12% to >30%), and every
   "how far from the open" bucket. A regime filter (HMM) can't help when no
   regime has an edge, because it can only choose *when* to trade.
5. Time exits (1,427 of them) lost $132,723. Price usually didn't come back
   within an hour.

### Research
- **SPY intraday moves tend to continue, not revert.** Gao, Han, Li & Zhou,
  *Market Intraday Momentum* (Journal of Financial Economics, 2018): the first
  half-hour return predicts the last half-hour return in SPY (1993–2013), more
  strongly on volatile and high-volume days.
- **A documented SPY day-trading edge is momentum.** Zarattini, Aziz & Barbon,
  *Beat the Market: An Effective Intraday Momentum Strategy for SPY* (Swiss
  Finance Institute WP 24-97): trades breakouts from a "noise area" around the
  open (from the 14-day average intraday move), with trailing stops. They report
  about 19.6% a year and Sharpe 1.33 net of costs, 2007–2024. These are the
  authors' own numbers and need independent replication.
- **VWAP fades usually die on costs.** A QuantConnect reproduction on QQQ finds
  break-even below about 1 bp round trip, under real spreads. VWAP comes from
  execution research, not signal research.

### Suggested improvements (ranked)
1. **Flip to intraday momentum on SPY** (noise-area breakout, per Zarattini et
   al.). This has the strongest evidence, and our own data points the same way.
   Trade-off: it's no longer a mean-reversion bot. Risk: replicating published
   results that may be overfit, so verify with walk-forward.
2. **Keep mean reversion, but trade something that reverts.** For example, an
   intraday spread between two closely related assets (pairs), or individual
   stocks' short-term reversal. Risk: costs on single stocks are higher, and
   this needs more data and work.
3. **Keep the VWAP fade with much stricter entries** (e.g. z < −3, fewer
   trades). Not recommended: the zero-cost result is already negative, so this
   would mostly be curve-fitting.
4. **Not recommended now:** an HMM filter on this signal. No subgroup was
   profitable, so a filter has nothing good to select.

**Decision:** the owner approved option 1, intraday momentum, and authorized
autonomous iteration on branches, with nothing merged without review.

---

## Run 3: intraday momentum + volatility sizing + HMM regime + Kelly

Branches, stacked: `feature/intraday-momentum` → `experiment/vol-sizing` →
`experiment/hmm-regime` → `experiment/kelly`.

### Method changes (apply to everything below)
- **Locked holdout.** Development and tuning used only 2016-01-04 to
  2024-10-31 ("dev"). 2024-11-01 to 2026-10-27 (497 days) was untouched until
  the final test, run once.
- **Costs measured, not guessed.** 360 SPY quotes from Alpaca (SIP), sampled at
  6 times of day on 60 random days: the median spread is 1 cent, a
  **half-spread of 0.18 bp** (95th percentile 0.30 bp), with hundreds of shares
  at the top of book. New default "realistic" costs: 0.5 bp slippage per side
  (about 2.8x the measured half-spread) plus $0.0035/share commission
  ($0.35 minimum). The old profile (2 bp + $0.005/share) is always reported
  as a "stress" test.
- **Engine fixes:**
  1. It now holds shares until the target changes. Before, it re-sized every
     bar, which cost about 3.4 orders per round trip and $2.5k of fees on the
     baseline.
  2. Short selling, and long↔short flips as two orders.
  3. A leverage cap on the *combined* size after all scales, for shorts too.
     This bug was found mid-run: vol-target × Kelly reached 2.6x under a 2x
     "cap". All results below are after the fix.

### Strategy
Noise-area breakout from Zarattini, Aziz & Barbon (2024), implemented per the
paper:
- band = average |move from open| at each time of day over the previous 14
  days, adjusted for the overnight gap
- decisions only at :00 and :30
- go long above the upper band, short below the lower band
- trailing stop at max(upper band, VWAP) for longs, min(lower band, VWAP) for
  shorts
- flat at the close

### Additions tested
- **Volatility targeting** (paper): size = min(cap, 2% / σ of the last 14
  daily returns).
- **HMM regime filter**: a 2-state Gaussian HMM on the 5-day average intraday
  *variance ratio* (trendiness). Refit every 21 days on the previous 756 days,
  using filtered (forward) probabilities pushed one day ahead. The bot trades
  only when P(trending) > 0.5.
  - The first version also used realized vol. Its "trending" state just
    tracked volatility (corr 0.60 with vol, 0.02 with trendiness) and *hurt*
    results (Sharpe 0.60→0.43), so it was dropped.
- **Fractional Kelly**: f* = μ/σ² from the strategy's own previous 252 daily
  returns at unit size, half Kelly, clipped to [0, cap].

### Dev results (2016-01 to 2024-10, realistic costs; stress in brackets)

| Variant | Net profit | Sharpe | Max DD | Stress net / Sharpe |
|---|---|---|---|---|
| Buy & hold SPY | $183,865 | 0.74 | 34.2% | — |
| A momentum baseline | $43,920 | 0.65 | 13.5% | −$19,029 / −0.32 |
| B + vol-target (1x) | $54,902 | 0.83 | 12.3% | −$12,250 / −0.21 |
| C + HMM only | $40,484 | 0.72 | 12.7% | −$295 / 0.02 |
| D vol-target + HMM | $50,886 | 0.95 | 11.1% | $7,670 / 0.19 |
| E D + ½ Kelly, cap 1x | $46,663 | 0.99 | 7.0% | $10,557 / 0.29 |
| **F D + ½ Kelly, cap 2x** | **$120,669** | **1.05** | 12.4% | $20,922 / 0.30 |
| G D + ½ Kelly, cap 4x | $366,819 | 1.09 | 18.8% | $13,200 / 0.17 |

Also tried, not kept:
- a simple variance-ratio rank filter (Sharpe 0.55–0.80): the HMM beat it, so
  the HMM was kept per the "prefer simpler unless clearly better" rule
- an HMM size-scaling mode instead of filtering (slightly worse)
- quarter Kelly (worse)
- volatility filters: no-lookahead tests showed no consistent pattern, so none
  was used

**Robustness (F, each parameter ±20%):** Sharpe ranged 0.85–1.10 and net
profit $88k–$129k. All were profitable at realistic costs. The weakest was
band width 0.8x (0.85). Kelly fraction barely matters: Kelly is usually at the
cap, so in practice it acts as "use the cap unless the past year lost money".
(It turned trading off for all of 2017, which the unsized strategy lost.)

**F year by year (dev):** 2016 −10.8%, 2017 0% (Kelly off), 2018 +29.4%,
2019 +0.7%, 2020 +5.5%, 2021 +10.9%, 2022 +36.3%, 2023 +10.8%, 2024 +7.5%.
The best years (2018, 2022) were bad years for SPY.

On dev, F met the Sharpe target (> 1.0 and above buy-and-hold) but not the
net-profit target. G met both.

### HOLDOUT (2024-11-01 to 2026-10-27, run once, nothing tuned after)

| Variant | Net profit | Sharpe | Stress net |
|---|---|---|---|
| Buy & hold SPY | **$34,356** | **1.03** | — |
| A baseline | −$4,011 | −0.29 | −$15,955 |
| D vol-target + HMM | $690 | 0.11 | −$4,490 |
| E ½ Kelly, cap 1x | $239 | 0.05 | −$5,381 |
| F ½ Kelly, cap 2x | −$1,684 | −0.10 | −$3,144 |
| G ½ Kelly, cap 4x | $432 | 0.08 | −$7,018 |

**Verdict: FAIL.** The filters cut the losses but found no edge. F traded only
72 of 497 days.

### Why it failed (diagnosis only, no tuning on the holdout)
1. **The edge faded after mid-2025.** Zero-cost baseline Sharpe by half-year
   was positive in 13 of 14 half-years from 2018 through the first half of
   2025, then −0.33 (H2 2025), −0.21 and −1.68 (2026).
2. **It was always thin.** The first noise-area breakout of the day, held to
   the close, earned ~3–4 bp gross on average across years, but no single year
   was statistically significant (best t = 1.57).
3. **The Gao et al. effect doesn't show in this sample.** The correlation
   between the first half-hour (including overnight) and the last half-hour
   was −0.22 to +0.17 by year, with no stable sign in 2016–2026.
4. **Post-publication decay is the likely cause.** The paper came out in May
   2024 and was widely replicated (e.g. TradingView scripts). McLean & Pontiff
   (Journal of Finance, 2016) find anomaly returns fall ~58% after
   publication, on average across 97 predictors.

### Takeaways
- The process worked as designed. The holdout caught an edge that looked good
  in development (Sharpe 1.05–1.09) but didn't survive.
- **Valid reusable parts:** measured cost model, no-churn engine, leverage
  caps, walk-forward HMM with filtered probabilities, no-lookahead Kelly, and
  the dev/holdout discipline.
- **The holdout is now spent.** Any further tuning on 2024-11 to 2026-10 would
  be overfitting, so new ideas need new out-of-sample data.

### Suggested next steps (ranked)
1. **Paper-trade candidate F on Alpaca for 1–3 months.** This gives genuinely
   new data and tests the live pipeline (orders, fills, the 3:55 PM close).
   It's free and honest. Expectation: roughly flat, given recent decay.
2. **Test the same family on assets it wasn't developed on** (QQQ, IWM, or
   other liquid ETFs) as a fresh out-of-sample check. Intraday momentum is
   reported across ETFs (Gao et al. 2018). Pick the asset list *before*
   looking.
3. **Return to mean reversion where it's documented to exist,** e.g. intraday
   pairs or spreads between closely related ETFs (the owner's original
   preference), with a new locked holdout from the start.

### Extra out-of-sample check: same frozen candidate F on other ETFs
The ETF list (QQQ, IWM, DIA) was fixed before looking. Nothing was changed.
Full 2016-01 to 2026-10 period, realistic costs:

| ETF | Net profit | Sharpe | Max DD | Stress Sharpe | Buy & hold Sharpe | Nov 2024–Oct 2026 Sharpe |
|---|---|---|---|---|---|---|
| QQQ | $213,727 | 1.02 | 12.7% | 0.33 | 0.90 | 0.24 |
| IWM | −$6,627 | −0.05 | 30.0% | −0.38 | 0.50 | −1.06 |
| DIA | −$28,298 | −0.72 | 29.4% | −1.00 | 0.69 | −0.64 |

Only QQQ worked, and it was weak recently too. **1 of 3 passes, so the edge
doesn't generalize.** That makes it more likely that the SPY dev result was
partly luck plus our variant selection, not just decay.

**Decision:** pending owner review.
