# Quant-bot: working rules for Claude

## Git workflow
- Never push to `main`. Every change goes on its own branch
  (`feature/...`, `fix/...`, `experiment/...`, `docs/...`) and a pull request.
- The owner reviews and merges, or says "merge it." Don't merge without that.
- Commit identity for this repo: `Claude <noreply@anthropic.com>`.

## The improvement loop (follow this every time)
After every backtest run:

1. **Fail?** Compare against the targets below. Anything short of them is a
   fail.
2. **Identify why.** Break results down (by exit reason, trend, volatility,
   year, worst trades) until the losses have a concrete cause. Use data, not
   guesses.
3. **Research why and where.** Look for evidence (papers, known strategy
   behavior) that explains the failure and how others fix it. Cite sources.
4. **Suggest improvements.** Rank by expected impact, explain each in plain
   language, and name the risk (especially overfitting).
5. **Wait for approval.** Don't build an improvement until the owner approves it.
6. **Continue.** Build the approved change on a new branch, rerun, and log it.

Record every run in `RESEARCH_LOG.md`: what changed, results, diagnosis, and
the decision.

## Targets (set by the owner; final verdict on out-of-sample data)
All results are after realistic costs, and always reported next to SPY
buy-and-hold over the same period.

Every strategy must have:
1. **Sharpe ratio > 1.0**
2. **A profit under stress costs** (the pessimistic cost profile)
3. **Max drawdown smaller than buy-and-hold's**

Plus, by type:
- **Directional** (takes market-direction bets, e.g. momentum, mean reversion
  on one asset): Sharpe must also be **above buy-and-hold's**. Net profit vs
  buy-and-hold is reported but not required, since leverage scales profit,
  not Sharpe.
- **Market-neutral** (long and short at once, e.g. pairs): correlation of
  daily returns with SPY must be **between −0.3 and +0.3**. No profit or
  Sharpe comparison with buy-and-hold is required, but both are reported.

## Honesty rules for backtests
- No look-ahead: decide at bar t close, trade at bar t+1 open. Day trading:
  always flat at the close, never hold overnight. HMM uses filtered
  probabilities only, never Viterbi.
- Always report net of costs and next to buy-and-hold.
- Keep a change only if it improves results for a reason we can explain. Tune
  parameters on training windows only once walk-forward exists, and check that
  results survive ±20% parameter nudges.
- Prefer the simpler model when a complex one doesn't clearly beat it.

## Commands
- Tests: `python -m pytest`
- Day-trading backtest: `python run_backtest.py` (5-minute Alpaca bars; `--refresh` re-downloads)
- Daily swing backtest (reference): `python run_daily_backtest.py`
- Settings: `config.yaml`
