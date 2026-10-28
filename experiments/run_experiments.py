"""Re-run every variant from RESEARCH_LOG run 3 (dev period by default).

    python experiments/run_experiments.py            # development period
    python experiments/run_experiments.py holdout    # locked holdout (already spent)
"""

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from quantbot.alpaca_data import load_intraday  # noqa: E402
from quantbot.config import load_config  # noqa: E402
from run_backtest import run  # noqa: E402

BASE = load_config()
# Start every variant from the plain baseline, whatever config.yaml defaults to.
BASE["sizing"].update(method="none", kelly=False, max_leverage=1.0)
BASE["regime"]["enabled"] = False

VT = {"sizing__method": "vol_target"}
HMM = {"regime__enabled": True}
KELLY = {"sizing__kelly": True}
VARIANTS = [
    ("A baseline", {}),
    ("B vol-target 1x", VT),
    ("C HMM filter", HMM),
    ("D vol-target 1x + HMM", {**VT, **HMM}),
    ("E D + half Kelly, cap 1x", {**VT, **HMM, **KELLY}),
    ("F D + half Kelly, cap 2x", {**VT, **HMM, **KELLY, "sizing__max_leverage": 2.0}),
    ("G D + half Kelly, cap 4x", {**VT, **HMM, **KELLY, "sizing__max_leverage": 4.0}),
]


def variant(**overrides):
    cfg = copy.deepcopy(BASE)
    for key, value in overrides.items():
        section, name = key.split("__")
        cfg[section][name] = value
    return cfg


def main():
    period = sys.argv[1] if len(sys.argv) > 1 else "dev"
    d = BASE["intraday_data"]
    bars = load_intraday(d["symbol"], d["start"], d["end"], d["timeframe"], d["feed"],
                         d["cache_dir"])
    for name, overrides in VARIANTS:
        cfg = variant(**overrides)
        _, _, r = run(cfg, bars, "momentum", period)
        stressed = copy.deepcopy(cfg)
        stressed["costs"] = cfg["stress_costs"]
        _, _, rs = run(stressed, bars, "momentum", period)
        print(f"{name:28} net ${r['net_profit']:>10,.0f}  Sharpe {r['sharpe']:5.2f}  "
              f"maxDD {r['max_drawdown']:5.1%}  | stress: net ${rs['net_profit']:>9,.0f}  "
              f"Sharpe {rs['sharpe']:5.2f}")


if __name__ == "__main__":
    main()
