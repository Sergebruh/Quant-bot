import copy

import numpy as np
import pandas as pd

from quantbot.config import load_config
from quantbot.signals import mean_reversion_positions, zscore


def test_zscore_has_no_lookahead():
    close = pd.Series(np.random.default_rng(1).normal(100, 1, 200))
    z_full = zscore(close, 20)
    z_cut = zscore(close.iloc[:150], 20)
    # Values up to day 149 must not change when future data is added.
    pd.testing.assert_series_equal(z_full.iloc[:150], z_cut)


def test_enters_on_dip_and_exits_on_reversion():
    cfg = copy.deepcopy(load_config())
    cfg["signal"].update(lookback=5, entry_z=-1.0, exit_z=0.0, stop_z=-10, max_hold_days=50)
    close = pd.Series([100, 100.5, 99.5, 100, 100.2, 95, 96, 101, 101, 101.0])
    w, reason, _ = mean_reversion_positions(close, cfg)
    assert w.iloc[5] == 1.0                 # dip -> long
    assert w.iloc[7] == 0.0                 # bounced above mean -> flat
    assert reason.iloc[7] == "target"
