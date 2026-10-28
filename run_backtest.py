"""Run the strategy on the configured symbol and compare with buy-and-hold."""

import argparse

import pandas as pd

from quantbot.backtest import buy_and_hold, run_backtest
from quantbot.config import load_config
from quantbot.data import load_prices
from quantbot.signals import mean_reversion_positions

ROWS = [
    ("Net profit (after costs)", "net_profit", "${:,.0f}"),
    ("Sharpe ratio", "sharpe", "{:.2f}"),
    ("CAGR", "cagr", "{:.2%}"),
    ("Max drawdown", "max_drawdown", "-{:.1%}"),
    ("Annual volatility", "annual_vol", "{:.1%}"),
    ("Trades", "trades", "{:d}"),
    ("Win rate", "win_rate", "{:.1%}"),
    ("Avg hold (days)", "avg_hold_days", "{:.1f}"),
    ("Total costs paid", "total_costs", "${:,.0f}"),
]


def print_report(results):
    names = list(results)
    print(f"{'':28}" + "".join(f"{n:>18}" for n in names))
    for label, key, fmt in ROWS:
        print(f"{label:28}" + "".join(f"{fmt.format(results[n][key]):>18}" for n in names))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=None)
    parser.add_argument("--refresh", action="store_true", help="re-download prices")
    args = parser.parse_args()

    cfg = load_config(args.config) if args.config else load_config()
    d = cfg["data"]
    prices = load_prices(d["symbol"], d["start"], d["end"], d["cache_dir"], args.refresh)

    weight, reasons, _ = mean_reversion_positions(prices["close"], cfg)
    _, trades, strat = run_backtest(prices, weight, cfg, reasons)
    _, _, bench = buy_and_hold(prices, cfg)

    print(f"{d['symbol']}  {prices.index[0].date()} -> {prices.index[-1].date()}\n")
    print_report({"Mean reversion": strat, "Buy & hold": bench})

    closed = pd.DataFrame([t for t in trades if t["exit_date"] is not None])
    if not closed.empty:
        print("\nExits by reason:")
        print(closed.groupby("reason")["pnl"].agg(["count", "sum", "mean"]).round(0))


if __name__ == "__main__":
    main()
