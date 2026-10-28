"""Z-score mean-reversion signal."""

import numpy as np
import pandas as pd


def zscore(close, lookback):
    """(price - rolling mean) / rolling std, using only data up to each day."""
    mean = close.rolling(lookback).mean()
    std = close.rolling(lookback).std(ddof=1)
    return (close - mean) / std


def mean_reversion_positions(close, cfg):
    """Long-only target weights (0 or 1) and exit reasons, decided at each close.

    Enter when z < entry_z. Exit when z >= exit_z (target), z < stop_z (stop),
    or after max_hold_days bars (time). After a stop or time exit, wait for z to
    climb back above entry_z before entering again, so we don't re-buy a falling
    market the next day.
    """
    s = cfg["signal"]
    z = zscore(close, s["lookback"])

    weight = np.zeros(len(close))
    reason = np.array([None] * len(close), dtype=object)
    in_pos, held, armed = False, 0, True

    for i, zi in enumerate(z.to_numpy()):
        if np.isnan(zi):
            continue
        if not armed and zi > s["entry_z"]:
            armed = True
        if in_pos:
            held += 1
            if zi >= s["exit_z"]:
                in_pos, reason[i] = False, "target"
            elif zi < s["stop_z"]:
                in_pos, armed, reason[i] = False, False, "stop"
            elif held >= s["max_hold_days"]:
                in_pos, armed, reason[i] = False, False, "time"
        elif armed and zi < s["entry_z"]:
            in_pos, held = True, 0
        weight[i] = 1.0 if in_pos else 0.0

    return pd.Series(weight, index=close.index), pd.Series(reason, index=close.index), z
