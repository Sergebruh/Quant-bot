"""Download intraday bars from Alpaca's market data API.

Credentials are injected by the environment's network proxy as the
APCA-API-KEY-ID / APCA-API-SECRET-KEY headers. If you run this on your own
machine instead, set ALPACA_API_KEY and ALPACA_SECRET_KEY and they'll be sent.
"""

import os
import time
from pathlib import Path

import pandas as pd
import requests

BARS_URL = "https://data.alpaca.markets/v2/stocks/{symbol}/bars"
CALENDAR_URL = "https://paper-api.alpaca.markets/v2/calendar"
MARKET_TZ = "America/New_York"


def _headers():
    key, secret = os.environ.get("ALPACA_API_KEY"), os.environ.get("ALPACA_SECRET_KEY")
    if key and secret:
        return {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    return {}


def fetch_bars(symbol, start, end, timeframe="5Min", feed="sip"):
    """Fetch all bars between start and end (ISO dates), following pagination."""
    params = {
        "timeframe": timeframe, "start": start, "end": end, "feed": feed,
        "adjustment": "raw", "limit": 10000,
    }
    rows, session = [], requests.Session()
    while True:
        for attempt in range(5):
            resp = session.get(BARS_URL.format(symbol=symbol), params=params,
                               headers=_headers(), timeout=60)
            if resp.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            break
        payload = resp.json()
        rows.extend(payload.get("bars") or [])
        token = payload.get("next_page_token")
        if not token:
            break
        params["page_token"] = token
    if not rows:
        raise RuntimeError(f"no bars returned for {symbol}")
    return _to_frame(rows)


def _to_frame(rows):
    df = pd.DataFrame(rows).rename(columns={
        "t": "time", "o": "open", "h": "high", "l": "low", "c": "close",
        "v": "volume", "vw": "vwap_bar", "n": "trades",
    })
    df["time"] = pd.to_datetime(df["time"], utc=True).dt.tz_convert(MARKET_TZ)
    return df.set_index("time")[["open", "high", "low", "close", "volume", "vwap_bar"]]


def regular_hours(df):
    """Keep only bars that start between 9:30 and 15:55 New York time."""
    t = df.index.hour * 60 + df.index.minute
    return df[(t >= 9 * 60 + 30) & (t < 16 * 60)]


def fetch_calendar(start, end):
    """Official open/close time for every trading day (handles half-days)."""
    resp = requests.get(CALENDAR_URL, params={"start": start, "end": end},
                        headers=_headers(), timeout=60)
    resp.raise_for_status()
    cal = pd.DataFrame(resp.json())[["date", "open", "close"]]
    return cal.set_index("date")


def trim_to_sessions(df, calendar):
    """Drop bars outside each day's official session, e.g. after a 1 PM close."""
    day = df.index.strftime("%Y-%m-%d")
    hhmm = df.index.strftime("%H:%M")
    opens = calendar["open"].reindex(day).to_numpy()
    closes = calendar["close"].reindex(day).to_numpy()
    keep = (hhmm >= opens) & (hhmm < closes)
    return df[keep]


def load_intraday(symbol, start, end, timeframe="5Min", feed="sip",
                  cache_dir="data", refresh=False):
    """Regular-hours intraday bars, cached to a compressed CSV."""
    cache = Path(cache_dir) / f"{symbol}_{timeframe}_{start}_{end}.csv.gz"
    cal_cache = Path(cache_dir) / f"calendar_{start}_{end}.csv"
    if cache.exists() and not refresh:
        df = pd.read_csv(cache, index_col=0)
        df.index = pd.to_datetime(df.index, utc=True).tz_convert(MARKET_TZ)
    else:
        df = regular_hours(fetch_bars(symbol, start, end, timeframe, feed))
        df = df[~df.index.duplicated(keep="last")].sort_index()
        cache.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(cache)
    if cal_cache.exists() and not refresh:
        calendar = pd.read_csv(cal_cache, index_col=0)
    else:
        calendar = fetch_calendar(start, end)
        calendar.to_csv(cal_cache)
    return trim_to_sessions(df, calendar)
