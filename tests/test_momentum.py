import copy

import numpy as np
import pandas as pd
import pytest

from quantbot.backtest import run_backtest
from quantbot.config import load_config
from quantbot.intraday import session_dates
from quantbot.momentum import momentum_positions, noise_bands
from tests.test_intraday import make_bars


@pytest.fixture
def cfg():
    c = copy.deepcopy(load_config())
    c["costs"].update(commission_per_share=0, commission_min=0, slippage_bps=0)
    return c


def test_noise_bands_have_no_lookahead():
    bars = make_bars(days=30, seed=5)
    up_full, lo_full, _ = noise_bands(bars, 14)
    cut = bars.iloc[: 20 * 78]
    up_cut, lo_cut, _ = noise_bands(cut, 14)
    pd.testing.assert_series_equal(up_full.iloc[: len(cut)], up_cut)
    pd.testing.assert_series_equal(lo_full.iloc[: len(cut)], lo_cut)


def test_noise_bands_need_full_lookback_and_use_gap():
    bars = make_bars(days=16, seed=2)
    up, lo, sigma = noise_bands(bars, 14)
    day = np.array(bars.index.date)
    days = sorted(set(day))
    assert sigma[day == days[13]].isna().all()     # only 13 prior days
    assert sigma[day == days[14]].notna().all()    # 14 prior days available
    valid = up.notna() & lo.notna()
    assert (up[valid] >= lo[valid]).all()


def test_short_trade_profits_when_price_falls(cfg):
    idx = pd.bdate_range("2024-01-01", periods=4)
    p = pd.DataFrame({"open": [100, 100, 90, 90], "close": [100, 100, 90, 90]},
                     index=idx, dtype=float)
    w = pd.Series([-1, -1, 0, 0], index=idx, dtype=float)
    equity, trades, _ = run_backtest(p, w, cfg)
    assert trades[0]["side"] == "short"
    assert trades[0]["pnl"] == pytest.approx(1000 * 10)   # 1,000 shares x $10
    assert equity.iloc[-1] == pytest.approx(110_000)


def test_flip_long_to_short_records_two_trades(cfg):
    idx = pd.bdate_range("2024-01-01", periods=5)
    p = pd.DataFrame({"open": [100, 100, 110, 100, 100], "close": [100, 100, 110, 100, 100]},
                     index=idx, dtype=float)
    w = pd.Series([1, -1, -1, 0, 0], index=idx, dtype=float)
    _, trades, _ = run_backtest(p, w, cfg)
    assert [t["side"] for t in trades] == ["long", "short"]
    assert trades[0]["pnl"] == pytest.approx(1000 * 10)      # bought 100, sold 110
    assert trades[1]["pnl"] == pytest.approx(1000 * 10)      # shorted 110, covered 100


def test_momentum_only_decides_on_the_half_hour(cfg):
    bars = make_bars(days=25, seed=11)
    w, _ = momentum_positions(bars, cfg)
    changes = w[w.diff().fillna(0) != 0]
    close_minute = (changes.index + pd.Timedelta(minutes=5)).minute
    # Position changes happen at :00/:30 decisions, or the daily reset at the open.
    first_bar = changes.index.strftime("%H:%M") == "09:30"
    assert set(close_minute[~first_bar]) <= {0, 30}
