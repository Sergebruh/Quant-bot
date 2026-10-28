# Quant-bot

A **day-trading** bot for SPY on 5-minute bars. The current strategy is
regime-aware **intraday momentum** (noise-area breakout): go long or short when
SPY breaks out of its normal intraday range, but only when a Hidden Markov
Model says the market is in a trending regime. Positions are sized by
volatility targeting and fractional Kelly. Every position is closed before the
market closes; nothing is held overnight.

> Status: it passes on 2016–2024 development data (Sharpe 1.05) but **fails
> the locked 2024-11 to 2026-10 holdout** (Sharpe −0.10 vs 1.03 for
> buy-and-hold). The edge appears to have faded after the method was
> published. Full details: `RESEARCH_LOG.md` run 3.

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
python run_backtest.py            # day-trading backtest, development period
python run_backtest.py --holdout  # the locked holdout period
python experiments/run_experiments.py   # every variant from run 3
python run_daily_backtest.py      # original daily swing version, for reference
```

All tunable settings (costs, z-score levels, HMM, sizing) live in `config.yaml`.

## Strategy in one picture

```
5-minute SPY bars (regular hours, official calendar incl. half-days)
    │
    ▼
[1] Regime filter (Hidden Markov Model)   →  is SPY in a trending regime?
    │   trade only when P(trending) > 0.5
    ▼
[2] Signal (noise-area breakout)          →  has price left its normal range?
    │   long above the band, short below it, checked at :00 and :30
    ▼
[3] Risk scaling (standard deviation)     →  size = 2% / recent daily vol
    ▼
[4] Position size (fractional Kelly)      →  ½ × μ/σ² of the bot's own past
    │   returns, capped at max_leverage
    ▼
Order at the NEXT bar's open (net of commissions + slippage)
    │
    ▼
Flat by 3:55 PM (12:55 PM on half-days). Nothing held overnight.
```

## 1. Regime filter: Hidden Markov Model

Momentum pays when moves *within* a day tend to continue. Each day is
summarized by its **variance ratio**, var(30-min returns) / 6·var(5-min
returns): above 1 means trending, below 1 means choppy. A 2-state Gaussian HMM
learns trending vs choppy regimes from the 5-day average variance ratio.

- Refit every 21 days on the previous ~3 years only.
- The probability for today uses only data through yesterday: the *filtered*
  probability (forward algorithm) pushed one step through the transition
  matrix. Never Viterbi or smoothed probabilities.

## 2. Signal: noise-area breakout (a z-score on the move from the open)

From Zarattini, Aziz & Barbon (2024). For each time of day, σ(t) = the average
|move from the open| at that time over the previous 14 days. In z-score terms,
the bot trades when today's move from the open is more than 1 "typical move".

```
upper(t) = max(open, yesterday's close) × (1 + σ(t))
lower(t) = min(open, yesterday's close) × (1 − σ(t))
```

| Condition (checked at :00 and :30)       | Action                 |
|------------------------------------------|------------------------|
| Price above `upper`                      | Go long                |
| Price below `lower`                      | Go short               |
| Long and price < max(upper, VWAP)        | Exit (trailing stop)   |
| Short and price > min(lower, VWAP)       | Exit (trailing stop)   |
| 3:55 PM                                  | Close everything       |

## 3. Risk: standard deviation (volatility targeting)

`size = min(max_leverage, 2% / σ_daily)`, where σ_daily is the standard
deviation of the last 14 daily returns. Positions shrink when markets are wild.

## 4. Position sizing: fractional Kelly

```
f* = μ / σ²       μ, σ² = mean and variance of the bot's own daily returns
                  over the previous 252 days (at unit size)
```

The bot bets **½ Kelly**, clipped to [0, max_leverage]. If its past year lost
money, f* < 0 and it doesn't trade. The combined size after all scales is
capped at `max_leverage` (default 2x; US day-trading accounts of $25k+ can use
up to 4x intraday).

## How we measure success

Two numbers, both **after costs**, always next to buying and holding SPY:

### Net profit (after commissions and slippage)

| Cost        | Realistic (default)              | Stress test (always reported) |
|-------------|----------------------------------|-------------------------------|
| Commission  | $0.0035 per share, $0.35 minimum | $0.005 per share, $1 minimum  |
| Slippage    | 0.5 bp per side                  | 2 bp per side                 |

The realistic slippage is about 2.8x SPY's *measured* half-spread (0.18 bp,
from Alpaca quote data). Alpaca itself charges $0 commission.

### Sharpe ratio

Annualized and computed on end-of-day net returns:

```
sharpe = mean(daily_return − rf_daily) / std(daily_return) × √252
```

**Target:** Sharpe > 1.0 out of sample and above buy-and-hold.

## Testing method

1. **No peeking:** signals use data up to bar *t* close, and trades fill at bar
   *t + 1* open. Bands, VWAP, HMM and Kelly use only past data.
2. **Locked holdout:** develop only on data through `dev_end` (2024-10-31), then
   test the final candidate once on the rest (`--holdout`). The holdout is now
   spent; new ideas need fresh out-of-sample data.
3. **Avoid overfitting:** few parameters. Results must survive ±20% nudges.
4. **Paper trade** on Alpaca for 1–3 months before any real money.

## Project structure

```
quant-bot/
├── quantbot/
│   ├── alpaca_data.py   # 5-minute bars + market calendar from Alpaca (cached)
│   ├── intraday.py      # VWAP z-score signal (run 2)
│   ├── momentum.py      # noise-area breakout signal (run 3)
│   ├── regime.py        # walk-forward HMM on intraday trendiness
│   ├── sizing.py        # volatility targeting + fractional Kelly
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
- [x] Intraday momentum + vol sizing + HMM regime + Kelly (run 3: passes dev,
      fails holdout, see log)
- [ ] Next step, pending approval (see `RESEARCH_LOG.md`)
- [ ] Paper trading on Alpaca

## Disclaimer

This is an educational project. Backtested results don't guarantee future
returns. Don't trade money you can't afford to lose.
