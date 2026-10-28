"""Daily backtest engine.

Timing rule (no look-ahead): a target position decided with data up to the
close of day t is traded at the OPEN of day t+1, paying slippage and
commission. Equity is marked to market at each close.
"""

import math

import pandas as pd

from .costs import commission, fill_price
from .metrics import summarize


def run_backtest(prices, target_weight, cfg, reasons=None):
    """Simulate trading `target_weight` (fraction of equity, decided at close).

    prices: DataFrame with open/close columns.
    target_weight: Series aligned to prices.index, values in [0, max_position].
    reasons: optional Series of exit-reason labels, aligned like target_weight.
    Returns (equity Series, list of trade dicts, summary dict).
    """
    costs = cfg["costs"]
    start_eq = cfg["backtest"]["starting_equity"]
    target = target_weight.reindex(prices.index).fillna(0.0)

    cash, shares = float(start_eq), 0
    equity, trades = [], []
    open_trade = None

    opens = prices["open"].to_numpy()
    closes = prices["close"].to_numpy()
    dates = prices.index

    for i in range(len(prices)):
        # Trade at today's open toward yesterday's target.
        if i > 0:
            want = target.iloc[i - 1]
            value_at_open = cash + shares * opens[i]
            desired = math.floor(want * value_at_open / opens[i]) if want > 0 else 0
            delta = desired - shares
            if delta != 0:
                side = 1 if delta > 0 else -1
                px = fill_price(opens[i], side, costs["slippage_bps"])
                fee = commission(delta, costs["commission_per_share"], costs["commission_min"])
                # Don't let a buy overdraw cash after slippage + fees.
                if side > 0:
                    affordable = math.floor((cash - fee) / px)
                    delta = max(0, min(delta, affordable))
                    fee = commission(delta, costs["commission_per_share"], costs["commission_min"])
                if delta != 0:
                    cash -= delta * px + fee
                    slip = abs(delta) * abs(px - opens[i])
                    if shares == 0:
                        open_trade = {
                            "entry_date": dates[i], "entry_price": px, "shares": delta,
                            "cost_basis": delta * px + fee, "costs": fee + slip,
                            "exit_date": None, "exit_price": None, "pnl": 0.0,
                            "days": 0, "reason": None,
                        }
                    elif open_trade is not None:
                        open_trade["costs"] += fee + slip
                        if delta > 0:
                            open_trade["cost_basis"] += delta * px + fee
                    shares += delta
                    if shares == 0 and open_trade is not None:
                        open_trade["exit_date"] = dates[i]
                        open_trade["exit_price"] = px
                        proceeds = -delta * px - fee
                        open_trade["pnl"] = proceeds - open_trade["cost_basis"]
                        open_trade["days"] = (dates[i] - open_trade["entry_date"]).days
                        if reasons is not None:
                            open_trade["reason"] = reasons.iloc[i - 1]
                        trades.append(open_trade)
                        open_trade = None

        equity.append(cash + shares * closes[i])

    if open_trade is not None:
        trades.append(open_trade)  # still open at the end; excluded from trade stats

    equity = pd.Series(equity, index=dates, name="equity")
    summary = summarize(equity, trades, start_eq, cfg["backtest"]["risk_free_rate"])
    return equity, trades, summary


def buy_and_hold(prices, cfg):
    """Benchmark: buy on the first day and hold, paying the same costs."""
    weight = pd.Series(1.0, index=prices.index)
    return run_backtest(prices, weight, cfg)
