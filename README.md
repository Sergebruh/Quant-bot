# Quant-bot

A regime-aware **mean-reversion** trading bot. It buys when price has stretched
unusually far below its normal level and sells as it snaps back, but only when
the market is in a regime where mean reversion tends to work. It sizes each
position with volatility and a fractional Kelly criterion.

> Status: design phase. The code isn't written yet; this document is the plan.

## Getting started

```bash
git clone https://github.com/Sergebruh/Quant-bot.git
cd Quant-bot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest
```

All tunable settings (costs, z-score levels, HMM, sizing) live in `config.yaml`.

## Strategy in one picture

```
Daily prices
    │
    ▼
[1] Regime filter (Hidden Markov Model)   →  calm / trending / crisis?
    │   only trade mean reversion in the calm regime
    ▼
[2] Entry/exit signal (z-score)           →  is price unusually far from normal?
    │   buy when z < −2, exit when z returns to ~0
    ▼
[3] Risk scaling (standard deviation)     →  how volatile is it right now?
    │   smaller positions when volatility is high
    ▼
[4] Position size (fractional Kelly)      →  how much capital to commit?
    │
    ▼
Order (net of commissions + slippage)
```

## 1. Regime filter: Hidden Markov Model

Mean reversion works in calm, range-bound markets and loses money in strong
trends and crashes, where a "cheap" price keeps getting cheaper. A Gaussian HMM
finds these hidden market states from the data.

- **Inputs (features):** daily log returns and rolling 20-day volatility.
- **States:** 3 (calm, trending, crisis), labeled after fitting by each state's
  average volatility.
- **Rule:** open new mean-reversion trades only when the probability of the calm
  state is above 0.6 (`P(calm) > 0.6`). In the crisis state, close positions and
  stay flat.
- **No look-ahead:** refit the model on a rolling window of past data only. Use
  *filtered* state probabilities (the forward algorithm), never the Viterbi
  path, because Viterbi uses future data to smooth the past.

## 2. Signal: z-score

```
z = (price − rolling_mean(N)) / rolling_std(N)        N = 20 days (to be tuned)
```

| Condition                         | Action            |
|-----------------------------------|-------------------|
| `z < −2.0` and regime is calm     | Enter long        |
| `z ≥ 0` (back to the mean)        | Exit              |
| `z < −3.5` (stop)                 | Exit, don't add   |
| Held 10 days with no reversion    | Time-stop exit    |
| Regime flips to crisis            | Exit immediately  |

Long-only to start. Shorting (`z > +2`) can be added later.

## 3. Risk: standard deviation

Standard deviation drives the z-score, and it also sets position size through
**volatility targeting**:

```
vol_scale = target_vol / realized_vol      target_vol = 10% annualized
```

When the market gets wild, positions shrink automatically.

## 4. Position sizing: fractional Kelly

For a continuous return stream, the Kelly-optimal fraction is:

```
f* = μ / σ²       μ = expected return per trade, σ² = variance of trade returns
```

- Estimate μ and σ² from **past trades in the same regime**, with a rolling
  window and no look-ahead.
- Bet **¼ to ½ Kelly**, never full Kelly. Estimates of the edge are noisy, and
  full Kelly on an overestimated edge leads to large drawdowns.
- Final size: `position = min(kelly_fraction × f*, vol_scale, max_position)`.
- Hard caps: maximum position size of 100% of equity (no leverage at first) and
  a pause in trading if drawdown exceeds 20%.

## How we measure success

We judge the bot on two numbers, both **after costs**:

### Net profit (after commissions and slippage)

Every simulated trade pays:

| Cost        | Default assumption            | Config key        |
|-------------|-------------------------------|-------------------|
| Commission  | $0.005 per share, $1 minimum  | `commission`      |
| Slippage    | 2 basis points per side       | `slippage_bps`    |

```
net_profit = final_equity − starting_equity     (all costs already deducted)
```

### Sharpe ratio

Annualized and computed on daily net returns:

```
sharpe = mean(daily_return − rf_daily) / std(daily_return) × √252
```

- `rf` = risk-free rate (default 0%, configurable).
- **Target:** Sharpe > 1.0 out of sample. Anything below the Sharpe of buying
  and holding SPY means the strategy isn't worth running.

### Also reported

Maximum drawdown, win rate, number of trades, average holding period, and total
costs paid. These are always compared side by side with buying and holding SPY.

## Testing method

1. **Walk-forward backtest:** train on years 1–3, test on year 4, roll forward
   one year, and repeat. Only the out-of-sample (test) years count.
2. **No peeking:** signals use data up to day *t* close, and trades fill at day
   *t + 1* open.
3. **Avoid overfitting:** a small set of parameters, tuned only on training
   windows. Results must hold up when parameters are nudged ±20%.
4. **Paper trade** for at least 1–3 months before any real money.

## Planned project structure

```
quant-bot/
├── quantbot/
│   ├── data.py        # download and cache prices (yfinance)
│   ├── regime.py      # HMM fit + filtered regime probabilities
│   ├── signals.py     # z-score entry/exit logic
│   ├── sizing.py      # vol targeting + fractional Kelly
│   ├── backtest.py    # walk-forward engine with commissions + slippage
│   └── metrics.py     # net profit, Sharpe, drawdown, etc.
├── config.yaml        # all tunable parameters and cost assumptions
├── run_backtest.py
└── tests/
```

**Tech:** Python, pandas, numpy, hmmlearn, yfinance.

## Roadmap

- [x] Design
- [ ] v1: single-asset backtester on SPY (daily bars)
- [ ] v2: pairs trading, applying the z-score to the spread of two related
      assets (for example KO/PEP)
- [ ] v3: paper trading through a broker API

## Disclaimer

This is an educational project. Backtested results don't guarantee future
returns. Don't trade money you can't afford to lose.
