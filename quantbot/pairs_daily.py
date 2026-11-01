"""Multi-day pairs trading on daily bars (positions held overnight).

Follows the classic approach (Gatev, Goetzmann & Rouwenhorst 2006) with
rolling windows as in Avellaneda & Lee (2010):

    beta        OLS of log(A) on log(B) over the previous `window_days` closes
    mu, sigma   mean / std of log(A) - beta*log(B) over the same days
    z           (today's spread - mu) / sigma, with today's beta

All parameters use days before today, so the decision at today's close has no
look-ahead; the trade fills at the next day's open.

    z < -entry_z  -> long the spread   (buy A, short beta x B)
    z > +entry_z  -> short the spread
    z crosses 0   -> exit (target)
    |z| > stop_z  -> exit (stop), wait for |z| < entry_z before re-entering
    held max_hold_days -> exit (time), same wait
"""

import numpy as np
import pandas as pd


def align_daily(a, b):
    out = a[["open", "close"]].add_suffix("_a").join(b[["open", "close"]].add_suffix("_b"),
                                                     how="inner")
    return out.dropna()


def rolling_spread_z(pair, window_days):
    x, y = np.log(pair["close_b"]), np.log(pair["close_a"])
    roll = lambda s: s.rolling(window_days, min_periods=window_days).mean().shift(1)  # noqa: E731
    mx, my = roll(x), roll(y)
    vx = roll(x * x) - mx**2
    vy = roll(y * y) - my**2
    cxy = roll(x * y) - mx * my
    beta = cxy / vx
    mu = my - beta * mx
    sigma = np.sqrt((vy + beta**2 * vx - 2 * beta * cxy).clip(lower=0)).replace(0, np.nan)
    z = (y - beta * x - mu) / sigma
    return beta, z


def daily_pair_positions(pair, cfg):
    s = cfg["pairs_daily"]
    beta, z = rolling_spread_z(pair, s["window_days"])
    zs, bs = z.to_numpy(), beta.to_numpy()
    pos = np.zeros(len(pair))
    reason = np.array([None] * len(pair), dtype=object)
    state, armed, held = 0, True, 0
    for i in range(len(pair)):
        zi = zs[i]
        if np.isnan(zi) or not bs[i] > 0:
            pos[i] = state
            continue
        if not armed and abs(zi) < s["entry_z"]:
            armed = True
        if state != 0:
            held += 1
            if (state == 1 and zi >= 0) or (state == -1 and zi <= 0):
                state, reason[i] = 0, "target"
            elif abs(zi) > s["stop_z"]:
                state, armed, reason[i] = 0, False, "stop"
            elif held >= s["max_hold_days"]:
                state, armed, reason[i] = 0, False, "time"
        elif armed and abs(zi) > s["entry_z"]:
            state, held = (1 if zi < 0 else -1), 0
        pos[i] = state
    return (pd.Series(pos, index=pair.index), pd.Series(reason, index=pair.index), beta, z)
