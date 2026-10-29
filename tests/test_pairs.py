import copy

import numpy as np
import pandas as pd
import pytest

from quantbot.config import load_config
from quantbot.pairs import align, daily_spread_params, pair_positions, run_pair_backtest


def make_pair(days=30, per_day=78, seed=0, beta=1.0):
    rng = np.random.default_rng(seed)
    idx = []
    for d in pd.bdate_range("2024-03-04", periods=days):
        start = pd.Timestamp(d.date()).tz_localize("America/New_York") + pd.Timedelta("9h30min")
        idx += list(pd.date_range(start, periods=per_day, freq="5min"))
    idx = pd.DatetimeIndex(idx)
    lb = np.log(50) + np.cumsum(rng.normal(0, 0.001, len(idx)))
    noise = np.zeros(len(idx))
    for t in range(1, len(idx)):                      # stationary AR(1) spread
        noise[t] = 0.9 * noise[t - 1] + rng.normal(0, 0.0005)
    la = 0.3 + beta * lb + noise
    a = pd.DataFrame({"open": np.exp(la), "close": np.exp(la)}, index=idx)
    b = pd.DataFrame({"open": np.exp(lb), "close": np.exp(lb)}, index=idx)
    return a, b


@pytest.fixture
def cfg():
    c = copy.deepcopy(load_config())
    c["pairs"]["slippage_bps"] = {"A": 0.0, "B": 0.0}
    c["pairs"]["costs"] = {"commission_per_share": 0.0, "commission_min": 0.0}
    return c


def test_params_use_only_previous_days():
    a, b = make_pair(days=40)
    pair = align(a, b)
    full = daily_spread_params(pair, 20, 5)
    cut = daily_spread_params(pair.iloc[: 30 * 78], 20, 5)
    pd.testing.assert_frame_equal(full.iloc[:30], cut)
    assert full["beta"].iloc[:20].isna().all() and full["beta"].iloc[20:].notna().all()


def test_beta_recovers_true_hedge_ratio():
    a, b = make_pair(days=40, beta=1.5, seed=3)
    params = daily_spread_params(align(a, b), 20, 5)
    assert params["beta"].iloc[-1] == pytest.approx(1.5, abs=0.15)


def test_mean_reverting_spread_makes_money_without_costs(cfg):
    a, b = make_pair(days=40, seed=7)
    pair = align(a, b)
    pos, reasons, beta, _ = pair_positions(pair, cfg)
    _, trades, summary = run_pair_backtest(pair, pos, beta, cfg, ("A", "B"), reasons)
    assert len(trades) >= 5
    assert summary["net_profit"] > 0


def test_legs_are_hedged_and_flat_overnight(cfg):
    a, b = make_pair(days=40, seed=7, beta=1.2)
    pair = align(a, b)
    pos, reasons, beta, _ = pair_positions(pair, cfg)
    _, trades, _ = run_pair_backtest(pair, pos, beta, cfg, ("A", "B"), reasons)
    for t in trades:
        assert t["entry_date"].date() == t["exit_date"].date()
        assert np.sign(t["shares"]) == -np.sign(t["shares_b"])     # one long, one short
        i = pair.index.get_loc(t["entry_date"])
        dollars_a = abs(t["shares"]) * pair["open_a"].iloc[i]
        dollars_b = abs(t["shares_b"]) * pair["open_b"].iloc[i]
        assert dollars_b / dollars_a == pytest.approx(t["beta"], rel=0.02)
