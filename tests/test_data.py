import numpy as np
import pandas as pd

from quantbot import data


def make_raw():
    idx = pd.to_datetime(["2024-01-03", "2024-01-02", "2024-01-04", "2024-01-04", "2024-01-05"])
    return pd.DataFrame(
        {
            "Open": [101, 100, 102, 102.5, np.nan],
            "High": [102, 101, 103, 103.5, 104],
            "Low": [100, 99, 101, 101.5, 102],
            "Close": [101.5, 100.5, 102.5, 103, 103],
            "Volume": [1000, 1000, 1000, 1000, 1000],
        },
        index=idx,
    )


def test_clean_sorts_dedupes_and_drops_bad_rows():
    df = data.clean(make_raw())
    assert list(df.columns) == data.COLUMNS
    assert df.index.is_monotonic_increasing
    assert not df.index.duplicated().any()
    assert len(df) == 3                       # duplicate and NaN rows removed
    assert df.loc["2024-01-04", "close"] == 103  # keeps the last duplicate


def test_load_prices_uses_cache(tmp_path, monkeypatch):
    calls = []

    def fake_download(symbol, start, end):
        calls.append(symbol)
        return make_raw()

    monkeypatch.setattr(data, "_download", fake_download)
    first = data.load_prices("SPY", "2024-01-01", cache_dir=tmp_path)
    second = data.load_prices("SPY", "2024-01-01", cache_dir=tmp_path)

    assert calls == ["SPY"]  # second call read from disk
    pd.testing.assert_frame_equal(first, second, check_freq=False)
