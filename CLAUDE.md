# Quant-bot: working rules for Claude

## Git workflow
- Never push to `main`. Every change goes on its own branch
  (`feature/...`, `fix/...`, `experiment/...`, `docs/...`) and a pull request.
- The owner reviews and merges, or says "merge it." Don't merge without that.
- Commit identity for this repo: `Claude <noreply@anthropic.com>`.

## The improvement loop (follow this every time)
After every backtest run:

1. **Fail?** Compare against the targets: net profit after commissions and
   slippage beats buy-and-hold, **and** Sharpe ratio > 1.0 and above
   buy-and-hold's. Anything short of that is a fail.
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

## Honesty rules for backtests
- No look-ahead: decide at close t, trade at open t+1. HMM uses filtered
  probabilities only, never Viterbi.
- Always report net of costs and next to buy-and-hold.
- Keep a change only if it improves results for a reason we can explain. Tune
  parameters on training windows only once walk-forward exists, and check that
  results survive ±20% parameter nudges.
- Prefer the simpler model when a complex one doesn't clearly beat it.

## Commands
- Tests: `python -m pytest`
- Backtest: `python run_backtest.py` (add `--refresh` to re-download prices)
- Settings: `config.yaml`
