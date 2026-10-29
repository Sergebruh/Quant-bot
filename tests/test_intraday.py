import copy

import numpy as np
import pandas as pd
import pytest

from quantbot.alpaca_data import trim_to_sessions
from quantbot.backtest import run_backtest
from quantbot.config import load_config
from quantbot.intraday import session_dates, vwap_reversion_positions, vwap_zscore


def make_bars(days=3, per_day=78, seed=0):
    rng = np.random.default_rng(seed)
    idx = []
    for d in pd.bdate_range("2024-03-04", periods=days):
        start = pd.Timestamp(d.date()).tz_localize("America/New_York") + pd.Timedelta("9h30min")
        idx += list(pd.date_range(start, periods=per_day, freq="5min"))
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.001, len(idx))))
    return pd.DataFrame(
        {"open": close, "close": close, "vwap_bar": close,
         "volume": rng.integers(1_000, 5_000, len(idx)).astype(float)},
        index=pd.DatetimeIndex(idx),
    )


def test_vwap_resets_each_morning_and_has_no_lookahead():
    bars = make_bars()
    vwap, z = vwap_zscore(bars)
    first_bars = session_dates(bars.index).groupby(bars.index.date).head(1).index
    # At each day's first bar, VWAP equals that bar's price (fresh start).
    assert np.allclose(vwap.loc[first_bars], bars.loc[first_bars, "vwap_bar"])
    _, z_cut = vwap_zscore(bars.iloc[:100])
    pd.testing.assert_series_equal(z.iloc[:100], z_cut)


def test_force_flat_never_holds_overnight():
    cfg = copy.deepcopy(load_config())
    bars = make_bars()
    always_long = pd.Series(1.0, index=bars.index)
    sessions = session_dates(bars.index)
    _, trades, _ = run_backtest(bars, always_long, cfg, sessions=sessions, force_flat=True)
    assert len(trades) == 3                       # one round trip per day
    for t in trades:
        assert t["entry_date"].date() == t["exit_date"].date()
        assert t["exit_date"].strftime("%H:%M") == "15:55"
        assert t["reason"] == "close"


def test_no_entries_during_warmup_or_after_last_entry():
    cfg = copy.deepcopy(load_config())
    bars = make_bars(days=5, seed=3)
    w, _, _ = vwap_reversion_positions(bars, cfg)
    entries = w[(w > 0) & (w.shift(1, fill_value=0) == 0)]
    hhmm = entries.index.strftime("%H:%M")
    assert (hhmm >= "10:00").all() and (hhmm < "15:30").all()


def test_trim_drops_bars_after_half_day_close():
    bars = make_bars(days=1)
    day = bars.index[0].strftime("%Y-%m-%d")
    cal = pd.DataFrame({"open": ["09:30"], "close": ["13:00"]}, index=[day])
    kept = trim_to_sessions(bars, cal)
    assert len(kept) == 42
    assert kept.index[-1].strftime("%H:%M") == "12:55"
