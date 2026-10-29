"""Position sizing: volatility targeting and fractional Kelly.

All scales are decided before the day starts, from past daily closes only.
"""

import numpy as np
import pandas as pd

from .intraday import session_dates


def daily_closes(bars):
    day = session_dates(bars.index).to_numpy()
    return bars["close"].groupby(day).last()


def vol_target_scale(bars, target_daily_vol, lookback_days=14, max_leverage=1.0):
    """Per-bar exposure multiplier = min(max_leverage, target / recent daily vol).

    Recent vol is the std of the previous `lookback_days` daily close-to-close
    returns (today excluded), as in Zarattini, Aziz & Barbon (2024).
    """
    closes = daily_closes(bars)
    vol = closes.pct_change().rolling(lookback_days).std(ddof=1).shift(1)
    scale = (target_daily_vol / vol).clip(upper=max_leverage)
    day = session_dates(bars.index).to_numpy()
    return pd.Series(day, index=bars.index).map(scale).astype(float)


def apply_sizing(weight, bars, cfg):
    """Scale +1/-1/0 signals into position sizes per the `sizing` config."""
    s = cfg["sizing"]
    method = s.get("method", "none")
    if method == "none":
        return weight.clip(-s["max_leverage"], s["max_leverage"])
    if method == "vol_target":
        scale = vol_target_scale(bars, s["target_daily_vol"], s["vol_lookback_days"],
                                 s["max_leverage"])
        return (weight * scale).fillna(0.0)
    raise ValueError(f"unknown sizing method {method!r}")


def kelly_leverage(daily_returns, fraction=0.5, lookback_days=252, min_days=126,
                   max_leverage=1.0):
    """Per-day leverage from the strategy's own past daily returns.

    Kelly for a continuous return stream: f* = mu / sigma^2. We estimate mu and
    sigma^2 from the previous `lookback_days` daily returns of the strategy run
    at unit size (today excluded), bet `fraction` of f*, and clip to
    [0, max_leverage]. A negative estimated edge means f* < 0: don't trade.
    Before `min_days` of history, use leverage 1.
    """
    r = pd.Series(daily_returns).astype(float)
    mu = r.rolling(lookback_days, min_periods=min_days).mean().shift(1)
    var = r.rolling(lookback_days, min_periods=min_days).var(ddof=1).shift(1)
    f = (fraction * mu / var).clip(lower=0, upper=max_leverage)
    return f.fillna(1.0).clip(upper=max_leverage)
