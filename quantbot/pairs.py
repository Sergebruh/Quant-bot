"""Intraday pairs trading: mean reversion of the spread between two related assets.

Spread:   s = log(A) - beta * log(B)
z-score:  z = (s - mu) / sigma

beta comes from an OLS regression of log(A) on log(B) over the 5-minute bars of
the previous `beta_days` sessions. mu and sigma are the mean and standard
deviation of the spread (with today's beta) over the previous `zscore_days`
sessions. All three are fixed before the day starts, so nothing looks ahead.

Signal (decided at each bar's close, traded at the next bar's open):
  z < -entry_z  -> long the spread  (buy A, short beta x B)
  z > +entry_z  -> short the spread (short A, buy beta x B)
  z crosses 0   -> exit (target)
  |z| > stop_z  -> exit (stop), and wait for |z| < entry_z before re-entering
Entries only between `first_entry` and `last_entry`. Flat at the close.
"""

import math

import numpy as np
import pandas as pd

from .costs import commission, fill_price
from .intraday import session_dates
from .metrics import summarize


def align(bars_a, bars_b):
    """Bars present for both assets, with columns open_a/close_a/open_b/close_b."""
    a = bars_a[["open", "close"]].add_suffix("_a")
    b = bars_b[["open", "close"]].add_suffix("_b")
    return a.join(b, how="inner")


def daily_spread_params(pair, beta_days, zscore_days):
    """Per-session beta, mu, sigma using only previous sessions."""
    x = np.log(pair["close_b"])
    y = np.log(pair["close_a"])
    day = session_dates(pair.index).to_numpy()
    sums = pd.DataFrame({"n": 1.0, "x": x, "y": y, "xx": x * x, "yy": y * y, "xy": x * y})
    sums = sums.groupby(day).sum()

    def window(n_days):
        w = sums.rolling(n_days, min_periods=n_days).sum().shift(1)
        mx, my = w["x"] / w["n"], w["y"] / w["n"]
        vx = w["xx"] / w["n"] - mx**2
        vy = w["yy"] / w["n"] - my**2
        cxy = w["xy"] / w["n"] - mx * my
        return mx, my, vx, vy, cxy

    mx, my, vx, vy, cxy = window(beta_days)
    beta = cxy / vx

    mx, my, vx, vy, cxy = window(zscore_days)
    mu = my - beta * mx
    var = vy + beta**2 * vx - 2 * beta * cxy
    sigma = np.sqrt(var.clip(lower=0)).replace(0, np.nan)
    return pd.DataFrame({"beta": beta, "mu": mu, "sigma": sigma})


def pair_zscore(pair, beta_days, zscore_days):
    """Per-bar beta and z-score of the spread."""
    params = daily_spread_params(pair, beta_days, zscore_days)
    day = session_dates(pair.index)
    p = params.reindex(day.to_numpy())
    p.index = pair.index
    spread = np.log(pair["close_a"]) - p["beta"] * np.log(pair["close_b"])
    z = (spread - p["mu"]) / p["sigma"]
    return p["beta"], z


def pair_positions(pair, cfg):
    """Spread position per bar (+1 long spread, -1 short, 0 flat) and exit reasons."""
    s = cfg["pairs"]
    beta, z = pair_zscore(pair, s["beta_days"], s["zscore_days"])
    day = session_dates(pair.index).to_numpy()
    hhmm = pair.index.strftime("%H:%M").to_numpy()
    zs, bs = z.to_numpy(), beta.to_numpy()

    pos = np.zeros(len(pair))
    reason = np.array([None] * len(pair), dtype=object)
    state, armed = 0, True
    for i in range(len(pair)):
        if i > 0 and day[i] != day[i - 1]:
            state, armed = 0, True
        zi = zs[i]
        if np.isnan(zi) or not bs[i] > 0:
            pos[i] = state
            continue
        if not armed and abs(zi) < s["entry_z"]:
            armed = True
        if state == 1 and zi >= 0:
            state, reason[i] = 0, "target"
        elif state == -1 and zi <= 0:
            state, reason[i] = 0, "target"
        elif state != 0 and abs(zi) > s["stop_z"]:
            state, armed, reason[i] = 0, False, "stop"
        elif (state == 0 and armed and s["first_entry"] <= hhmm[i] < s["last_entry"]
              and abs(zi) > s["entry_z"]):
            state = 1 if zi < 0 else -1
        pos[i] = state
    return (pd.Series(pos, index=pair.index), pd.Series(reason, index=pair.index),
            beta, z)


def run_pair_backtest(pair, position, beta, cfg, symbols, reasons=None):
    """Simulate a dollar-hedged pair, flat at each close.

    A long spread holds +L/(1+beta) of equity in A and -beta*L/(1+beta) in B,
    so gross exposure is L (cfg pairs.gross_leverage). Shares are set when a
    position opens and held until it changes. Each leg pays its own slippage
    (cfg pairs.slippage_bps[symbol]) plus commission.
    """
    costs = cfg["pairs"].get("costs", cfg["costs"])
    slip_bps = cfg["pairs"]["slippage_bps"]
    lev = cfg["pairs"]["gross_leverage"]
    start_eq = cfg["backtest"]["starting_equity"]
    sym_a, sym_b = symbols

    sess = session_dates(pair.index)
    last_bar = (sess != sess.shift(-1)).to_numpy()
    opens = {sym_a: pair["open_a"].to_numpy(), sym_b: pair["open_b"].to_numpy()}
    closes_a, closes_b = pair["close_a"].to_numpy(), pair["close_b"].to_numpy()
    pos = position.to_numpy()
    betas = beta.to_numpy()
    reason_arr = None if reasons is None else reasons.to_numpy()
    dates = pair.index

    cash = float(start_eq)
    shares = {sym_a: 0, sym_b: 0}
    held_state = 0
    equity, trades, trade = [], [], None

    def fill(i, sym, delta):
        nonlocal cash
        if delta == 0:
            return 0.0, 0.0
        side = 1 if delta > 0 else -1
        px = fill_price(opens[sym][i], side, slip_bps[sym])
        fee = commission(delta, costs["commission_per_share"], costs["commission_min"])
        cash -= delta * px + fee
        shares[sym] += delta
        return -(delta * px) - fee, fee + abs(delta) * abs(px - opens[sym][i])

    for i in range(len(pair)):
        if i > 0:
            want = pos[i - 1]
            why = reason_arr[i - 1] if reason_arr is not None else None
            if last_bar[i] or last_bar[i - 1]:
                if held_state != 0 and last_bar[i]:
                    why = "close"
                want = 0
            if want != held_state:
                # Close the current position (both legs).
                if held_state != 0:
                    f1, c1 = fill(i, sym_a, -shares[sym_a])
                    f2, c2 = fill(i, sym_b, -shares[sym_b])
                    trade["cash_flow"] += f1 + f2
                    trade["costs"] += c1 + c2
                    trade.update(exit_date=dates[i], pnl=trade["cash_flow"], reason=why,
                                 days=0, bars=i - trade["entry_bar"])
                    trades.append(trade)
                    trade = None
                # Open the new one.
                if want != 0:
                    b = betas[i - 1]
                    eq_now = cash + shares[sym_a] * opens[sym_a][i] + shares[sym_b] * opens[sym_b][i]
                    notional_a = lev * eq_now / (1 + b)
                    qa = math.trunc(want * notional_a / opens[sym_a][i])
                    qb = math.trunc(-want * b * notional_a / opens[sym_b][i])
                    f1, c1 = fill(i, sym_a, qa)
                    f2, c2 = fill(i, sym_b, qb)
                    trade = {"side": "long_spread" if want > 0 else "short_spread",
                             "entry_date": dates[i], "entry_bar": i, "beta": b,
                             "shares": qa, "shares_b": qb,
                             "cost_basis": abs(qa) * opens[sym_a][i] + abs(qb) * opens[sym_b][i],
                             "cash_flow": f1 + f2, "costs": c1 + c2,
                             "exit_date": None, "pnl": 0.0, "days": 0, "bars": 0,
                             "reason": None}
                held_state = want
        equity.append(cash + shares[sym_a] * closes_a[i] + shares[sym_b] * closes_b[i])

    equity = pd.Series(equity, index=dates, name="equity")
    daily = equity.groupby(sess.to_numpy()).last()
    summary = summarize(daily, trades, start_eq, cfg["backtest"]["risk_free_rate"])
    return equity, trades, summary
