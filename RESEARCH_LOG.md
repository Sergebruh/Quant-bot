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
