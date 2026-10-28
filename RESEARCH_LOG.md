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

**Decision:** pending owner approval.
