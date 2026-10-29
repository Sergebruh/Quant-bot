"""Intraday pairs-trading backtest: each pair, plus an equal-weight portfolio.

    python run_pairs.py              # development period
    python run_pairs.py --holdout    # locked holdout (run once, at the end)
"""

import argparse
import copy

import numpy as np
import pandas as pd

from quantbot.alpaca_data import load_intraday
from quantbot.backtest import buy_and_hold
from quantbot.config import load_config
from quantbot.intraday import session_dates
from quantbot.metrics import summarize
from quantbot.pairs import align, pair_positions, run_pair_backtest


def load_pair(cfg, sym_a, sym_b):
    d, p = cfg["intraday_data"], cfg["pairs"]
    a = load_intraday(sym_a, d["start"], d["end"], d["timeframe"], d["feed"], d["cache_dir"],
                      adjustment=p["adjustment"])
    b = load_intraday(sym_b, d["start"], d["end"], d["timeframe"], d["feed"], d["cache_dir"],
                      adjustment=p["adjustment"])
    return align(a, b)


def period_mask(index, cfg, period):
    dev_end = pd.Timestamp(cfg["intraday_data"]["dev_end"]).date()
    day = np.array(index.date)
    if period == "dev":
        return day <= dev_end
    if period == "holdout":
        return day > dev_end
    return np.ones(len(index), dtype=bool)


def stressed(cfg):
    s = copy.deepcopy(cfg)
    p = s["pairs"]
    p["costs"] = p["stress_costs"]
    p["slippage_bps"] = {k: v * p["stress_slippage_mult"] for k, v in p["slippage_bps"].items()}
    return s


def run_pair(cfg, pair, symbols, period, equity=None):
    """Signals use all history (backward-looking only); the backtest runs on `period`."""
    pos, reasons, beta, _ = pair_positions(pair, cfg)
    m = period_mask(pair.index, cfg, period)
    c = copy.deepcopy(cfg)
    if equity is not None:
        c["backtest"]["starting_equity"] = equity
    return run_pair_backtest(pair[m], pos[m], beta[m], c, symbols, reasons[m])


def portfolio(cfg, pairs, period):
    """Equal capital per pair; returns the summed daily equity and summary."""
    start = cfg["backtest"]["starting_equity"]
    curves, trades = [], []
    for symbols, pair in pairs.items():
        eq, tr, _ = run_pair(cfg, pair, symbols, period, start / len(pairs))
        curves.append(eq.groupby(np.array(eq.index.date)).last())
        trades += tr
    total = pd.concat(curves, axis=1).ffill().sum(axis=1)
    return summarize(total, trades, start, cfg["backtest"]["risk_free_rate"])


def line(name, r, rs=None):
    out = (f"{name:14} net ${r['net_profit']:>10,.0f}  Sharpe {r['sharpe']:5.2f}  "
           f"maxDD {r['max_drawdown']:5.1%}  trades {r['trades']:5d}  win {r['win_rate']:5.1%}")
    if rs is not None:
        out += f"  | stress: net ${rs['net_profit']:>10,.0f} Sharpe {rs['sharpe']:5.2f}"
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--holdout", action="store_true")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    period = "holdout" if args.holdout else "all" if args.all else "dev"

    cfg = load_config()
    pairs = {tuple(s): load_pair(cfg, *s) for s in cfg["pairs"]["symbols"]}
    print(f"Intraday pairs, 5-min bars  [{period}]\n")
    for symbols, pair in pairs.items():
        _, _, r = run_pair(cfg, pair, symbols, period)
        _, _, rs = run_pair(stressed(cfg), pair, symbols, period)
        print(line("/".join(symbols), r, rs))
    print()
    print(line("PORTFOLIO", portfolio(cfg, pairs, period), portfolio(stressed(cfg), pairs, period)))

    d = cfg["intraday_data"]
    spy = load_intraday("SPY", d["start"], d["end"], d["timeframe"], d["feed"], d["cache_dir"])
    spy = spy[period_mask(spy.index, cfg, period)]
    _, _, b = buy_and_hold(spy, cfg, sessions=session_dates(spy.index))
    print(f"{'SPY buy&hold':14} net ${b['net_profit']:>10,.0f}  Sharpe {b['sharpe']:5.2f}  "
          f"maxDD {b['max_drawdown']:5.1%}")


if __name__ == "__main__":
    main()
