from app.services.event_aware_risk_overlay_conservative_calibration import (
    build_conservative_event_risk_overlay_calibration,
    generate_conservative_overlay_configs,
    score_conservative_overlay_metrics,
)


def test_conservative_overlay_calibration_contract_imports():
    assert callable(build_conservative_event_risk_overlay_calibration)
    assert callable(generate_conservative_overlay_configs)
    assert callable(score_conservative_overlay_metrics)
