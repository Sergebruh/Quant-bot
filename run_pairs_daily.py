"""Multi-day pairs backtest (held overnight): each pair, plus an equal-weight
portfolio, next to SPY buy-and-hold. Same costs as run_pairs.py plus a
short-borrow fee.

    python run_pairs_daily.py              # development period
    python run_pairs_daily.py --holdout    # locked holdout (run once, at the end)
"""

import argparse
import copy

import numpy as np
import pandas as pd

from quantbot.alpaca_data import load_daily
from quantbot.config import load_config
from quantbot.metrics import summarize
from quantbot.pairs import run_pair_backtest
from quantbot.pairs_daily import align_daily, daily_pair_positions


def daily_cfg(cfg):
    """Engine settings for daily pairs: measured slippage from `pairs`,
    leverage and borrow fee from `pairs_daily`."""
    c = copy.deepcopy(cfg)
    c["pairs"]["gross_leverage"] = cfg["pairs_daily"]["gross_leverage"]
    c["pairs"]["borrow_bps_per_year"] = cfg["pairs_daily"]["borrow_bps_per_year"]
    return c


def stressed(cfg):
    s = copy.deepcopy(cfg)
    p = s["pairs"]
    p["costs"] = p["stress_costs"]
    p["slippage_bps"] = {k: v * p["stress_slippage_mult"] for k, v in p["slippage_bps"].items()}
    p["borrow_bps_per_year"] = p.get("borrow_bps_per_year", 0) * 4
    return s


def load(cfg, sym):
    d = cfg["intraday_data"]
    return load_daily(sym, d["start"], d["end"], d["feed"], d["cache_dir"])


def period_mask(index, cfg, period):
    dev_end = pd.Timestamp(cfg["intraday_data"]["dev_end"])
    if period == "dev":
        return index <= dev_end
    if period == "holdout":
        return index > dev_end
    return np.ones(len(index), dtype=bool)


def run_pair(cfg, pair, symbols, period, equity=None):
    """Signals use all history (backward-looking only); the backtest runs on `period`."""
    pos, reasons, beta, _ = daily_pair_positions(pair, cfg)
    m = period_mask(pair.index, cfg, period)
    c = copy.deepcopy(cfg)
    if equity is not None:
        c["backtest"]["starting_equity"] = equity
    return run_pair_backtest(pair[m], pos[m], beta[m], c, symbols, reasons[m], force_flat=False)


def portfolio(cfg, pairs, period):
    start = cfg["backtest"]["starting_equity"]
    curves, trades = [], []
    for symbols, pair in pairs.items():
        eq, tr, _ = run_pair(cfg, pair, symbols, period, start / len(pairs))
        curves.append(eq)
        trades += tr
    total = pd.concat(curves, axis=1).ffill().bfill().sum(axis=1)
    return summarize(total, trades, start, cfg["backtest"]["risk_free_rate"]), total


def line(name, r, rs=None):
    out = (f"{name:14} net ${r['net_profit']:>10,.0f}  Sharpe {r['sharpe']:5.2f}  "
           f"maxDD {r['max_drawdown']:5.1%}  trades {r['trades']:4d}  win {r['win_rate']:5.1%}  "
           f"hold {r['avg_hold_days']:4.1f}d")
    if rs is not None:
        out += f"  | stress: net ${rs['net_profit']:>9,.0f} Sharpe {rs['sharpe']:5.2f}"
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--holdout", action="store_true")
    args = parser.parse_args()
    period = "holdout" if args.holdout else "dev"

    cfg = daily_cfg(load_config())
    pairs = {tuple(s): align_daily(load(cfg, s[0]), load(cfg, s[1]))
             for s in cfg["pairs"]["symbols"]}
    print(f"Multi-day pairs, daily bars, held overnight  [{period}]\n")
    for symbols, pair in pairs.items():
        _, _, r = run_pair(cfg, pair, symbols, period)
        _, _, rs = run_pair(stressed(cfg), pair, symbols, period)
        print(line("/".join(symbols), r, rs))
    print()
    r, _ = portfolio(cfg, pairs, period)
    rs, _ = portfolio(stressed(cfg), pairs, period)
    print(line("PORTFOLIO", r, rs))

    spy = load(cfg, "SPY")
    spy = spy[period_mask(spy.index, cfg, period)]
    shares = cfg["backtest"]["starting_equity"] / spy["open"].iloc[0]
    eq = shares * spy["close"]
    b = summarize(eq, [], cfg["backtest"]["starting_equity"], 0.0)
    print(f"{'SPY buy&hold':14} net ${b['net_profit']:>10,.0f}  Sharpe {b['sharpe']:5.2f}  "
          f"maxDD {b['max_drawdown']:5.1%}   (dividends included)")


if __name__ == "__main__":
    main()
