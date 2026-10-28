"""Download daily price bars and cache them on disk."""

from pathlib import Path

import pandas as pd

COLUMNS = ["open", "high", "low", "close", "volume"]


def load_prices(symbol, start, end=None, cache_dir="data", refresh=False):
    """Return daily OHLCV bars for `symbol`, using a CSV cache when present.

    Prices are split- and dividend-adjusted, so returns include dividends.
    """
    cache = Path(cache_dir) / f"{symbol}_{start}_{end or 'latest'}.csv"
    if cache.exists() and not refresh:
        return clean(pd.read_csv(cache, index_col=0, parse_dates=True))

    raw = _download(symbol, start, end)
    df = clean(raw)
    cache.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(cache)
    return df


def _download(symbol, start, end):
    import yfinance as yf

    df = yf.download(symbol, start=start, end=end, auto_adjust=True, progress=False)
    if df.empty:
        raise RuntimeError(f"no data returned for {symbol}")
    if isinstance(df.columns, pd.MultiIndex):
        # yfinance returns (field, ticker) columns; keep just the field name.
        df.columns = df.columns.get_level_values(0)
    return df


def clean(df):
    """Normalize columns and drop bad rows."""
    df = df.rename(columns=str.lower)
    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"price data is missing columns: {missing}")

    df = df[COLUMNS].copy()
    df.index = pd.to_datetime(df.index)
    df.index.name = "date"
    df = df[~df.index.duplicated(keep="last")].sort_index()

    prices = df[["open", "high", "low", "close"]]
    df = df[prices.notna().all(axis=1) & (prices > 0).all(axis=1)]
    return df
