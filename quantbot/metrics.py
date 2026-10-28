"""Performance metrics. All computed on net (after-cost) results."""

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def sharpe_ratio(daily_returns, risk_free_rate=0.0):
    """Annualized Sharpe ratio from daily returns."""
    r = pd.Series(daily_returns).dropna()
    excess = r - risk_free_rate / TRADING_DAYS
    std = excess.std(ddof=1)
    if len(r) < 2 or std == 0 or np.isnan(std):
        return 0.0
    return float(excess.mean() / std * np.sqrt(TRADING_DAYS))


def max_drawdown(equity):
    """Largest peak-to-trough fall, as a positive fraction (0.25 = -25%)."""
    equity = pd.Series(equity)
    return float((1 - equity / equity.cummax()).max())


def cagr(equity):
    equity = pd.Series(equity)
    years = len(equity) / TRADING_DAYS
    if years <= 0 or equity.iloc[0] <= 0:
        return 0.0
    return float((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1)


def summarize(equity, trades, starting_equity, risk_free_rate=0.0):
    """Headline numbers for one backtest."""
    equity = pd.Series(equity)
    returns = equity.pct_change().dropna()
    closed = [t for t in trades if t["exit_date"] is not None]
    wins = [t for t in closed if t["pnl"] > 0]
    return {
        "net_profit": float(equity.iloc[-1] - starting_equity),
        "total_return": float(equity.iloc[-1] / starting_equity - 1),
        "cagr": cagr(equity),
        "sharpe": sharpe_ratio(returns, risk_free_rate),
        "max_drawdown": max_drawdown(equity),
        "annual_vol": float(returns.std(ddof=1) * np.sqrt(TRADING_DAYS)),
        "trades": len(closed),
        "win_rate": len(wins) / len(closed) if closed else 0.0,
        "avg_hold_days": float(np.mean([t["days"] for t in closed])) if closed else 0.0,
        "total_costs": float(sum(t["costs"] for t in trades)),
    }
