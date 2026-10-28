"""Bar-by-bar backtest engine for daily or intraday bars.

Timing rule (no look-ahead): a target position decided with data up to the
close of bar t is traded at the OPEN of bar t+1, paying slippage and
commission. Equity is marked to market at each close.

Day-trading mode (`force_flat=True`): the position is closed at the open of
each session's last bar, and nothing decided on one day is carried into the
next, so the bot never holds overnight.
"""

import math

import pandas as pd

from .costs import commission, fill_price
from .metrics import summarize


def run_backtest(prices, target_weight, cfg, reasons=None, sessions=None, force_flat=False):
    """Simulate trading `target_weight` (fraction of equity, decided at close).

    prices: DataFrame with open/close columns.
    target_weight: Series aligned to prices.index, values in [0, max_position].
    reasons: optional Series of exit-reason labels, aligned like target_weight.
    sessions: optional Series of trading dates for intraday bars. Metrics are
        then computed on end-of-day equity.
    force_flat: close everything before each session ends (needs `sessions`).
    Returns (equity Series, list of trade dicts, summary dict).
    """
    costs = cfg["costs"]
    start_eq = cfg["backtest"]["starting_equity"]
    target = target_weight.reindex(prices.index).fillna(0.0).to_numpy()
    reason_arr = None if reasons is None else reasons.reindex(prices.index).to_numpy()
    if force_flat and sessions is None:
        raise ValueError("force_flat needs sessions")
    if sessions is not None:
        sess = pd.Series(sessions, index=prices.index)
        last_bar = (sess != sess.shift(-1)).to_numpy()

    cash, shares = float(start_eq), 0
    equity, trades = [], []
    open_trade = None

    opens = prices["open"].to_numpy()
    closes = prices["close"].to_numpy()
    dates = prices.index

    for i in range(len(prices)):
        # Trade at today's open toward yesterday's target.
        if i > 0:
            want = target[i - 1]
            exit_reason = reason_arr[i - 1] if reason_arr is not None else None
            if force_flat and (last_bar[i] or last_bar[i - 1]):
                if shares != 0 and last_bar[i]:
                    exit_reason = "close"
                want = 0.0
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
                            "days": 0, "bars": 0, "entry_bar": i, "reason": None,
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
                        open_trade["bars"] = i - open_trade["entry_bar"]
                        open_trade["reason"] = exit_reason
                        trades.append(open_trade)
                        open_trade = None

        equity.append(cash + shares * closes[i])

    if open_trade is not None:
        trades.append(open_trade)  # still open at the end; excluded from trade stats

    equity = pd.Series(equity, index=dates, name="equity")
    daily = equity if sessions is None else equity.groupby(sess.to_numpy()).last()
    summary = summarize(daily, trades, start_eq, cfg["backtest"]["risk_free_rate"])
    return equity, trades, summary


def buy_and_hold(prices, cfg, sessions=None):
    """Benchmark: buy on the first bar and hold, paying the same costs."""
    weight = pd.Series(1.0, index=prices.index)
    return run_backtest(prices, weight, cfg, sessions=sessions)
