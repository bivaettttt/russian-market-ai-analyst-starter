from app.services.consumer_signals import normalize_conservative_event_overlay_mode
from app.services.event_aware_risk_overlay import get_conservative_event_risk_overlay_config


def test_conservative_event_overlay_config_exact_preset():
    config = get_conservative_event_risk_overlay_config()
    assert config["config_id"] == "cons_t20_40_60_80_m95_e80_h65_x40_w100"
    assert config["moderate_threshold"] == 20
    assert config["elevated_threshold"] == 40
    assert config["high_threshold"] == 60
    assert config["extreme_threshold"] == 80
    assert config["moderate_multiplier"] == 0.95
    assert config["elevated_multiplier"] == 0.80
    assert config["high_multiplier"] == 0.65
    assert config["extreme_multiplier"] == 0.40
    assert config["research_source"] == "conservative_event_risk_overlay_calibration"


def test_conservative_overlay_mode_blocks_experimental_downgrade():
    assert normalize_conservative_event_overlay_mode("soft_adjust") == "soft_adjust"
    assert normalize_conservative_event_overlay_mode("diagnostic_only") == "diagnostic_only"
    assert normalize_conservative_event_overlay_mode("experimental_downgrade") == "soft_adjust"
    assert normalize_conservative_event_overlay_mode("bad_mode") == "soft_adjust"
