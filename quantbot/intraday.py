"""Intraday VWAP z-score mean-reversion signal.

VWAP is the volume-weighted average price since today's open. The z-score
measures how many volume-weighted standard deviations price sits below or
above it:

    z = (close - VWAP) / sigma,   sigma^2 = sum(v * p^2) / sum(v) - VWAP^2

Both are reset every morning and use only bars up to the current one.
"""

import numpy as np
import pandas as pd


def session_dates(index):
    return pd.Series(index.date, index=index, name="session")


def vwap_zscore(bars):
    """Return (vwap, z) Series for intraday bars with vwap_bar/volume/close."""
    day = session_dates(bars.index)
    price = bars["vwap_bar"].fillna(bars["close"])
    vol = bars["volume"].astype(float)
    cum_v = vol.groupby(day).cumsum()
    cum_pv = (price * vol).groupby(day).cumsum()
    cum_p2v = (price**2 * vol).groupby(day).cumsum()
    vwap = cum_pv / cum_v
    var = (cum_p2v / cum_v - vwap**2).clip(lower=0)
    sigma = np.sqrt(var).replace(0, np.nan)
    return vwap, (bars["close"] - vwap) / sigma


def vwap_reversion_positions(bars, cfg):
    """Long-only target weights and exit reasons, decided at each bar's close.

    Enter when z < entry_z (after the warm-up, before the last-entry time).
    Exit when z >= exit_z (target), z < stop_z (stop), or after max_hold_bars
    (time). After a stop or time exit, wait for z to recover above entry_z
    before re-entering. State resets each day; the engine flattens at the close.
    """
    s = cfg["intraday_signal"]
    _, z = vwap_zscore(bars)
    day = session_dates(bars.index).to_numpy()
    bar_no = session_dates(bars.index).groupby(day).cumcount().to_numpy()
    hhmm = bars.index.strftime("%H:%M").to_numpy()

    weight = np.zeros(len(bars))
    reason = np.array([None] * len(bars), dtype=object)
    in_pos, held, armed = False, 0, True
    zs = z.to_numpy()

    for i in range(len(bars)):
        if i > 0 and day[i] != day[i - 1]:
            in_pos, held, armed = False, 0, True
        zi = zs[i]
        if np.isnan(zi):
            weight[i] = 1.0 if in_pos else 0.0
            continue
        if not armed and zi > s["entry_z"]:
            armed = True
        if in_pos:
            held += 1
            if zi >= s["exit_z"]:
                in_pos, reason[i] = False, "target"
            elif zi < s["stop_z"]:
                in_pos, armed, reason[i] = False, False, "stop"
            elif held >= s["max_hold_bars"]:
                in_pos, armed, reason[i] = False, False, "time"
        elif (armed and zi < s["entry_z"] and bar_no[i] >= s["warmup_bars"]
              and hhmm[i] < s["last_entry"]):
            in_pos, held = True, 0
        weight[i] = 1.0 if in_pos else 0.0

    return pd.Series(weight, index=bars.index), pd.Series(reason, index=bars.index), z
