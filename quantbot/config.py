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

    isig = cfg.get("intraday_signal")
    if isig:
        if not isig["stop_z"] < isig["entry_z"] < isig["exit_z"]:
            raise ValueError("intraday_signal: need stop_z < entry_z < exit_z")
        if isig["max_hold_bars"] < 1:
            raise ValueError("intraday_signal.max_hold_bars must be at least 1")

    mom = cfg.get("momentum_signal")
    if mom:
        if mom["lookback_days"] < 2:
            raise ValueError("momentum_signal.lookback_days must be at least 2")
        if mom["band_mult"] <= 0:
            raise ValueError("momentum_signal.band_mult must be positive")
        if not set(mom["decision_minutes"]) <= set(range(0, 60, 5)):
            raise ValueError("momentum_signal.decision_minutes must be multiples of 5")
    if cfg.get("strategy", "momentum") not in ("momentum", "vwap_reversion"):
        raise ValueError("strategy must be momentum or vwap_reversion")

    reg = cfg["regime"]
    if reg["n_states"] < 2:
        raise ValueError("regime.n_states must be at least 2")
    if reg.get("mode", "filter") not in ("filter", "scale"):
        raise ValueError("regime.mode must be filter or scale")
    if not 0 < reg.get("trend_prob_threshold", 0.5) < 1:
        raise ValueError("regime.trend_prob_threshold must be between 0 and 1")
    if not 0 < reg["calm_prob_threshold"] < 1:
        raise ValueError("regime.calm_prob_threshold must be between 0 and 1")

    size = cfg["sizing"]
    if not 0 < size["kelly_fraction"] <= 1:
        raise ValueError("sizing.kelly_fraction must be in (0, 1]")
    if size.get("max_leverage", 1.0) <= 0:
        raise ValueError("sizing.max_leverage must be positive")
    if size.get("method", "none") not in ("none", "vol_target"):
        raise ValueError("sizing.method must be none or vol_target")
    if size["max_position"] <= 0:
        raise ValueError("sizing.max_position must be positive")
    if not 0 < size["max_drawdown_halt"] < 1:
        raise ValueError("sizing.max_drawdown_halt must be between 0 and 1")
