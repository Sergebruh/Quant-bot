import copy

import pytest

from quantbot.config import load_config, validate


def test_default_config_loads():
    cfg = load_config()
    assert cfg["data"]["symbol"] == "SPY"


def test_rejects_negative_slippage():
    cfg = load_config()
    bad = copy.deepcopy(cfg)
    bad["costs"]["slippage_bps"] = -1
    with pytest.raises(ValueError, match="slippage"):
        validate(bad)


def test_rejects_misordered_z_levels():
    cfg = load_config()
    bad = copy.deepcopy(cfg)
    bad["signal"]["entry_z"] = 1.0  # entry above exit makes no sense
    with pytest.raises(ValueError, match="stop_z < entry_z < exit_z"):
        validate(bad)


def test_rejects_full_kelly_overshoot():
    cfg = load_config()
    bad = copy.deepcopy(cfg)
    bad["sizing"]["kelly_fraction"] = 2.0
    with pytest.raises(ValueError, match="kelly_fraction"):
        validate(bad)
