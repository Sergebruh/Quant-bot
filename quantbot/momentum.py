"""Intraday momentum: trade breakouts from the "noise area".

Based on Zarattini, Aziz & Barbon, "Beat the Market: An Effective Intraday
Momentum Strategy for S&P500 ETF (SPY)" (Swiss Finance Institute WP 24-97).

For each time of day, the noise area is how far SPY normally moves from the
open by that time, averaged over the previous `lookback_days` days:

    sigma(t)  = mean over past days of |close(t) / open - 1|
    upper(t)  = max(open, prev_close) * (1 + band_mult * sigma(t))
    lower(t)  = min(open, prev_close) * (1 - band_mult * sigma(t))

Price inside the band is treated as noise. A break above `upper` means buyers
are in control (go long); below `lower`, sellers are (go short). A trailing
stop sits at the band or VWAP, whichever is closer to price. Decisions are
only made at `decision_minutes` (e.g. every half hour) to limit overtrading.
"""

import numpy as np
import pandas as pd

from .intraday import session_dates, vwap_zscore


def noise_bands(bars, lookback_days, band_mult=1.0):
    """Return (upper, lower, sigma) Series. Uses only days before today."""
    day = session_dates(bars.index).to_numpy()
    bar_no = pd.Series(day, index=bars.index).groupby(day).cumcount().to_numpy()
    day_open = bars["open"].groupby(day).transform("first")
    move = (bars["close"] / day_open - 1).abs()

    # Table of days x time-of-day; average the previous N days at each time.
    table = pd.DataFrame({"day": day, "bar": bar_no, "move": move.to_numpy()})
    wide = table.pivot(index="day", columns="bar", values="move")
    sigma_wide = wide.rolling(lookback_days, min_periods=lookback_days).mean().shift(1)
    sigma_long = sigma_wide.stack().rename("sigma").reset_index()
    sigma = (
        table[["day", "bar"]]
        .merge(sigma_long, on=["day", "bar"], how="left")["sigma"]
        .to_numpy()
    )
    sigma = pd.Series(sigma, index=bars.index)

    last_close = bars["close"].groupby(day).last()
    prev_close = pd.Series(day, index=bars.index).map(last_close.shift(1))
    top = np.maximum(day_open, prev_close.fillna(day_open))
    bottom = np.minimum(day_open, prev_close.fillna(day_open))
    upper = top * (1 + band_mult * sigma)
    lower = bottom * (1 - band_mult * sigma)
    return upper, lower, sigma


def momentum_positions(bars, cfg):
    """Target weights (+1 long, -1 short, 0 flat) and exit reasons per bar."""
    s = cfg["momentum_signal"]
    upper, lower, _ = noise_bands(bars, s["lookback_days"], s["band_mult"])
    vwap, _ = vwap_zscore(bars)

    day = session_dates(bars.index).to_numpy()
    close_time = bars.index + pd.Timedelta(minutes=5)  # bar timestamps are start times
    decide = np.isin(close_time.minute, s["decision_minutes"])
    ub, lb, vw, px = (x.to_numpy() for x in (upper, lower, vwap, bars["close"]))

    weight = np.zeros(len(bars))
    reason = np.array([None] * len(bars), dtype=object)
    pos = 0
    for i in range(len(bars)):
        if i > 0 and day[i] != day[i - 1]:
            pos = 0
        if decide[i] and not np.isnan(ub[i]):
            if pos > 0 and px[i] < max(ub[i], vw[i]):
                pos, reason[i] = 0, "stop"
            elif pos < 0 and px[i] > min(lb[i], vw[i]):
                pos, reason[i] = 0, "stop"
            if pos == 0:
                if px[i] > ub[i]:
                    pos = 1
                elif px[i] < lb[i] and s["allow_short"]:
                    pos = -1
        weight[i] = pos
    return pd.Series(weight, index=bars.index), pd.Series(reason, index=bars.index)
