import copy
import math

import numpy as np
import pandas as pd
import pytest

from quantbot.backtest import buy_and_hold, run_backtest
from quantbot.config import load_config
from quantbot.costs import commission, fill_price
from quantbot.metrics import max_drawdown, sharpe_ratio


@pytest.fixture
def cfg():
    return copy.deepcopy(load_config())


def prices_from(opens, closes):
    idx = pd.bdate_range("2024-01-01", periods=len(opens))
    return pd.DataFrame({"open": opens, "close": closes}, index=idx, dtype=float)


def test_commission_minimum_and_per_share():
    assert commission(0, 0.005, 1.0) == 0.0
    assert commission(10, 0.005, 1.0) == 1.0       # minimum applies
    assert commission(-1000, 0.005, 1.0) == 5.0    # sign doesn't matter


def test_slippage_hurts_both_sides():
    assert fill_price(100, +1, 2.0) == pytest.approx(100.02)
    assert fill_price(100, -1, 2.0) == pytest.approx(99.98)


def test_trades_fill_at_next_open_not_same_close(cfg):
    # Signal fires on day 1's close; the fill must use day 2's open (110),
    # not day 1's close (100).
    p = prices_from([100, 100, 110, 110], [100, 100, 110, 110])
    w = pd.Series([0, 1, 1, 1], index=p.index, dtype=float)
    _, trades, _ = run_backtest(p, w, cfg)
    assert trades[0]["entry_date"] == p.index[2]
    slip = cfg["costs"]["slippage_bps"] / 10_000
    assert trades[0]["entry_price"] == pytest.approx(110 * (1 + slip))


def test_round_trip_pnl_is_net_of_costs(cfg):
    cfg["backtest"]["starting_equity"] = 10_000
    p = prices_from([100, 100, 100, 100], [100, 100, 100, 100])
    w = pd.Series([1, 1, 0, 0], index=p.index, dtype=float)
    equity, trades, summary = run_backtest(p, w, cfg)
    t = trades[0]
    # Flat price: the only P&L is costs, so the trade must lose money.
    assert t["pnl"] < 0
    assert summary["net_profit"] == pytest.approx(equity.iloc[-1] - 10_000)
    assert summary["net_profit"] == pytest.approx(t["pnl"])


def test_zero_cost_buy_and_hold_tracks_price(cfg):
    cfg["costs"].update(commission_per_share=0, commission_min=0, slippage_bps=0)
    cfg["backtest"]["starting_equity"] = 1_000_000
    closes = np.linspace(100, 200, 50)
    p = prices_from(closes, closes)
    equity, _, _ = buy_and_hold(p, cfg)
    # Bought at day 1's open (~102); ends at 200.
    assert equity.iloc[-1] / 1_000_000 == pytest.approx(200 / closes[1], rel=1e-3)


def test_metrics():
    assert max_drawdown([100, 120, 90, 130]) == pytest.approx(0.25)
    assert sharpe_ratio([0.0, 0.0, 0.0]) == 0.0
    r = np.random.default_rng(0).normal(0.001, 0.01, 5000)
    assert sharpe_ratio(r) == pytest.approx(0.001 / 0.01 * np.sqrt(252), rel=0.15)


def test_holds_shares_while_target_is_unchanged(cfg):
    # Price drifts while the target stays at 1.0: no re-sizing orders, so the
    # only costs are one entry and one exit.
    p = prices_from([100, 101, 103, 106, 110, 110], [101, 103, 106, 110, 110, 110])
    w = pd.Series([1, 1, 1, 1, 0, 0], index=p.index, dtype=float)
    _, trades, _ = run_backtest(p, w, cfg)
    assert len(trades) == 1
    t = trades[0]
    assert t["shares"] == math.floor(100_000 / (101 * (1 + cfg["costs"]["slippage_bps"] / 1e4)))
    entry_fee = commission(t["shares"], cfg["costs"]["commission_per_share"], cfg["costs"]["commission_min"])
    exit_fee = entry_fee
    slip = t["shares"] * (101 + 110) * cfg["costs"]["slippage_bps"] / 1e4
    assert t["costs"] == pytest.approx(entry_fee + exit_fee + slip, rel=1e-6)
