"""Day-trading backtest on 5-minute bars (strategy chosen in config.yaml)."""

import argparse

import pandas as pd

from quantbot.alpaca_data import load_intraday
from quantbot.backtest import buy_and_hold, run_backtest
from quantbot.config import load_config
from quantbot.intraday import session_dates, vwap_reversion_positions
from quantbot.momentum import momentum_positions

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


STRATEGY_NAMES = {"momentum": "Momentum", "vwap_reversion": "VWAP reversion"}


def period_slice(bars, cfg, period):
    """'dev' = data up to dev_end, 'holdout' = after it, 'all' = everything."""
    dev_end = pd.Timestamp(cfg["intraday_data"]["dev_end"]).date()
    day = bars.index.date
    if period == "dev":
        return bars[day <= dev_end]
    if period == "holdout":
        return bars[day > dev_end]
    return bars


def run(cfg, bars, strategy=None, period="all"):
    """Signals are computed on all bars (they only look backward), then the
    backtest runs on the requested period."""
    strategy = strategy or cfg.get("strategy", "momentum")
    if strategy == "momentum":
        weight, reasons = momentum_positions(bars, cfg)
    else:
        weight, reasons, _ = vwap_reversion_positions(bars, cfg)
    bars = period_slice(bars, cfg, period)
    sessions = session_dates(bars.index)
    return run_backtest(bars, weight.reindex(bars.index), cfg, reasons.reindex(bars.index),
                        sessions=sessions, force_flat=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=None)
    parser.add_argument("--refresh", action="store_true", help="re-download bars")
    parser.add_argument("--strategy", choices=list(STRATEGY_NAMES), default=None)
    parser.add_argument("--holdout", action="store_true",
                        help="test on the locked holdout period (do this once, at the end)")
    parser.add_argument("--all", action="store_true", help="run on the full history")
    args = parser.parse_args()

    cfg = load_config(args.config) if args.config else load_config()
    d = cfg["intraday_data"]
    bars = load_intraday(d["symbol"], d["start"], d["end"], d["timeframe"], d["feed"],
                         d["cache_dir"], args.refresh)

    strategy = args.strategy or cfg.get("strategy", "momentum")
    period = "holdout" if args.holdout else "all" if args.all else "dev"
    _, trades, strat = run(cfg, bars, strategy, period)
    window = period_slice(bars, cfg, period)
    _, _, bench = buy_and_hold(window, cfg, sessions=session_dates(window.index))

    print(f"{d['symbol']} {d['timeframe']}  {window.index[0].date()} -> "
          f"{window.index[-1].date()}  [{period}]\n")
    print_report({STRATEGY_NAMES[strategy]: strat, "Buy & hold": bench})

    closed = pd.DataFrame([t for t in trades if t["exit_date"] is not None])
    if not closed.empty:
        print("\nExits by reason:")
        print(closed.groupby("reason")["pnl"].agg(["count", "sum", "mean"]).round(0))
        if "side" in closed:
            print("\nBy side:")
            print(closed.groupby("side")["pnl"].agg(["count", "sum", "mean"]).round(0))


if __name__ == "__main__":
    main()
