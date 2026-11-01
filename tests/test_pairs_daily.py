import copy

import numpy as np
import pandas as pd
import pytest

from quantbot.config import load_config
from quantbot.pairs import run_pair_backtest
from quantbot.pairs_daily import daily_pair_positions, rolling_spread_z


def make_daily_pair(n=400, seed=0, beta=1.0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2020-01-01", periods=n)
    lb = np.log(50) + np.cumsum(rng.normal(0, 0.01, n))
    noise = np.zeros(n)
    for t in range(1, n):
        noise[t] = 0.8 * noise[t - 1] + rng.normal(0, 0.005)
    la = 0.2 + beta * lb + noise
    return pd.DataFrame({"open_a": np.exp(la), "close_a": np.exp(la),
                         "open_b": np.exp(lb), "close_b": np.exp(lb)}, index=idx)


@pytest.fixture
def cfg():
    c = copy.deepcopy(load_config())
    c["pairs"]["slippage_bps"] = {"A": 0.0, "B": 0.0}
    c["pairs"]["costs"] = {"commission_per_share": 0.0, "commission_min": 0.0}
    c["pairs"]["borrow_bps_per_year"] = 0.0
    return c


def test_rolling_z_has_no_lookahead():
    pair = make_daily_pair()
    beta, z = rolling_spread_z(pair, 60)
    beta2, z2 = rolling_spread_z(pair.iloc[:300], 60)
    pd.testing.assert_series_equal(z.iloc[:300], z2)
    assert z.iloc[:60].isna().all() and z.iloc[60:].notna().all()


def test_holds_overnight_and_profits_on_reverting_spread(cfg):
    pair = make_daily_pair(seed=3)
    pos, reasons, beta, _ = daily_pair_positions(pair, cfg)
    _, trades, summary = run_pair_backtest(pair, pos, beta, cfg, ("A", "B"), reasons,
                                           force_flat=False)
    assert len(trades) >= 5
    assert any(t["bars"] > 1 for t in trades)          # held across days
    assert summary["net_profit"] > 0


def test_borrow_fee_is_charged_on_the_short_leg(cfg):
    pair = make_daily_pair(seed=3)
    pos, reasons, beta, _ = daily_pair_positions(pair, cfg)
    _, t0, s0 = run_pair_backtest(pair, pos, beta, cfg, ("A", "B"), reasons, force_flat=False)
    cfg["pairs"]["borrow_bps_per_year"] = 100.0
    _, t1, s1 = run_pair_backtest(pair, pos, beta, cfg, ("A", "B"), reasons, force_flat=False)
    assert s1["net_profit"] < s0["net_profit"]
    assert all(b["costs"] > a["costs"] for a, b in zip(t0, t1))
