"""Load and validate config.yaml."""

from pathlib import Path

import yaml

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config.yaml"

REQUIRED_SECTIONS = ("data", "costs", "backtest", "signal", "regime", "sizing")


def load_config(path=DEFAULT_PATH):
    """Read the YAML config and check that it makes sense."""
    with open(path) as f:
        cfg = yaml.safe_load(f)
    validate(cfg)
    return cfg


def validate(cfg):
    missing = [s for s in REQUIRED_SECTIONS if s not in cfg]
    if missing:
        raise ValueError(f"config is missing sections: {missing}")

    costs = cfg["costs"]
    if costs["commission_per_share"] < 0 or costs["commission_min"] < 0:
        raise ValueError("commissions can't be negative")
    if costs["slippage_bps"] < 0:
        raise ValueError("slippage can't be negative")

    sig = cfg["signal"]
    if sig["lookback"] < 2:
        raise ValueError("signal.lookback must be at least 2")
    if not sig["stop_z"] < sig["entry_z"] < sig["exit_z"]:
        raise ValueError("need stop_z < entry_z < exit_z")
    if sig["max_hold_days"] < 1:
        raise ValueError("signal.max_hold_days must be at least 1")

    reg = cfg["regime"]
    if reg["n_states"] < 2:
        raise ValueError("regime.n_states must be at least 2")
    if not 0 < reg["calm_prob_threshold"] < 1:
        raise ValueError("regime.calm_prob_threshold must be between 0 and 1")

    size = cfg["sizing"]
    if not 0 < size["kelly_fraction"] <= 1:
        raise ValueError("sizing.kelly_fraction must be in (0, 1]")
    if size["max_position"] <= 0:
        raise ValueError("sizing.max_position must be positive")
    if not 0 < size["max_drawdown_halt"] < 1:
        raise ValueError("sizing.max_drawdown_halt must be between 0 and 1")
