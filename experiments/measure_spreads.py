"""Measure each symbol's typical bid-ask spread from Alpaca SIP quotes.

Samples the first valid quote at several times of day on random trading days
(dev period only) and sets per-side slippage = max(0.5 bp, 2.5 x median
half-spread). Prints a YAML block for config.yaml's pairs.slippage_bps.

    python experiments/measure_spreads.py KO PEP XOM ...
"""

import random
import sys
import time
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from quantbot.alpaca_data import _headers  # noqa: E402

QUOTES_URL = "https://data.alpaca.markets/v2/stocks/{symbol}/quotes"
TIMES = ["10:00:00", "12:30:00", "15:00:00"]


def sample_days(n=30, seed=7, dev_end="2024-10-31"):
    cal = pd.read_csv(sorted(Path("data").glob("calendar_*.csv"))[0], index_col=0)
    days = [d for d in cal.index if cal.loc[d, "close"] == "16:00" and d <= dev_end]
    random.seed(seed)
    return sorted(random.sample(days, n))


def half_spread_bps(symbol, day, hhmmss, session):
    start = pd.Timestamp(f"{day} {hhmmss}", tz="America/New_York").tz_convert("UTC")
    params = {"start": start.isoformat(), "end": (start + pd.Timedelta(seconds=2)).isoformat(),
              "feed": "sip", "limit": 20}
    for attempt in range(5):
        r = session.get(QUOTES_URL.format(symbol=symbol), params=params,
                        headers=_headers(), timeout=30)
        if r.status_code == 429:
            time.sleep(2 ** attempt)
            continue
        r.raise_for_status()
        break
    for q in r.json().get("quotes") or []:
        if q["ap"] > 0 and q["bp"] > 0 and q["ap"] >= q["bp"]:
            mid = (q["ap"] + q["bp"]) / 2
            return (q["ap"] - q["bp"]) / 2 / mid * 1e4
    return None


def main():
    symbols = sys.argv[1:]
    days = sample_days()
    session = requests.Session()
    print("slippage_bps:")
    for sym in symbols:
        vals = [v for d in days for t in TIMES
                if (v := half_spread_bps(sym, d, t, session)) is not None]
        med = pd.Series(vals).median()
        slip = max(0.5, round(2.5 * med, 2))
        print(f"    {sym}: {slip}    # median half-spread {med:.2f} bp, n={len(vals)}", flush=True)


if __name__ == "__main__":
    main()
