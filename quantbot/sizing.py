"""Position sizing: volatility targeting (and later, fractional Kelly).

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
