# Quant-bot

A **day-trading** bot for SPY on 5-minute bars. The current strategy is
regime-aware **mean reversion**: buy when price stretches unusually far below
today's VWAP and sell as it snaps back. Every position is closed before the
market closes; nothing is held overnight. Positions are sized with volatility
and a fractional Kelly criterion.

> Status: data, engine and the baseline signal are built and tested. The
> baseline fails (see `RESEARCH_LOG.md`); improvements go through the loop in
> `CLAUDE.md`.

## Getting started

```bash
git clone https://github.com/Sergebruh/Quant-bot.git
cd Quant-bot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest
```

Price data comes from Alpaca (a free paper account works). On your own machine,
set `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` as environment variables. Never
commit keys. Then run:

```bash
python run_backtest.py            # day-trading backtest (5-minute bars)
python run_daily_backtest.py      # original daily swing version, for reference
```

All tunable settings (costs, z-score levels, HMM, sizing) live in `config.yaml`.

## Strategy in one picture

```
5-minute SPY bars (regular hours, official calendar incl. half-days)
    │
    ▼
[1] Regime filter (Hidden Markov Model)   →  calm / trending / volatile day?
    │   only trade mean reversion when the regime suits it
    ▼
[2] Entry/exit signal (VWAP z-score)      →  how far is price from today's VWAP?
    │   buy when z < −2, exit when z returns to 0
    ▼
[3] Risk scaling (standard deviation)     →  how volatile is it right now?
    │   smaller positions when volatility is high
    ▼
[4] Position size (fractional Kelly)      →  how much capital to commit?
    │
    ▼
Order at the NEXT bar's open (net of commissions + slippage)
    │
    ▼
Flat by 3:55 PM (12:55 PM on half-days). Nothing held overnight.
```

## 1. Regime filter: Hidden Markov Model

Mean reversion only pays when price actually snaps back. On strong trend days a
"cheap" price keeps getting cheaper. A Gaussian HMM finds hidden market states
from the data.

- **Inputs (features):** intraday returns and realized volatility.
- **States:** 3 (calm, trending, volatile), labeled after fitting by each
  state's average volatility.
- **Rule:** open new trades only when the probability of the favorable state is
  above 0.6.
- **No look-ahead:** refit on past data only, and use *filtered* probabilities
  (the forward algorithm), never the Viterbi path.

## 2. Signal: VWAP z-score

VWAP is the volume-weighted average price since today's open. Sigma is the
volume-weighted standard deviation of price around it (the "VWAP bands"):

```
z = (close − VWAP) / σ_VWAP          both reset every morning
```

| Condition                            | Action              |
|--------------------------------------|---------------------|
| `z < −2.0`, after 10:00, before 15:30 | Enter long         |
| `z ≥ 0` (back to VWAP)               | Exit                |
| `z < −3.5`                           | Stop-loss exit      |
| Held 12 bars (1 hour)                | Time-stop exit      |
| 3:55 PM                              | Close everything    |

Long-only to start.

## 3. Risk: standard deviation

Standard deviation drives the z-score and also sets size through **volatility
targeting**: `vol_scale = target_vol / realized_vol`.

## 4. Position sizing: fractional Kelly

```
f* = μ / σ²       μ = expected return per trade, σ² = variance of trade returns
```

Estimate μ and σ² from past trades only, bet **¼ to ½ Kelly**, and cap
position size at 100% of equity (no leverage at first). Trading pauses if
drawdown exceeds 20%.

## How we measure success

Two numbers, both **after costs**, always next to buying and holding SPY:

### Net profit (after commissions and slippage)

| Cost        | Default assumption            | Config key              |
|-------------|-------------------------------|-------------------------|
| Commission  | $0.005 per share, $1 minimum  | `commission_per_share`  |
| Slippage    | 2 basis points per side       | `slippage_bps`          |

Alpaca itself charges $0 commission. The default is deliberately conservative,
and `RESEARCH_LOG.md` shows results across cost levels.

### Sharpe ratio

Annualized and computed on end-of-day net returns:

```
sharpe = mean(daily_return − rf_daily) / std(daily_return) × √252
```

**Target:** Sharpe > 1.0 out of sample and above buy-and-hold.

## Testing method

1. **No peeking:** signals use data up to bar *t* close, and trades fill at bar
   *t + 1* open. VWAP and sigma use only bars so far today.
2. **Walk-forward:** tune on past windows and test on the next window only.
3. **Avoid overfitting:** few parameters. Results must survive ±20% nudges.
4. **Paper trade** on Alpaca for 1–3 months before any real money.

## Project structure

```
quant-bot/
├── quantbot/
│   ├── alpaca_data.py   # 5-minute bars + market calendar from Alpaca (cached)
│   ├── intraday.py      # VWAP z-score signal
│   ├── backtest.py      # bar-by-bar engine, next-bar fills, flat at the close
│   ├── costs.py         # commission + slippage
│   ├── metrics.py       # net profit, Sharpe, drawdown, etc.
│   ├── config.py        # loads + validates config.yaml
│   ├── data.py          # daily prices (yfinance), for the daily version
│   └── signals.py       # daily z-score signal, for the daily version
├── config.yaml
├── run_backtest.py          # day-trading backtest
├── run_daily_backtest.py    # daily swing backtest (reference)
├── RESEARCH_LOG.md          # every run: results, diagnosis, decisions
├── CLAUDE.md                # workflow + improvement loop
└── tests/
```

## Roadmap

- [x] Design
- [x] Daily swing baseline (run 1: failed, see log)
- [x] Day-trading data, engine and VWAP baseline (run 2: failed, see log)
- [x] Intraday pairs trading, 8 pairs (run 4: failed on costs, see log;
      `python run_pairs.py`)
- [ ] Next improvement, pending approval (see `RESEARCH_LOG.md`)
- [ ] Regime filter, sizing, walk-forward
- [ ] Paper trading on Alpaca

## Disclaimer

This is an educational project. Backtested results don't guarantee future
returns. Don't trade money you can't afford to lose.
