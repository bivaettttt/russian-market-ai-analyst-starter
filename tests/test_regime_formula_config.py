import json

from app.services.market_regime import normalize_market_regime_formula_config


def test_market_regime_formula_config_defaults_are_serializable():
    config = normalize_market_regime_formula_config(None)

    for key in [
        "risk_on_threshold",
        "risk_off_threshold",
        "strong_risk_off_threshold",
        "downside_pressure_block_threshold",
        "breadth_weight",
        "trend_weight",
        "downside_weight",
        "volatility_weight",
        "risk_on_position_multiplier",
        "neutral_position_multiplier",
        "risk_off_position_multiplier",
        "strong_risk_off_position_multiplier",
    ]:
        assert key in config

    json.dumps(config)


def test_market_regime_formula_config_clamps_and_ignores_invalid_values():
    config = normalize_market_regime_formula_config(
        {
            "risk_off_threshold": -999,
            "risk_on_threshold": 999,
            "downside_weight": "bad-value",
            "neutral_position_multiplier": 9,
            "unknown": 123,
        }
    )

    assert config["risk_off_threshold"] == -80.0
    assert config["risk_on_threshold"] == 80.0
    assert config["downside_weight"] == 0.20
    assert config["neutral_position_multiplier"] == 1.2
    assert "unknown" not in config
