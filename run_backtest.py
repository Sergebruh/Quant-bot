"""Day-trading backtest: VWAP z-score mean reversion on 5-minute bars."""

import argparse

import pandas as pd

from quantbot.alpaca_data import load_intraday
from quantbot.backtest import buy_and_hold, run_backtest
from quantbot.config import load_config
from quantbot.intraday import session_dates, vwap_reversion_positions

ROWS = [
    ("Net profit (after costs)", "net_profit", "${:,.0f}"),
    ("Sharpe ratio", "sharpe", "{:.2f}"),
    ("CAGR", "cagr", "{:.2%}"),
    ("Max drawdown", "max_drawdown", "-{:.1%}"),
    ("Annual volatility", "annual_vol", "{:.1%}"),
    ("Trades", "trades", "{:d}"),
    ("Win rate", "win_rate", "{:.1%}"),
    ("Avg hold (5-min bars)", "avg_hold_bars", "{:.1f}"),
    ("Total costs paid", "total_costs", "${:,.0f}"),
]


def print_report(results):
    names = list(results)
    print(f"{'':28}" + "".join(f"{n:>18}" for n in names))
    for label, key, fmt in ROWS:
        print(f"{label:28}" + "".join(f"{fmt.format(results[n][key]):>18}" for n in names))


def run(cfg, bars):
    sessions = session_dates(bars.index)
    weight, reasons, _ = vwap_reversion_positions(bars, cfg)
    return run_backtest(bars, weight, cfg, reasons, sessions=sessions, force_flat=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=None)
    parser.add_argument("--refresh", action="store_true", help="re-download bars")
    args = parser.parse_args()

    cfg = load_config(args.config) if args.config else load_config()
    d = cfg["intraday_data"]
    bars = load_intraday(d["symbol"], d["start"], d["end"], d["timeframe"], d["feed"],
                         d["cache_dir"], args.refresh)

    _, trades, strat = run(cfg, bars)
    _, _, bench = buy_and_hold(bars, cfg, sessions=session_dates(bars.index))

    print(f"{d['symbol']} {d['timeframe']}  {bars.index[0].date()} -> {bars.index[-1].date()}\n")
    print_report({"VWAP reversion": strat, "Buy & hold": bench})

    closed = pd.DataFrame([t for t in trades if t["exit_date"] is not None])
    if not closed.empty:
        print("\nExits by reason:")
        print(closed.groupby("reason")["pnl"].agg(["count", "sum", "mean"]).round(0))


if __name__ == "__main__":
    main()
