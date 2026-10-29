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
    target_weight: Series aligned to prices.index. Positive = long, negative =
        short, as a fraction of equity.
    reasons: optional Series of exit-reason labels, aligned like target_weight.
    sessions: optional Series of trading dates for intraday bars. Metrics are
        then computed on end-of-day equity.
    force_flat: close everything before each session ends (needs `sessions`).
    Returns (equity Series, list of trade dicts, summary dict).
    """
    costs = cfg["costs"]
    start_eq = cfg["backtest"]["starting_equity"]
    max_leverage = cfg.get("sizing", {}).get("max_leverage", 1.0)
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

    def fill(i, delta, reason):
        """Trade `delta` shares at bar i's open; return shares actually traded."""
        nonlocal cash, shares, open_trade
        side = 1 if delta > 0 else -1
        px = fill_price(opens[i], side, costs["slippage_bps"])
        fee = commission(delta, costs["commission_per_share"], costs["commission_min"])
        # Buying power: a position (long or short) can't exceed
        # max_leverage x equity.
        if abs(shares + delta) > abs(shares):
            equity_now = cash + shares * opens[i]
            limit = math.floor((max_leverage * equity_now - fee) / px)
            if side > 0:
                delta = max(0, min(delta, limit - shares))
            else:
                delta = min(0, max(delta, -limit - shares))
            fee = commission(delta, costs["commission_per_share"], costs["commission_min"])
        if delta == 0:
            return 0
        cash -= delta * px + fee
        slip = abs(delta) * abs(px - opens[i])
        if shares == 0:
            open_trade = {
                "side": "long" if delta > 0 else "short",
                "entry_date": dates[i], "entry_price": px, "shares": delta,
                "cost_basis": abs(delta) * px, "cash_flow": 0.0, "costs": 0.0,
                "exit_date": None, "exit_price": None, "pnl": 0.0,
                "days": 0, "bars": 0, "entry_bar": i, "reason": None,
            }
        elif (delta > 0) == (shares > 0):
            open_trade["cost_basis"] += abs(delta) * px  # adding to the position
        open_trade["cash_flow"] -= delta * px + fee
        open_trade["costs"] += fee + slip
        shares += delta
        if shares == 0:
            open_trade.update(
                exit_date=dates[i], exit_price=px, pnl=open_trade["cash_flow"],
                days=(dates[i] - open_trade["entry_date"]).days,
                bars=i - open_trade["entry_bar"], reason=reason,
            )
            trades.append(open_trade)
            open_trade = None
        return delta

    last_want = 0.0
    for i in range(len(prices)):
        # Trade at this bar's open toward the target decided at the previous close.
        if i > 0:
            want = target[i - 1]
            exit_reason = reason_arr[i - 1] if reason_arr is not None else None
            if force_flat and (last_bar[i] or last_bar[i - 1]):
                if shares != 0 and last_bar[i]:
                    exit_reason = "close"
                want = 0.0
            # Only trade when the target changes; otherwise hold the same shares
            # (re-sizing every bar as equity drifts just churns commissions).
            if want == last_want and not (want == 0 and shares != 0):
                equity.append(cash + shares * closes[i])
                continue
            last_want = want
            value_at_open = cash + shares * opens[i]
            desired = math.trunc(want * value_at_open / opens[i])
            if desired != shares:
                # Flipping long <-> short goes through flat, as two orders.
                if shares != 0 and (desired == 0 or (desired > 0) != (shares > 0)):
                    fill(i, -shares, exit_reason or "flip")
                if desired != shares:
                    fill(i, desired - shares, exit_reason)

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
